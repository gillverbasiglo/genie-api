import logging
import json
import asyncio
import requests
from typing import List
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..init_db import get_db
from app.models import User, Share, Notification, DeviceToken
from ..schemas.shares import ShareResponse, ShareCreate
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

async def send_single_notification(device_token: str, notification: Notification) -> bool:
    """
    Send a single push notification to a device
    
    Args:
        client: httpx AsyncClient instance
        device_token: Device token to send notification to
        notification: Notification object containing the notification details
        
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    try:
        # Send notification
        response = requests.post(
            settings.push_notification_url.get_secret_value(),
            json.dumps({
                "deviceToken": device_token,
                "message": notification.message,
                "title": notification.title,
                "badge": 1
            })
        )
        
        if response.status_code == 200:
            logger.info(f"Successfully sent notification to device {device_token[:10]}...")
            return True
        else:
            logger.error(f"Failed to send notification to device {device_token[:10]}... Status: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending notification to device {device_token[:10]}...: {str(e)}")
        return False

async def send_push_notifications(device_tokens: List[DeviceToken], notification: Notification):
    """
    Send push notifications to multiple devices via HTTP endpoint
    
    Args:
        device_tokens: List of DeviceToken objects
        notification: Notification object containing the notification details
    """
    if not device_tokens:
        logger.warning("No device tokens found for notification")
        return
        
    # Extract device tokens
    tokens = [token.token for token in device_tokens]
    logger.info(f"Found {len(tokens)} active device tokens for notification")
    
    # Create a semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(10)  # Limit to 10 concurrent requests
    
    async def send_with_semaphore(token: str) -> bool:
        async with semaphore:
            return await send_single_notification(token, notification)
    
    # Send notifications concurrently
    try:
        # Create tasks for all notifications
        tasks = [send_with_semaphore(token) for token in tokens]
        
        # Wait for all notifications to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successful notifications
        successful = sum(1 for result in results if result is True)
        failed = len(results) - successful
        
        logger.info(f"Notification delivery summary - Total: {len(tokens)}, Successful: {successful}, Failed: {failed}")
        
        # Log failed tokens
        failed_tokens = [token for token, success in zip(tokens, results) if not success]
        if failed_tokens:
            logger.warning(f"Failed to deliver notifications to tokens: {failed_tokens}")
                
    except Exception as e:
        logger.error(f"Error in push notification batch: {str(e)}")

@router.post("/recommendation", response_model=ShareResponse)
async def share_content(
    share_data: ShareCreate, 
    db: Session = Depends(get_db), 
    current_user: dict = Depends(get_current_user)
):
    logger.debug("Entering in Share")
    # Check if user exists

    from_user = db.execute(select(User).where(User.id == current_user['uid'])).scalar_one_or_none()
    if not from_user:
        raise HTTPException(status_code=404, detail="Sharing User not found")

    to_user = db.execute(select(User).where(User.id == share_data.to_user_id)).scalar_one_or_none()
    
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
    db.commit()
    db.refresh(share)
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
    db.commit()
    db.refresh(notification)
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
    device_tokens = db.execute(stmt).scalars().all()
    
    # Send push notifications
    asyncio.create_task(send_push_notifications(device_tokens, notification))
    
    return share

