import json
import logging
from fastapi.responses import PlainTextResponse
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_
from app.models.chat.private_chat_message import Message
from sqlalchemy import func
from app.models.device_token import DeviceToken
from app.models.notifications import Notification
from app.schemas.notifications import NotificationType
from app.schemas.private_chat_message import MessageStatus
from app.services.shared_content_service import send_push_notifications

# Configure logger for this module
logger = logging.getLogger(__name__)

async def send_push_notification_for_offline_user(
    receiver_id: str, db: AsyncSession, title: str, content: str
):
    
    # Create notification for the recipient
    notification = Notification(
        user_id=receiver_id,
        type=NotificationType.PRIVATE_CHAT_MESSAGE,
        title=title,
        message=content
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    # Send push notification for offline users
    stmt = select(DeviceToken).where(
        DeviceToken.is_active == True,
        DeviceToken.user_id == receiver_id,
        DeviceToken.platform == "ios"
    )
    device_tokens_result = await db.execute(stmt)
    device_tokens = device_tokens_result.scalars().all()

    if not device_tokens:
        logger.info(f"No active iOS device tokens found for user {receiver_id}")

    logger.info(f"Sending push notification: {notification}")

    try:
        notification_responses = await send_push_notifications(device_tokens, notification)
        logger.info(f"Push notifications sent: {len(notification_responses)} responses")
        logger.info(f"Push notifications responses: {notification_responses}")
    except Exception as e:
        logger.exception("Error while sending push notifications.")
        notification_responses = []

async def get_paginated_private_messages(
    db: AsyncSession,
    sender_id: str,
    receiver_id: str,
    skip: int = 0,
    limit: int = 3
):
    """
    Retrieve paginated private messages between two users.
    
    Args:
        db (AsyncSession): Database session
        sender_id (str): ID of the message sender
        receiver_id (str): ID of the message receiver
        skip (int): Number of messages to skip (for pagination)
        limit (int): Maximum number of messages to return
        
    Returns:
        dict: Dictionary containing:
            - messages: List of Message objects
            - has_more: Boolean indicating if more messages exist
    """
    # Query messages where either user is sender or receiver
    query = (
        select(Message)
        .where(
            or_(
                and_(Message.sender_id == sender_id, Message.receiver_id == receiver_id),
                and_(Message.sender_id == receiver_id, Message.receiver_id == sender_id)
            )
        )
        .order_by(Message.created_at.desc())  # Sort by newest first for scroll-up pagination
        .offset(skip)
        .limit(limit + 1)  # Fetch one extra message to determine if more exist
    )

    result = await db.execute(query)
    messages = result.scalars().all()

    # Check if there are more messages beyond the current page
    has_more = len(messages) > limit
    return {
        "messages": messages[:limit],  # Return only the requested number of messages
        "has_more": has_more
    }

async def get_unread_message_count(
    db: AsyncSession,
    receiver_id: str
):
    """
    Count the number of unread messages for a specific user.
    
    Args:
        db (AsyncSession): Database session
        receiver_id (str): ID of the user to count unread messages for
        
    Returns:
        int: Number of unread messages
    """
    # Count messages that are not marked as READ
    query = select(func.count(Message.id)).where(
        and_(
            Message.receiver_id == receiver_id,
            Message.status != MessageStatus.READ
        )
    )
    
    result = await db.execute(query)
    return result.scalar_one()

async def call_recommendation_api(
    db: AsyncSession,
    user_1_id: str,
    user_2_id: str,
    query: str
):
    payload = {
    "messages": [
        {
        "role": "user",
        "parts": [
            {
            "type": "text",
            "text": query
            }
        ]
        }
    ],
    "group": "web",
    "model": "genie-gemini"
    }
    
    """async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", "https://genesis-ehfyuaedu-genie-the-ai.vercel.app/api/search", json=payload) as response:
            async for line in response.aiter_lines():
                if not line or ':' not in line:
                    continue  # skip invalid lines
                prefix, content = line.split(':', 1)
                try:
                    parsed = json.loads(content)
                    yield {prefix: parsed}
                except json.JSONDecodeError:
                    yield {prefix: content}"""
    async with httpx.AsyncClient(timeout=None) as client:
        response = await client.post(
            "https://genesis-engine.vercel.app/api/search",
            json=payload
        )
        response.raise_for_status()  # raise exception if the request failed
        content = response.text
        result = []
        for line in content.splitlines():
            if not line or ':' not in line:
                continue
            prefix, data = line.split(':', 1)
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                parsed = data
            result.append({prefix: parsed})

        return result
