import logging
from typing import Dict
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.init_db import get_db
from app.schemas.device_token import DeviceTokenCreate, DeviceTokenResponse
from app.common import get_current_user
from app.services.device_token_service import get_device_token, register_device_token, unregister_device_token

# Configure logger for this module
logger = logging.getLogger(__name__)

# Router for device token management endpoints
router = APIRouter(prefix="/device-tokens", tags=["device-tokens"])

@router.post("/register", response_model=DeviceTokenResponse)
async def register_device_token_api(
    device_token_data: DeviceTokenCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new device token for push notifications.
    
    Args:
        device_token_data: The device token information to register
        current_user: The authenticated user making the request
        db: Database session
    
    Returns:
        DeviceTokenResponse: The registered device token information
    """
    result = await register_device_token(db, current_user, device_token_data)
    return result

@router.post("/unregister")
async def unregister_device_token_api(
    token: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Unregister a device token to stop receiving push notifications.
    
    Args:
        token: The device token to unregister
        current_user: The authenticated user making the request
        db: Database session
    
    Returns:
        dict: Result of the unregistration operation
    """
    result = await unregister_device_token(db, current_user, token)
    return result

@router.get("/get_by_user_id")
async def get_device_token_api(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a device token for push notifications.
    
    Args:
        user_id: The user id to get the device token for
        db: Database session
    
    Returns:
        DeviceTokenResponse: The registered device token information
    """
    result = await get_device_token(db, user_id)
    return result

    
    