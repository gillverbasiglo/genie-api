import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.init_db import get_db
from app.schemas.private_chat_message import PaginatedMessagesResponse
from app.services.chat_service import get_paginated_private_messages

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.get("/private/history", response_model=PaginatedMessagesResponse)
async def get_private_chat_messages(
    sender_id: str,
    receiver_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    db: AsyncSession = Depends(get_db)
):
    result = await get_paginated_private_messages(db, sender_id, receiver_id, skip, limit)
    return result

@router.get("/unread-count")
async def unread_message_count(
    user_id: str,
    friend_id: str,
    db: AsyncSession = Depends(get_db)
):
    count = await get_unread_message_count(db, user_id, friend_id)
    return {"unread_count": count}
