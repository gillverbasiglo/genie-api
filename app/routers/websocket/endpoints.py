import logging
import asyncio
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.websocket.message_handler import MessageHandler
from app.core.websocket.websocket_manager import manager  
from app.init_db import get_db
from app.models.user import User
from app.schemas.private_chat_message import MessageStatus
from datetime import datetime, timezone
from app.models.chat.private_chat_message import Message
from app.schemas.websocket import WebSocketMessageType

# Set up the logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["web-socket"])

@router.websocket("/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    try:
        logger.info(f"Attempting WebSocket connection for user: {user_id}")
        
        # Check if user exists
        results = await db.execute(select(User).where(User.id == user_id))
        user = results.scalar_one_or_none()

        if not user:
            logger.warning(f"User {user_id} not found")
            await websocket.close(code=1000)
            return

        # Connect the user
        await manager.connect(websocket, user_id)
        logger.info(f"WebSocket connected for user {user_id}")

        message_handler = MessageHandler(db, manager)

        try:
            while True:
                message_data = await websocket.receive_json()
                logger.info(f"message_data: {message_data}")
                
                await message_handler.handle_message(message_data, user_id)

        except WebSocketDisconnect:
            await manager.disconnect(websocket, user_id)
            logger.info(f"User {user_id} disconnected from WebSocket")

    except Exception as e:
        logger.error(f"Error during WebSocket connection for user {user_id}: {str(e)}")
        await websocket.close(code=1000)


@router.websocket("/test")
async def websocket_test(websocket: WebSocket):
    """
    A simple test WebSocket connection that sends a message to the client
    and closes the connection after a few seconds.
    """
    try:
        await websocket.accept()
        logger.info("WebSocket test connection accepted.")
        await websocket.send_text("Hello from server!")
        await asyncio.sleep(10)  # Simulate a delay before closing
        await websocket.close()
        logger.info("WebSocket test connection closed.")
    except Exception as e:
        logger.error(f"Error in WebSocket test connection: {str(e)}")
        await websocket.close()
