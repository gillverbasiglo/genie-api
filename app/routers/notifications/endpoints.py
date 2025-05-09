import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.init_db import get_db
from app.common import get_current_user
from app.schemas.notifications import NotificationResponse, NotificationStatusUpdate
from app.services.notification_service import get_notifications, update_notification_status

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("/list", response_model=List[NotificationResponse])
async def get_notifications_api(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        return await get_notifications(request, db, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.post("/update_status", response_model=dict)
async def update_notification_status_api(
    request: NotificationStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        return await update_notification_status(request, db, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))