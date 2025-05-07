import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_
from app.models.chat.private_chat_message import Message

logger = logging.getLogger(__name__)


async def get_paginated_private_messages(
    db: AsyncSession,
    sender_id: str,
    receiver_id: str,
    skip: int = 0,
    limit: int = 3
):
    query = (
        select(Message)
        .where(
            or_(
                and_(Message.sender_id == sender_id, Message.receiver_id == receiver_id),
                and_(Message.sender_id == receiver_id, Message.receiver_id == sender_id)
            )
        )
        .order_by(Message.created_at.desc())  # latest first for scroll up
        .offset(skip)
        .limit(limit + 1)  # fetch one extra to check if more exist
    )

    result = await db.execute(query)
    messages = result.scalars().all()

    has_more = len(messages) > limit
    return {
        "messages": messages[:limit],
        "has_more": has_more
    }
