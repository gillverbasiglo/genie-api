import logging
import json
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..init_db import get_db
from app.models import User, Share, Notification, DeviceToken
from ..schemas.shares import ShareResponse, ShareCreate
from ..common import get_current_user
from ..common import manager as WebSocketConnectManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/share", tags=["share"])

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
    # Send push notifications (Will be implemented later)
    # asyncio.create_task(send_push_notifications(device_tokens, notification))
    
    return share

