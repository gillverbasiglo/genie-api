import logging
import json
import asyncio
import httpx
from typing import List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.schemas.notifications import NotificationType
from app.init_db import get_db
from app.models import User, Share, Notification, DeviceToken
from app.schemas.shares import ShareListResponse, ShareResponse, ShareCreate, NotificationResponse
from app.common import get_current_user
from app.common import manager as WebSocketConnectManager
from app.config import settings
from app.services.user_service import get_user_by_id
from sqlalchemy.orm import joinedload
from app.services.shared_content_service import share_content, get_shared_posts, update_share_seen_status

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/share", tags=["share"])

async def send_single_notification(device_token: str, notification: Notification) -> Dict[str, Any]:
    """
    Send a single push notification to a device
    
    Args:
        device_token: Device token to send notification to
        notification: Notification object containing the notification details
        
    Returns:
        Dict containing notification response details
    """
    try:
        # Prepare notification payload
        payload = {
            "deviceToken": device_token,
            "message": notification.message,
            "title": notification.title,
            "badge": 1
        }
        
        # Send notification
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.push_notification_url.get_secret_value(),
                json=payload,
                timeout=10.0
            )
            
            response_data = response.json()
            
            if response.status_code == 200:
                logger.info(f"Successfully sent notification to device {device_token[:10]}...")
                return {
                    "device_token": device_token,
                    "success": True,
                    "message": "Notification sent successfully",
                    "apns_id": response_data.get("apnsId"),
                    "apns_unique_id": response_data.get("apnsUniqueId")
                }
            else:
                logger.error(f"Failed to send notification to device {device_token[:10]}... Status: {response.status_code}")
                return {
                    "device_token": device_token,
                    "success": False,
                    "message": f"Failed to send notification. Status: {response.status_code}",
                    "apns_id": None,
                    "apns_unique_id": None
                }
            
    except Exception as e:
        logger.error(f"Error sending notification to device {device_token[:10]}...: {str(e)}")
        return {
            "device_token": device_token,
            "success": False,
            "message": f"Error sending notification: {str(e)}",
            "apns_id": None,
            "apns_unique_id": None
        }

async def send_push_notifications(device_tokens: List[DeviceToken], notification: Notification) -> List[Dict[str, Any]]:
    push_responses = []

    for token_obj in device_tokens:
        payload = {
            "deviceToken": token_obj.token,
            "message": notification.message,
            "title": notification.title,
            "badge": 1
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{settings.push_notification_url.get_secret_value()}", json=payload)
                push_responses.append({
                    "device_token": token_obj.token,
                    "status_code": response.status_code,
                    "response": response.json() if response.status_code == 200 else response.text
                })
        except Exception as e:
            push_responses.append({
                "device_token": token_obj.token,
                "status_code": 500,
                "response": f"Error sending notification: {str(e)}"
            })

    return push_responses

@router.post("/recommendation", response_model=ShareResponse)
async def share_content_endpoint(
    share_data: ShareCreate, 
    db: AsyncSession = Depends(get_db), 
    current_user: dict = Depends(get_current_user)
):
    logger.info("Processing content share request.")

    from_user = await get_user_by_id(db, current_user['uid'])
    to_user = await get_user_by_id(db, share_data.to_user_id)

    result = await share_content(share_data, from_user, to_user, db)

    return ShareResponse(
        id=result["share"].id,
        from_user_id=result["share"].from_user_id,
        to_user_id=result["share"].to_user_id,
        content_id=result["share"].content_id,
        content_type=result["share"].content_type,
        message=result["share"].message,
        created_at=result["share"].created_at,
        notification_responses=result["notification_responses"]
    )

@router.get("/list", response_model=List[ShareListResponse])
async def get_shared_posts_endpoint(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    shares = await get_shared_posts(current_user["uid"], db)
    return shares

@router.patch("/{share_id}/seen", response_model=ShareResponse)
async def mark_share_as_seen(
    share_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark a share as seen by the recipient
    """
    share = await update_share_seen_status(share_id, current_user["uid"], db)
    
    return ShareResponse(
        id=share.id,
        from_user_id=share.from_user_id,
        to_user_id=share.to_user_id,
        content_id=share.content_id,
        content_type=share.content_type,
        message=share.message,
        is_Seen=share.is_Seen, 
        created_at=share.created_at,
        notification_responses=[]  # No notifications for seen status update
    )
