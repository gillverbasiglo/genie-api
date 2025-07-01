import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from app.common import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from app.init_db import get_db
from app.schemas.llm_chat import PaginatedChatMessages, SaveChatRequest, SaveChatResponse
from app.services.llm_chat_service import save_chat_message, get_chat_messages

# Configure logger for LLM endpoints
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["LLM Chat"])

@router.post("/saveMessage", response_model=SaveChatResponse)
async def save_chat(
    request: SaveChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user) 
):
    """
    Save a llm chat message to the database.
    
    Args:
        request: SaveChatRequest containing the chat message data
        db: Database session dependency
        
    Returns:
        The saved chat message response
        
    Raises:
        HTTPException: If an error occurs during message saving
    """
    logger.info(f"Saving chat message for session: {request.session_id}")
    try:
        result = await save_chat_message(request, current_user['uid'], db)
        return result
    except Exception as e:
        logger.error(f"Error saving chat message: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/getMessages", response_model=list[PaginatedChatMessages])
async def get_chats(
    session_id: str,
    limit: int = Query(20, ge=1),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve all llm chat messages for a specific session.
    
    Args:
        session_id: Unique identifier for the chat session
        db: Database session dependency
        
    Returns:
        List of ChatMessageResponse objects for the session
        
    Raises:
        HTTPException: If an error occurs during message retrieval
    """
    logger.info(f"Retrieving chat messages for session: {session_id}")
    try:
        messages = await get_chat_messages(session_id, current_user['uid'], limit, offset, db)
        logger.info(f"Successfully retrieved {len(messages)} messages for session: {session_id}")
        return messages
    except Exception as e:
        logger.error(f"Error retrieving chat messages for session {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
