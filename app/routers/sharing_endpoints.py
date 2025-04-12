import logging
import json
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

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

# Share content with another user
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

    to_user = db.query(User).filter(User.id == share_data.to_user_id).first()
    
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
        title=f"{from_user.get('display_name', 'Someone')} shared content with you",
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
    
    # Send push notification if the user has registered devices
    device_tokens = db.query(DeviceToken).filter(
        DeviceToken.is_active == True,
        DeviceToken.user_id == share_data.to_user_id,
        DeviceToken.platform == "ios"
    ).all()
    
    # if device_tokens:
        # asyncio.create_task(send_push_notifications(device_tokens, notification))
    logger.debug(f"Shared Data: {share}")
    return share
