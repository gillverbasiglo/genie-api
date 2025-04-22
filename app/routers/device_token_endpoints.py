import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from ..init_db import get_db
from app.models import DeviceToken
from ..schemas.device_token import DeviceTokenCreate, DeviceTokenResponse
from ..common import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/device-tokens", tags=["device-tokens"])

@router.post("/register", response_model=DeviceTokenResponse)
async def register_device_token(
    device_token_data: DeviceTokenCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new device token for push notifications
    """
    try:
        # Check if token already exists for this user
        stmt = select(DeviceToken).where(
            DeviceToken.user_id == current_user["uid"],
            DeviceToken.token == device_token_data.token
        )
        existing_token = db.execute(stmt).scalar_one_or_none()
        if existing_token:
            # Update existing token if it was deactivated
            if not existing_token.is_active:
                existing_token.is_active = True
                db.commit()
                db.refresh(existing_token)
            return existing_token
        
        # Create new device token
        new_token = DeviceToken(
            user_id=current_user["uid"],
            token=device_token_data.token,
            platform=device_token_data.platform
        )
        
        db.add(new_token)
        db.commit()
        db.refresh(new_token)
        
        return new_token
        
    except Exception as e:
        logger.error(f"Error registering device token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register device token"
        )

@router.post("/unregister")
async def unregister_device_token(
    token: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Unregister a device token (mark as inactive)
    """
    try:
        stmt = select(DeviceToken).where(
            DeviceToken.user_id == current_user["uid"],
            DeviceToken.token == token
        )
        device_token = await db.execute(stmt).scalar_one_or_none()
        
        if not device_token:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device token not found"
            )
        
        device_token.is_active = False
        db.commit()
        
        return {"message": "Device token unregistered successfully"}
        
    except Exception as e:
        logger.error(f"Error unregistering device token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unregister device token"
        )
    