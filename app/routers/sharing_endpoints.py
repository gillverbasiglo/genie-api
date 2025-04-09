import logging
import json
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..models.device_token import DeviceToken
from ..models.shares import Share
from ..models.notifications import Notification
from ..schemas.shares import ShareResponse, ShareCreate
from ..common import get_current_user
from ..common import connection_manager as WebSocketConnectManager
from ..common import send

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

    # Check if user exists
    from_user = db.query(User).filter(User.id == current_user["uid"]).first()
    if not from_user:
        raise HTTPException(status_code=404, detail="User not found")

    to_user = db.query(User).filter(User.id == share_data.to_user_id).first()
    
    if not from_user or not to_user:
        raise HTTPException(status_code=404, detail="One or both users not found")
    
    # Create share record
    share = Share(
        from_user_id=share_data.from_user_id,
        to_user_id=share_data.to_user_id,
        content_id=share_data.content_id,
        content_type=share_data.content_type,
        message=share_data.message
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    
    # Create notification
    notification = Notification(
        user_id=share_data.to_user_id,
        type="share",
        title=f"{from_user.username} shared content with you",
        message=share_data.message,
        data=json.dumps({
            "content_id": share_data.content_id,
            "content_type": share_data.content_type,
            "from_user_id": share_data.from_user_id,
            "share_id": share.id
        }),
        is_read=False
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    
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
    
    if device_tokens:
        asyncio.create_task(send_push_notifications(device_tokens, notification))
    
    return share
