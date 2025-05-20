import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_
from app.models.chat.private_chat_message import Message
from sqlalchemy import func
from app.schemas.private_chat_message import MessageStatus

# Configure logger for this module
logger = logging.getLogger(__name__)

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

