import logging
import json
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..init_db import get_db
from ..models.user import User
from ..models.device_token import DeviceToken
from ..models.shares import Share
from ..models.notifications import Notification
from ..schemas.shares import ShareResponse, ShareCreate
from ..common import get_current_user
from ..common import manager as WebSocketConnectManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/share", tags=["share"])

async def send_push_notifications(device_tokens: list, notification: Notification):
    """
    Send push notifications to multiple devices
    """
    if not device_tokens:
        logger.warning("No device tokens found for notification")
        return
        
    # Extract device tokens
    tokens = [token.token for token in device_tokens]
    logger.info(f"Found {len(tokens)} active device tokens for notification")
    
    # Parse notification data
    try:
        notification_data = json.loads(notification.data)
        logger.debug(f"Notification data: {notification_data}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse notification data: {e}")
        return
        
    # Send notifications
    try:
        results = await apns_service.send_bulk_notifications(
            device_tokens=tokens,
            title=notification.title,
            body=notification.message,
            data=notification_data,
            sound="default",
            badge=1
        )
        
        # Log delivery results
        successful = sum(1 for success in results.values() if success)
        failed = len(results) - successful
        logger.info(f"Notification delivery summary - Total: {len(results)}, Successful: {successful}, Failed: {failed}")
        
        # Log failed tokens
        failed_tokens = [token for token, success in results.items() if not success]
        if failed_tokens:
            logger.warning(f"Failed to deliver notifications to tokens: {failed_tokens}")
            
    except Exception as e:
        logger.error(f"Error sending push notifications: {str(e)}")

@router.post("/recommendation", response_model=ShareResponse)
async def share_content(
    share_data: ShareCreate, 
    db: Session = Depends(get_db), 
    current_user: dict = Depends(get_current_user)
):
    logger.debug("Entering in Share")
    # Check if user exists
    from_user = current_user
    if not from_user:
        raise HTTPException(status_code=404, detail="Sharing User not found")

    to_user = db.execute(select(User).where(User.id == share_data.to_user_id)).scalar_one_or_none()
    
    if not from_user or not to_user:
        logger.debug("Error in Share")
        raise HTTPException(status_code=404, detail="One or both users not found")
    
    # Create share record
    share = Share(
        from_user_id=from_user['uid'],
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
        title=f"{from_user.get('display_name', 'Someone')} shared content with you with id: {share_data.content_id}",
        message=share_data.message,
        data=json.dumps({
            "content_id": share_data.content_id,
            "content_type": share_data.content_type,
            "from_user_id": from_user['uid'],
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

