import logging
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.notifications import Notification
from app.schemas.notifications import NotificationStatusUpdate

# Configure logging 
logger = logging.getLogger(__name__)

async def get_notifications(request: NotificationStatusUpdate, db: AsyncSession, current_user: dict):
    """
    Retrieve a list of notifications for the current user.
    
    Args:
        request (NotificationStatusUpdate): Request body containing notification update details
        db (AsyncSession): Database session dependency
        current_user (dict): Current authenticated user information
        
    Returns:
        List[NotificationResponse]: List of notifications for the user
        
    Raises:
        HTTPException: If there's an error retrieving notifications                 
    """
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user['uid'],
            Notification.is_read == False
        )
    )
    return result.scalars().all()


async def update_notification_status(request: NotificationStatusUpdate, db: AsyncSession, current_user: dict):
    """
    Update the status of a notification.
    
    Args:
        request (NotificationStatusUpdate): Request body containing notification update details
        db (AsyncSession): Database session dependency
        current_user (dict): Current authenticated user information             

    Returns:
        dict: Response indicating the status of the update operation
        
    Raises:
        HTTPException: If there's an error updating the notification status
    """ 
    stmt = (
        update(Notification)
        .where(Notification.user_id == current_user['uid'], Notification.id.in_(request.ids))
        .values(is_read=request.is_read)
        .execution_options(synchronize_session="fetch")
    )
    await db.execute(stmt)
    await db.commit()
    return {"updated_ids": request.ids, "is_read": request.is_read}