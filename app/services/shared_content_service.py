import logging
import json
import httpx
from typing import List, Dict, Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from app.schemas.notifications import NotificationType
from app.models import User, Share, Notification, DeviceToken
from app.schemas.shares import ShareCreate, NotificationResponse, ShareResponse
from app.config import settings
from app.schemas.websocket import WebSocketMessageType
from app.core.websocket.websocket_manager import manager

logger = logging.getLogger(__name__)

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
        logger.info(f"Sending push notification to device {token_obj.token} with payload: {payload}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post("http://localhost:3000/api/push-http", json=payload)
                push_responses.append({
                    "device_token": token_obj.token,
                    "status_code": response.status_code,
                    "response": response.json() if response.status_code == 200 else response.text
                })
        except Exception as e:
            push_responses.append({
                "device_token": token_obj.token,
                "status_code": 500,
                "error": f"Error sending notification: {str(e)}"
            })

    return push_responses

async def share_content(
    share_data: ShareCreate,
    from_user: User,
    to_user: User,
    db: AsyncSession
):
    """
    Share content between users and send notifications
    """
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
    
    # ✅ Send WebSocket notification if the user is connected
    try:
        # Prepare notification data within async context
        share_notification_data = {
            "id": share.id,
            "type": WebSocketMessageType.SHARED_ITEM,
            "message": share_data.message,
            "from_user": {
                "id": from_user.id,
                "email": from_user.email,
                "display_name": from_user.display_name,
                "phone_number": from_user.phone_number
            },
            "content_type": share_data.content_type,
            "content_id": share_data.content_id,
            "to_user": {
                "id": to_user.id,
                "email": to_user.email,
                "display_name": to_user.display_name,
                "phone_number": to_user.phone_number
            },
            "created_at": share.created_at.isoformat() if share.created_at else None,
        }
        # Convert to JSON string before sending
        notification_json = json.dumps(share_notification_data)
        await manager.send_notification(to_user.id, share_notification_data)

    except Exception as e:
        # Log it or silently continue
        logger.warning(f"Failed to send WebSocket share notification: {e}")

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
        logger.info(f"Push notifications sent: {notification_responses} responses")
    except Exception as e:
        logger.exception("Error while sending push notifications.")
        notification_responses = []

    # Map push notification responses to schema
    notification_response_models = [
        NotificationResponse(**response) for response in notification_responses
    ]

    return ShareResponse(
        id=share.id,
        from_user_id=share.from_user_id,
        to_user_id=share.to_user_id,
        content_id=share.content_id,
        content_type=share.content_type,
        message=share.message,
        is_Seen=share.is_Seen,
        created_at=share.created_at,
        notification_responses=notification_response_models
    )

async def get_shared_posts(
    current_user_id: str,
    db: AsyncSession,
    seen_status: str = "all"  # "all", "seen", or "unseen"
):
    """
    Get all shared posts for a user with optional seen status filter
    
    Args:
        current_user_id: ID of the current user
        db: Database session
        seen_status: Filter by seen status ("all", "seen", or "unseen")
        
    Returns:
        List of Share objects matching the filter
    """
    # Base query
    stmt = select(Share).where(
        Share.to_user_id == current_user_id
    ).options(
        joinedload(Share.from_user)
    )

    # Add seen status filter if specified
    if seen_status == "seen":
        stmt = stmt.where(Share.is_Seen == True)
    elif seen_status == "unseen":
        stmt = stmt.where(Share.is_Seen == False)
    # "all" doesn't need any additional filter

    shares = await db.execute(stmt)
    return shares.scalars().all()

async def update_share_seen_status(
    share_id: str,
    current_user_id: str,
    db: AsyncSession
):
    """
    Update the is_Seen status of a share
    
    Args:
        share_id: ID of the share to update
        current_user_id: ID of the current user
        db: Database session
        
    Returns:
        Updated Share object
    """
    # Get the share
    stmt = select(Share).where(
        Share.id == share_id,
        Share.to_user_id == current_user_id  # Ensure user is the recipient
    )
    result = await db.execute(stmt)
    share = result.scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=404, detail="Share not found or you don't have permission to update it")

    # Update is_Seen status
    share.is_Seen = True
    await db.commit()
    await db.refresh(share)

    return share
