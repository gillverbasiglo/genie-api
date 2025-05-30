import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import initialize_app, auth
from typing import Dict, List
import asyncio
from app.config import settings
from .init_db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from .models.user import User
from sqlalchemy.future import select
from app.core.websocket.websocket_manager import manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
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
    
    yield
    
    # Shutdown
    if firebase_app:
        firebase_app.delete()

app = FastAPI(lifespan=lifespan)
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

# Dependency to get current user from token
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):

    if settings.environment != "production":
        logger.info("Development mode - skipping token verification")
        return {
            "uid": "IhgzLPLZhzUWgerOiVWDdqGE0cm1",
            "email": "dev@example.com",
            "name": "Development User",
            "display_name": "Development User"
        }

    token = credentials.credentials
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
    