import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import initialize_app, credentials, auth
from sqlalchemy import inspect

from app.config import settings
from app.database import engine, Base
from app.models.User import User
from app.models.Invitation import Invitation

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    firebase_app = None
    
    # Initialize Database Tables
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    if not all(table in existing_tables for table in ['users', 'invitations']):
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully!")
    else:
        logger.info("Database tables already exist")

    # Initialize Firebase (existing code)
    if settings.environment == "production":
        try:
            cred = credentials.ApplicationDefault()
            firebase_app = initialize_app(
                credential=cred,
                options={
                    'projectId': 'genia-ai-19a34'
                }
            )
            logger.info("Firebase initialized successfully")
        except Exception as e:
            logger.exception(f"Error initializing Firebase: {e}")
            raise e
    else:
        logger.info("Running in development mode - skipping Firebase initialization")
    
    yield
    
    # Shutdown
    if firebase_app is not None:
        firebase_app.delete()
        logger.info("Firebase app deleted successfully")

app = FastAPI(lifespan=lifespan)
security = HTTPBearer()

# Dependency to get current user from token
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    if settings.environment != "production":
        logger.info("Development mode - skipping token verification")
        return {
            "uid": "dev-user-123",
            "email": "dev@example.com",
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
