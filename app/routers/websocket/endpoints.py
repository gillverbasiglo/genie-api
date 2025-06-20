import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.websocket.message_handler import MessageHandler
from app.core.websocket.websocket_manager import manager  
from app.database import AsyncSessionLocal
from app.init_db import get_db
from app.models.user import User

# Set up the logger
logger = logging.getLogger(__name__)

# Create router for WebSocket endpoints
router = APIRouter(prefix="/ws", tags=["web-socket"])

@router.websocket("/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str
):
    """
    Main WebSocket endpoint for user connections.
    
    Args:
        websocket (WebSocket): The WebSocket connection instance
        user_id (str): Unique identifier of the connecting user
        db (AsyncSession): Database session for user verification and message handling
    
    Flow:
        1. Verifies user existence in database
        2. Establishes WebSocket connection
        3. Processes incoming messages until disconnection
        4. Handles cleanup on disconnection
    """
    try:
        logger.info(f"Attempting WebSocket connection for user: {user_id}")
        
        # Verify user exists in database
        async with AsyncSessionLocal() as db:
            results = await db.execute(select(User).where(User.id == user_id))
            user = results.scalar_one_or_none()

        if not user:
            logger.warning(f"User {user_id} not found")
            await websocket.close(code=1000)
            return

        # Establish WebSocket connection
        await manager.connect(websocket, user_id)
        logger.info(f"WebSocket connected for user {user_id}")

        # Initialize message handler for processing incoming messages
        message_handler = MessageHandler(manager)

        try:
            # Main message processing loop
            while True:
                message_data = await websocket.receive_json()
                logger.info(f"Message type: {message_data.get('type')}")
                
                # Process the received message
                await message_handler.handle_message(message_data, user_id)

        except WebSocketDisconnect:
            # Handle graceful disconnection
            await manager.disconnect(websocket, user_id)
            logger.info(f"User {user_id} disconnected from WebSocket")

    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Error during WebSocket connection for user {user_id}: {str(e)}")
        await websocket.close(code=1000)


@router.websocket("/test")
async def websocket_test(websocket: WebSocket):
    """
    Test endpoint for WebSocket functionality.
    
    Args:
        websocket (WebSocket): The WebSocket connection instance
    
    Flow:
        1. Accepts connection
        2. Sends test message
        3. Waits for 10 seconds
        4. Closes connection
    """
    try:
        await websocket.accept()
        logger.info("WebSocket test connection accepted.")
        
        # Send test message
        await websocket.send_text("Hello from server!")
        
        # Simulate connection duration
        await asyncio.sleep(10)
        
        # Close connection
        await websocket.close()
        logger.info("WebSocket test connection closed.")
    except Exception as e:
        logger.error(f"Error in WebSocket test connection: {str(e)}")
        await websocket.close()
