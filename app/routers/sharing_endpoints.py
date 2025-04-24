import logging
import json
import asyncio
import httpx
from typing import List, Dict, Any
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..init_db import get_db
from app.models import User, Share, Notification, DeviceToken
from ..schemas.shares import ShareResponse, ShareCreate, NotificationResponse
from ..common import get_current_user
from ..common import manager as WebSocketConnectManager
from ..config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/share", tags=["share"])

class TestNotificationPayload(BaseModel):
    device_token: str
    title: str
    message: str
    badge: int = 1

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
    logger.debug("Entering in Share")
    
    # Get from_user
    result_from_user = await db.execute(select(User).where(User.id == current_user['uid']))
    from_user = result_from_user.scalar_one_or_none()
    if not from_user:
        raise HTTPException(status_code=404, detail="Sharing User not found")

    # Get to
    result_to_user = await db.execute(select(User).where(User.id == share_data.to_user_id))
    to_user = result_to_user.scalar_one_or_none()
    if not from_user or not to_user:
        logger.debug("Error in Share")
        raise HTTPException(status_code=404, detail="One or both users not found")
    
    
    # Create share record
    share = Share(
        from_user_id=from_user.id,
        to_user_id=share_data.to_user_id,
        content_id=share_data.content_id,
        content_type=share_data.content_type,
        message=share_data.message
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)
    logger.debug("Added Share")
    
    # Create notification
    notification = Notification(
        user_id=share_data.to_user_id,
        type="share",
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
    await db.refresh(notification)
    logger.debug("Added Notification")
    
    # Send real-time notification if user is connected
    notification_data = {
        "type": "share",
        "title": notification.title,
        "message": notification.message,
        "data": json.loads(notification.data),
        "created_at": notification.created_at.isoformat()
    }
    
    # Send real-time update via WebSocket if the user is online
    asyncio.create_task(WebSocketConnectManager.send_notification(share_data.to_user_id, notification_data))
    
    # Get active device tokens for the user
    stmt = select(DeviceToken).where(
        DeviceToken.is_active == True,
        DeviceToken.user_id == share_data.to_user_id,
        DeviceToken.platform == "ios"
    )
    device_tokens_result = await db.execute(stmt)
    device_tokens = device_tokens_result.scalars().all()
    # Send push notifications and get responses
    print("notification_responses_start")
    notification_responses = await send_push_notifications(device_tokens, notification)
    print("notification_responses", notification_responses)
    
    # Convert notification responses to Pydantic models
    notification_response_models = [
        NotificationResponse(**response) for response in notification_responses
    ]
    
    # Create response with notification results
    response = ShareResponse(
        id=share.id,
        from_user_id=share.from_user_id,
        to_user_id=share.to_user_id,
        content_id=share.content_id,
        content_type=share.content_type,
        message=share.message,
        created_at=share.created_at,
        notification_responses=notification_response_models
    )
    
    return response
@router.get("/list", response_model=List[ShareCreate])
async def get_shared_posts(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Get all pending invitations for these phone numbers
    stmt = select(Share).where(
        Share.to_user_id == current_user["uid"]
    )
    shares = await db.execute(stmt)
    shares = shares.scalars().all()
    
    return shares 
