import logging

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import initialize_app, credentials, auth

from app.config import settings

app = FastAPI()
security = HTTPBearer()
# Initialize Firebase
firebase_app = None

logger = logging.getLogger(__name__)

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