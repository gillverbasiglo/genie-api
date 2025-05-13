from fastapi import WebSocket
from typing import List, Dict
import logging



logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.online_users = set()

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.online_users.add(user_id)

    async def disconnect(self, websocket: WebSocket, user_id: str, reason: str = "Unknown"):
        logger.warning(f"Disconnecting user {user_id}. Reason: {reason}")
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        self.online_users.discard(user_id)
        try:
            if websocket.client_state.name == "CONNECTED":
                await websocket.close()
        except Exception as e:
            logger.warning(f"Failed to close WebSocket for user {user_id}: {e}")
        
    def is_user_online(self, user_id: str) -> bool:
        return user_id in self.online_users

    def get_online_users(self):
        return list(self.online_users)
    
    def get_active_connections(self):
        return self.active_connections

    async def send_notification(self, user_id: str, message: dict):
        """Send a notification to the user over WebSocket."""
        websocket = self.active_connections.get(user_id)
        if websocket:
            #await websocket.send_json(message)
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"WebSocket send failed for user {user_id}: {e}")
                await self.disconnect(websocket, user_id, reason="send_json failed")
        else:
            logger.warning(f"No active WebSocket connection for user {user_id}")
    
    async def send_personal_message(self, user_id: str, message: dict):
        websocket = self.active_connections.get(user_id)
        if websocket:
            #await websocket.send_json(message)
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"WebSocket send failed for user {user_id}: {e}")
                await self.disconnect(websocket, user_id, reason="send_json failed")
        else:
            logger.warning(f"No active WebSocket connection for user {user_id}")
    
    async def send_typing_status(self, receiver_id: str, message: dict):
         websocket = self.active_connections.get(receiver_id)
         if websocket:
             logger.info(f"Sending typing status to {receiver_id}")
             await websocket.send_json(message)
         else:
             logger.warning(f"No active WebSocket connection for user {receiver_id}")    
             
    async def send_user_status(self, receiver_id: str, message: dict):
         websocket = self.active_connections.get(receiver_id)
         if websocket:
             logger.info(f"Sending user status to {receiver_id}")
             await websocket.send_json(message)
         else:
             logger.warning(f"No active WebSocket connection for user {receiver_id}")
    

manager = ConnectionManager()