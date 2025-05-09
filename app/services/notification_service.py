import logging
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.notifications import Notification
from app.schemas.notifications import NotificationStatusUpdate

logger = logging.getLogger(__name__)

async def get_notifications(request: NotificationStatusUpdate, db: AsyncSession, current_user: dict):
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user['uid'],
            Notification.is_read == False
        )
    )
    return result.scalars().all()


async def update_notification_status(request: NotificationStatusUpdate, db: AsyncSession, current_user: dict):
    stmt = (
        update(Notification)
        .where(Notification.user_id == current_user['uid'], Notification.id.in_(request.ids))
        .values(is_read=request.is_read)
        .execution_options(synchronize_session="fetch")
    )
    await db.execute(stmt)
    await db.commit()
    return {"updated_ids": request.ids, "is_read": request.is_read}