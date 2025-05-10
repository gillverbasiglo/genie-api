import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.common import manager
from app.init_db import get_db
from app.common import get_current_user
from app.schemas.friends import (
    BlockListResponse,
    FriendRequestCreate,
    GetFriendsRequestResponse,
    FriendRequestUpdate,
    FriendResponse,
    FriendStatusResponse,
    UserBlockCreate,
    UserBlockResponse,
    UserReportCreate,
    UserReportResponse,
    FriendRequestType,
    FriendRequestResponse
)
from app.services.friends_service import get_blocked_users, get_friend_requests, get_friend_status, get_friends, report_user, send_friend_request, unblock_user, update_friend_request_status, remove_friend

router = APIRouter(prefix="/friends", tags=["friends"])

# Configure logging
logger = logging.getLogger(__name__)

@router.post("/request", response_model=FriendRequestResponse)
async def send_friend_request_api(
    request: FriendRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        return await send_friend_request(request, db, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/requests", response_model=List[GetFriendsRequestResponse])
async def get_friend_requests_api(
    request_type: FriendRequestType = FriendRequestType.ALL,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        return await get_friend_requests(request_type, db, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/request/{request_id}", response_model=FriendRequestResponse)
async def update_friend_request_status_api(
    request_id: str,
    update: FriendRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        return await update_friend_request_status(request_id, update, db, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating friend request: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while updating the friend request")
    
    
@router.get("/status/{user_id}", response_model=FriendStatusResponse)
async def get_friend_status_api(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        return await get_friend_status(user_id, db, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/block", response_model=UserBlockResponse)
async def block_user(
    block: UserBlockCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        return await get_friend_status(block, db, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    

@router.delete("/unblock/{user_id}")
async def unblock_user_api(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        return await unblock_user(user_id, db, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/report", response_model=UserReportResponse)
async def report_user_api(
    report: UserReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        return await report_user(report, db, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list", response_model=List[FriendResponse])
async def get_friends_api(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        return await get_friends(db, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.delete("/{friend_id}")
async def remove_friend_api(
    friend_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        return await remove_friend(friend_id, db, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocked/list", response_model=List[BlockListResponse])
async def get_blocked_users_api(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        return await get_blocked_users(db, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
