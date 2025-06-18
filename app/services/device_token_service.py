import logging
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.device_token import DeviceToken
from app.schemas.device_token import DeviceTokenCreate

# Configure logger for this module
logger = logging.getLogger(__name__)

async def register_device_token(
    db: AsyncSession,
    current_user: dict,
    device_token_data: DeviceTokenCreate
):
    """
    Register a new device token for push notifications or reactivate an existing one.
    
    Args:
        db (AsyncSession): Database session
        current_user (dict): Current authenticated user information
        device_token_data (DeviceTokenCreate): Device token data including token and platform
        
    Returns:
        DeviceToken: The registered or reactivated device token
        
    Raises:
        HTTPException: If there's an error during registration
    """
    try:
        # Check if token already exists for this user
        stmt = select(DeviceToken).where(
            DeviceToken.user_id == current_user["uid"],
            DeviceToken.token == device_token_data.token
        )
        existing_token = await db.execute(stmt)
        existing_token = existing_token.scalar_one_or_none()
        
        # If token exists and was deactivated, reactivate it
        if existing_token:
            if not existing_token.is_active:
                existing_token.is_active = True
                await db.commit()
                await db.refresh(existing_token)
            return existing_token
        
        # Create new device token if it doesn't exist
        new_token = DeviceToken(
            user_id=current_user["uid"],
            token=device_token_data.token,
            platform=device_token_data.platform
        )
        
        db.add(new_token)
        await db.commit()
        await db.refresh(new_token)
        
        return new_token
        
    except Exception as e:
        logger.error(f"Error registering device token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register device token"
        )
    

async def unregister_device_token(
    db: AsyncSession,
    current_user: dict,
    token: str
):
    """
    Deactivate a device token for push notifications.
    
    Args:
        db (AsyncSession): Database session
        current_user (dict): Current authenticated user information
        token (str): The device token to unregister
        
    Returns:
        dict: Success message
        
    Raises:
        HTTPException: If token not found or error during unregistration
    """
    try:
        # Find the device token for the current user
        stmt = select(DeviceToken).where(
            DeviceToken.user_id == current_user["uid"],
            DeviceToken.token == token
        )
        device_token = await db.execute(stmt).scalar_one_or_none()
        
        # Raise 404 if token not found
        if not device_token:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device token not found"
            )
        
        # Soft delete by setting is_active to False
        device_token.is_active = False
        await db.commit()
        
        return {"message": "Device token unregistered successfully"}
        
    except Exception as e:
        logger.error(f"Error unregistering device token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unregister device token"
        )
    
async def get_device_token(
    db: AsyncSession,
    user_id: str
):
    logger.info(f"Getting device token for user: {user_id}")
    """
    Get a device token for push notifications.
    
    Args:
        db (AsyncSession): Database session
        user_id (str): The user id to get the device token for
        
    Returns:    
        DeviceToken: The registered or reactivated device token
        
    Raises:
        HTTPException: If there's an error during registration
    """
    try:
        # Check if token already exists for this user
        stmt = select(DeviceToken).where(
            DeviceToken.user_id == user_id,
            DeviceToken.is_active == True
        )
        token = await db.execute(stmt)
        token = token.scalars().all()
        
        logger.info(f"Token: {token}")
        return token
        
    except Exception as e:
        logger.error(f"Error getting device token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get device token"
        )
    
