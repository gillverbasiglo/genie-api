import logging
import asyncio
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.websocket.websocket_manager import manager  
from app.init_db import get_db
from app.models.user import User
from app.schemas.private_chat_message import MessageStatus
from datetime import datetime, timezone
from app.models.chat.private_chat_message import Message

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

        try:
            while True:
                message_data = await websocket.receive_json()
                message_type = message_data.get("type")

                if message_type == "chatMessage":
                    receiver_id = message_data.get("receiver_id")
                    content = message_data.get("content")
                    timestamp = datetime.utcnow()

                    # Save message to the database
                    new_message = Message(
                        id=uuid.uuid4(),
                        sender_id=user_id,
                        receiver_id=receiver_id,
                        content=content,
                        status=MessageStatus.SENT,
                        created_at=timestamp,
                        updated_at=timestamp
                    )
                    logger.info(f"saving message to db: {new_message.status}")
                    #db.add(new_message)
                    #await db.commit()

                    # Convert the timestamp to an ISO 8601 string format
                    timestamp_str = timestamp.isoformat()

                    # Send message to receiver
                    logger.info(f"Sending message to {receiver_id}: {content}")
                    await manager.send_personal_message(
                        receiver_id,
                        {"type": "chatMessage", "sender_id": user_id, "content": content, "status": MessageStatus.SENT, "timestamp": timestamp_str}
                    )

                else:
                    logger.warning(f"Unsupported message type received: {message_type}")

        except WebSocketDisconnect:
            manager.disconnect(websocket, user_id)
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
