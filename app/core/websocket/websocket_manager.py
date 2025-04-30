from fastapi import WebSocket
from typing import List, Dict
import logging



logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    async def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            await websocket.close()

    async def send_notification(self, user_id: str, message: dict):
        """Send a notification to the user over WebSocket."""
        websocket = self.active_connections.get(user_id)
        if websocket:
            await websocket.send_json(message)
        else:
            logger.warning(f"No active WebSocket connection for user {user_id}")
    
    async def send_personal_message(self, user_id: str, message: dict):
        websocket = self.active_connections.get(user_id)
        if websocket:
            logger.info(f"Sending message to {user_id}: {message}")
            await websocket.send_json(message)
        else:
            logger.warning(f"No active WebSocket connection for user {user_id}")

manager = ConnectionManager()
