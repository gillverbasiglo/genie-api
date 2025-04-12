import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import initialize_app, auth
from typing import Dict, List

from app.config import settings
from .init_db import get_db
from sqlalchemy.orm import Session
from .models.user import User

app = FastAPI()
security = HTTPBearer()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Firebase
firebase_app = None

logger = logging.getLogger(__name__)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
    
    async def send_notification(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                await connection.send_json(message)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    firebase_app = None

manager = ConnectionManager()


# Dependency to get current user from token
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    if settings.environment != "production":
        logger.info("Development mode - skipping token verification")
        return {
            "uid": "xX51rMgKyUgHWIzj25Ewccq9gmt1",
            "email": "fatehv@example.com",
            "display_name": "Fateh",
            "name": "Development User"
        }

    # In production, verify the token
    logger.info(f"Verifying token: {token[:10]}...{token[-10:]} (truncated for security)")
    try:
        # Add more detailed debugging
        logger.debug("About to verify Firebase ID token")
        decoded_token = auth.verify_id_token(token)
        logger.info(f"Successfully decoded token with UID: {decoded_token.get('uid')}")
        return decoded_token
    except Exception as e:
        logger.exception(f"Detailed error verifying Firebase ID token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}"
        )

# WebSocket endpoint for real-time notifications
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    db: Session = Depends(get_db)
):
    try:
        # Check if user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await websocket.close(code=1000)
            return
        
        await manager.connect(websocket, user_id)
        
        try:
            while True:
                # Keep connection alive
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        for user_id in manager.active_connections:
            manager.disconnect(websocket, user_id)

@app.on_event("startup")
async def startup_event():
    global firebase_app
    if settings.environment == "production":
        try:
            # Import Firebase credentials
            from firebase_admin import credentials as fb_credentials
            
            # Create a credential object
            cred = fb_credentials.ApplicationDefault()
            
            # Initialize Firebase with explicit credentials
            firebase_app = initialize_app(
                credential=cred,
                options={
                    'projectId': 'genia-ai-19a34'
                }
            )
            logger.info("Firebase initialized successfully")
        except Exception as e:
            logger.exception(f"Error initializing Firebase")
            raise e
    else:
        logger.info("Running in development mode - skipping Firebase initialization")
