import logging
import uuid
from typing import Callable, Dict

from sqlalchemy import select
from app.models.chat.private_chat_message import Message
from app.schemas.websocket import WebSocketMessageType
from app.schemas.private_chat_message import MessageStatus
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from app.services.friends_service import are_friends

# Set up the logger
logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, db: AsyncSession, manager):
        self.db = db
        self.manager = manager
        self.handlers: Dict[str, Callable] = {
            WebSocketMessageType.PRIVATE_CHAT_MESSAGE: self.handle_private_chat_message,
            WebSocketMessageType.MESSAGE_UPDATE: self.handle_message_status_update,
            WebSocketMessageType.TYPING_STATUS: self.handle_typing_status,
            WebSocketMessageType.USER_STATUS: self.handle_user_status
        }

    async def handle_message(self, message_data: dict, user_id: str):
        message_type = message_data.get("type")
        handler = self.handlers.get(message_type)

        if handler:
            await handler(message_data, user_id)
        else:
            logger.warning(f"Unsupported message type: {message_type}")

    async def handle_private_chat_message(self, message_data: dict, user_id: str):
        receiver_id = message_data.get("receiver_id")
        content = message_data.get("content")
        timestamp = datetime.now()

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
                    
        self.db.add(new_message)
        await self.db.commit()
        await self.db.refresh(new_message)

        # Convert the timestamp to an ISO 8601 string format
        timestamp_str = timestamp.isoformat()

        # Send message to receiver
        logger.info(f"Sending message to {receiver_id}: {content}")
        await self.manager.send_personal_message(
                        receiver_id,
                        {"type":  WebSocketMessageType.PRIVATE_CHAT_MESSAGE, 
                         "id": new_message.id, 
                         "sender_id": user_id, 
                         "receiver_id": receiver_id,
                         "content": content, 
                         "status": MessageStatus.SENT, 
                         "timestamp": timestamp_str}
                    )
        
    async def handle_message_status_update(self, message_data: dict, user_id: str):
        message_id = message_data.get("message_id")
        new_status = message_data.get("status")

        # Validate status
        if new_status not in [MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ]:
            logger.warning(f"Invalid status update request: {new_status}")
            return

        stmt = select(Message).where(Message.id == message_id)
        result = await self.db.execute(stmt)
        message = result.scalar_one_or_none()

        if message:
            message.status = new_status
            message.updated_at = datetime.now()
            await self.db.commit()
            await self.db.refresh(message)

            logger.info(f"Updated message status to {new_status} for message {message_id}")

            # Notify the sender of the status update
            await self.manager.send_personal_message(
                message.sender_id,
                {"type": WebSocketMessageType.MESSAGE_STATUS_UPDATE,
                 "message_id": message_id,
                 "status": new_status}
            )
        else:
            logger.warning(f"Message not found for ID {message_id}")
            
    async def handle_typing_status(self, messsage_data: dict, user_id: str):
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
        logger.info(f"user_id in handle_user_status is: {user_id}")
        if user_id:
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
            