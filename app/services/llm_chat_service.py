import logging
from uuid import uuid4
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.llm.llm_chat_session import LLMChatSession
from app.models.llm.llm_chat_message import LLMChatMessage
from app.schemas.llm_chat import SaveChatRequest, ChatMessageResponse
from sqlalchemy.orm import selectinload
from sqlalchemy import func, select

# Configure logger for this module
logger = logging.getLogger(__name__)

async def save_chat_message(request: SaveChatRequest, user_id: str, db: AsyncSession):
    """
    Save a chat message to the database.
    
    Args:
        request: SaveChatRequest containing message details and session info
        user_id: ID of the user sending the message
        db: Async database session
        
    Returns:
        dict: Response containing message_id and session_id
        
    Raises:
        HTTPException: If session is not found for existing sessions
    """
    logger.info(f"Saving chat message for user {user_id}, session_id: {request.session_id}, is_new_session: {request.is_new_session}")
    session_id: str
    if request.is_new_session:
        # Always generate a new session ID when creating a new session
        session_id = str(uuid4())
        logger.debug(f"Creating new chat session with ID: {session_id}")
        
        session = LLMChatSession(
            id=session_id,
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        logger.info(f"Successfully created new chat session")
    else:
        session_id = request.session_id
        # Retrieve existing session and verify ownership
        logger.debug(f"Retrieving existing session: {request.session_id}")
        result = await db.execute(
            select(LLMChatSession).where(
                LLMChatSession.id == session_id,
                LLMChatSession.user_id == user_id
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            logger.warning(f"Session not found: {request.session_id} for user: {user_id}")
            raise HTTPException(status_code=404, detail="Session not found")

        # Update session timestamp
        session.updated_at = datetime.now(timezone.utc)
        db.add(session)
        await db.commit()

    # Create and save the chat message
    message_id = str(uuid4())
    logger.debug(f"Creating message with ID: {message_id}, sender: {request.sender}")
    
    message = LLMChatMessage(
        id=message_id,
        session_id=session_id,
        sender=request.sender,
        content=request.content,
        created_at=datetime.now(timezone.utc)
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    
    response = {
        "message": "Chat saved",
        "session_id": session_id
    }   
    logger.info(f"Chat message saved: {response}")
    return response


async def get_chat_messages(session_id: str, user_id: str, limit: int, offset: int, db: AsyncSession):
    """
    Retrieve paginated chat messages for a specific session.
    
    Args:
        session_id: ID of the chat session to retrieve messages from
        user_id: ID of the user requesting the messages (for authorization)
        limit: Maximum number of messages to return
        offset: Number of messages to skip for pagination
        db: Async database session
        
    Returns:
        dict: Response containing total message count and list of messages
        
    Raises:
        HTTPException: If session is not found or user doesn't have access
    """
    logger.info(f"Retrieving chat messages for session: {session_id}, user: {user_id}, limit: {limit}, offset: {offset}")
    
    # Verify session exists and user has access
    result = await db.execute(
        select(LLMChatSession)
        .where(LLMChatSession.id == session_id, LLMChatSession.user_id == user_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        logger.warning(f"Session not found: {session_id} for user: {user_id}")
        raise HTTPException(status_code=404, detail="Session not found")

    logger.debug(f"Session found: {session.id}, retrieving messages")

    # Get total message count for pagination metadata
    total_result = await db.execute(
        select(func.count(LLMChatMessage.id))
        .where(LLMChatMessage.session_id == session_id)
    )
    total = total_result.scalar()
    logger.debug(f"Total messages in session: {total}")

    # Get paginated messages ordered by creation time
    result = await db.execute(
        select(LLMChatMessage)
        .where(LLMChatMessage.session_id == session_id)
        .order_by(LLMChatMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    messages = result.scalars().all()
    
    logger.info(f"Retrieved {len(messages)} messages from session {session_id}")

    # Convert database models to response schemas
    response_messages = [
        ChatMessageResponse(
            id=msg.id,
            sender=msg.sender,
            content=msg.content,
            created_at=msg.created_at,
        )
        for msg in messages
    ]

    return {
        "total": total,
        "messages": response_messages
    }
