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
async def share_content(
    share_data: ShareCreate, 
    db: AsyncSession = Depends(get_db), 
    current_user: dict = Depends(get_current_user)
):
    logger.info("Processing content share request.")

    from_user = await get_user_by_id(db, current_user['uid'])
    to_user = await get_user_by_id(db, share_data.to_user_id)

    if not from_user or not to_user:
        logger.warning(f"User(s) not found: from_user={from_user}, to_user={to_user}")
        raise HTTPException(status_code=404, detail="One or both users not found")

    try:
        # Create share entry
        share = Share(
            from_user_id=from_user.id,
            to_user_id=to_user.id,
            content_id=share_data.content_id,
            content_type=share_data.content_type,
            message=share_data.message
        )
        db.add(share)

        # Create notification for the recipient
        notification = Notification(
            user_id=to_user.id,
            type=NotificationType.SHARE,
            title=share_data.title,
            message=share_data.message,
            data=json.dumps({
                "content_id": share_data.content_id,
                "content_type": share_data.content_type,
                "from_user_id": from_user.id,
                "share_id": share.id
            }),
            is_read=False
        )
        db.add(notification)

        await db.commit()
        await db.refresh(share)
        await db.refresh(notification)

        logger.info(f"Share created with ID: {share.id}")
        logger.info(f"Notification created with ID: {notification.id}")

    except Exception as e:
        logger.exception("Failed to create share or notification.")
        raise HTTPException(status_code=500, detail="Error creating share or notification")

    # Fetch active iOS device tokens for the recipient
    stmt = select(DeviceToken).where(
        DeviceToken.is_active == True,
        DeviceToken.user_id == to_user.id,
        DeviceToken.platform == "ios"
    )
    device_tokens_result = await db.execute(stmt)
    device_tokens = device_tokens_result.scalars().all()

    if not device_tokens:
        logger.info(f"No active iOS device tokens found for user {to_user.id}")

    # Send push notifications
    try:
        notification_responses = await send_push_notifications(device_tokens, notification)
        logger.info(f"Push notifications sent: {len(notification_responses)} responses")
    except Exception as e:
        logger.exception("Error while sending push notifications.")
        notification_responses = []

    # Map push notification responses to schema
    notification_response_models = [
        NotificationResponse(**response) for response in notification_responses
    ]

    # Construct final API response
    return ShareResponse(
        id=share.id,
        from_user_id=share.from_user_id,
        to_user_id=share.to_user_id,
        content_id=share.content_id,
        content_type=share.content_type,
        message=share.message,
        created_at=share.created_at,
        notification_responses=notification_response_models
    )



@router.get("/list", response_model=List[ShareListResponse])
async def get_shared_posts(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Get all pending invitations for these phone numbers
    stmt = select(Share).where(
        Share.to_user_id == current_user["uid"]
    ).options(
        joinedload(Share.from_user)
    )
    shares = await db.execute(stmt)
    shares = shares.scalars().all()
    
    return shares
