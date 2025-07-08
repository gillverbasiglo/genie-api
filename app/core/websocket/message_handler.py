import logging
import uuid
from typing import Callable, Dict, List, Union

from sqlalchemy import select
from app.core.websocket.websocket_manager import ConnectionManager
from app.database import AsyncSessionLocal
from app.models.chat.private_chat_message import Message
from app.schemas.websocket import WebSocketMessageType
from app.schemas.private_chat_message import MessageStatus, MessageType
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from app.services.chat_service import call_recommendation_api, send_push_notification_for_offline_user
from app.services.user_service import get_user_by_id

# Set up the logger
logger = logging.getLogger(__name__)

class MessageHandler:
    """
    Handles different types of WebSocket messages and manages real-time communication.
    """

    def __init__(self, manager: ConnectionManager):
        """
        Initialize the MessageHandler with database session and WebSocket manager.

        Args:
            db (AsyncSession): SQLAlchemy async database session
            manager: WebSocket connection manager instance
        """
        self.manager = manager
        # Map message types to their handler functions
        self.handlers: Dict[str, Callable] = {
            WebSocketMessageType.PRIVATE_CHAT_MESSAGE: self.handle_private_chat_message,
            WebSocketMessageType.MESSAGE_UPDATE: self.handle_message_status_update,
            WebSocketMessageType.TYPING_STATUS: self.handle_typing_status,
            WebSocketMessageType.USER_STATUS: self.handle_user_status,
            WebSocketMessageType.DRAG_END: self.handle_drag_end,
            WebSocketMessageType.DRAG_UPDATE: self.handle_drag_update
        }

    async def handle_message(self, message_data: dict, user_id: str):
        """
        Route incoming messages to appropriate handler based on message type.

        Args:
            message_data (dict): The message data containing type and content
            user_id (str): ID of the user sending the message
        """
        message_type = message_data.get("type")
        handler = self.handlers.get(message_type)

        if handler:
            await handler(message_data, user_id)
        else:
            logger.warning(f"Unsupported message type: {message_type}")

    def extract_result_only(self, response: List[Dict]) -> Union[Dict, None]:
        for item in response:
            if 'a' in item:
                result = item['a'].get('result')
                if result:
                    return result
        return None

    async def handle_private_chat_message(self, message_data: dict, user_id: str):
        """
        Process and store private chat messages.

        This method:
        1. Creates a new message record in the database
        2. Sends the message to the intended receiver
        3. Updates message status

        Args:
            message_data (dict): Message data containing receiver_id and content
            user_id (str): ID of the message sender
        """
        receiver_id = message_data.get("receiver_id")
        content = message_data.get("content")
        timestamp = datetime.now()

        # Create and store new message in database
        async with AsyncSessionLocal() as db:
            new_message = Message(
                id=uuid.uuid4(),
                sender_id=user_id,
                receiver_id=receiver_id,
                message_type=MessageType.TEXT,
                content=content,
                media_url=None,
                metadata=None,
                status=MessageStatus.SENT,
                created_at=timestamp,
                updated_at=timestamp
            )
                    
            db.add(new_message)
            await db.commit()
            await db.refresh(new_message)

            # Convert timestamp to ISO format for JSON serialization
            timestamp_str = timestamp.isoformat()

            message_dict = {
                "type":  WebSocketMessageType.PRIVATE_CHAT_MESSAGE, 
                "id": new_message.id, 
                "sender_id": user_id, 
                "receiver_id": receiver_id,
                "content": content, 
                "status": MessageStatus.SENT, 
                "timestamp": timestamp_str
            }

            # Handle real-time notification delivery
            is_user_online = self.manager.is_user_online(receiver_id)
            logger.info(f"Recipient user online: {is_user_online}")

            if is_user_online:
                await self.manager.send_personal_message(
                            receiver_id,
                            message_dict
                        )
            else:
                sender_user = await get_user_by_id(db, user_id)
                await send_push_notification_for_offline_user(receiver_id, db, sender_user.display_name, content)

    async def handle_drag_update(self, message_data: dict, user_id: str):
        logger.info(f"Drag update message received: {message_data}")
        await self.manager.send_personal_message(
            message_data.get("userId"),
            {
                "type": WebSocketMessageType.DRAG_UPDATE,
                "message": message_data.get("message")
            }
        )
        
    async def handle_drag_end(self, message_data: dict, user_id: str):
        logger.info(f"Drag end message received: {message_data}")
        await self.manager.send_personal_message(
            message_data.get("userId"),
            {
                "type": WebSocketMessageType.DRAG_END,
                "message": message_data.get("message")
            }
        )   

    async def handle_message_status_update(self, message_data: dict, user_id: str):
        """
        Update the status of a message (SENT, DELIVERED, READ).

        Args:
            message_data (dict): Contains message_id and new status
            user_id (str): ID of the user updating the status
        """
        message_id = message_data.get("message_id")
        new_status = message_data.get("status")

        # Validate status value
        if new_status not in [MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ]:
            logger.warning(f"Invalid status update request: {new_status}")
            return

        # Fetch and update message status
        async with AsyncSessionLocal() as db:
            stmt = select(Message).where(Message.id == message_id)
            result = await db.execute(stmt)
            message = result.scalar_one_or_none()

            if message:
                message.status = new_status
                message.updated_at = datetime.now()
                await db.commit()
                await db.refresh(message)

                logger.info(f"Updated message status to {new_status} for message {message_id}")

                # Notify sender of status change
                await self.manager.send_personal_message(
                    message.sender_id,
                    {
                        "type": WebSocketMessageType.MESSAGE_STATUS_UPDATE,
                        "message_id": message_id,
                        "status": new_status
                    }
                )
            else:
                logger.warning(f"Message not found for ID {message_id}")
            
    async def handle_typing_status(self, messsage_data: dict, user_id: str):
        """
        Handle typing indicator messages between users.

        Args:
            messsage_data (dict): Contains typing status information
            user_id (str): ID of the user whose typing status is being updated
        """
        if user_id:
            await self.manager.send_typing_status(
                messsage_data.get("receiver_id"),
                {
                    "type": WebSocketMessageType.TYPING_STATUS,
                    "user_id": messsage_data.get("user_id"),
                    "receiver_id": messsage_data.get("receiver_id"),
                    "is_typing": messsage_data.get("is_typing")
                }
            )
        else:
            logger.warning(f"Typing status not sent")
            
    async def handle_user_status(self, messsage_data: dict, user_id: str):
        """
        Handle user online/offline status updates.

        This method broadcasts user status changes to both the user and their contacts.

        Args:
            messsage_data (dict): Contains user status information
            user_id (str): ID of the user whose status is being updated
        """
        logger.info(f"user_id in handle_user_status is: {user_id}")
        if user_id:
            # Send status update to receiver
            await self.manager.send_user_status(
                messsage_data.get("receiver_id"),
                {
                    "type": WebSocketMessageType.USER_STATUS,
                    "user_id": messsage_data.get("user_id"),
                    "receiver_id": messsage_data.get("receiver_id"),
                    "timestamp": messsage_data.get("timestamp"),
                    "status": messsage_data.get("status")
                }
            )
            # Send status update to sender
            await self.manager.send_user_status(
                messsage_data.get("user_id"),
                {
                    "type": WebSocketMessageType.USER_STATUS,
                    "user_id": messsage_data.get("receiver_id"),
                    "receiver_id": messsage_data.get("user_id"),
                    "timestamp": messsage_data.get("timestamp"),
                    "status": messsage_data.get("status")
                }
            )
        else:
            logger.warning(f"User status not sent")
            