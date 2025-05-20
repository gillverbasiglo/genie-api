import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
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

# Configure logging for this module
logger = logging.getLogger(__name__)

# Initialize router with prefix and tags for API documentation
router = APIRouter(prefix="/friends", tags=["friends"])

@router.post("/request", response_model=FriendRequestResponse)
async def send_friend_request_api(
    request: FriendRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Send a friend request to another user.
    
    Args:
        request: FriendRequestCreate object containing the request details
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        FriendRequestResponse: Details of the created friend request
        
    Raises:
        HTTPException: If the request is invalid or user cannot send friend request
    """
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
    """
    Retrieve friend requests for the current user.
    
    Args:
        request_type: Type of requests to retrieve (ALL, SENT, RECEIVED)
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        List[GetFriendsRequestResponse]: List of friend requests
        
    Raises:
        HTTPException: If there's an error retrieving the requests
    """
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
    """
    Update the status of a friend request (accept/reject).
    
    Args:
        request_id: ID of the friend request to update
        update: FriendRequestUpdate object containing the new status
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        FriendRequestResponse: Updated friend request details
        
    Raises:
        HTTPException: If the request is invalid or user cannot update the request
    """
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
    """
    Get the friendship status between current user and another user.
    
    Args:
        user_id: ID of the user to check status with
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        FriendStatusResponse: Current friendship status
        
    Raises:
        HTTPException: If there's an error retrieving the status
    """
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
    """
    Block another user.
    
    Args:
        block: UserBlockCreate object containing blocking details
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        UserBlockResponse: Details of the created block
        
    Raises:
        HTTPException: If there's an error blocking the user
    """
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
    """
    Unblock a previously blocked user.
    
    Args:
        user_id: ID of the user to unblock
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        Success message if unblocked successfully
        
    Raises:
        HTTPException: If there's an error unblocking the user
    """
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
    """
    Report a user for inappropriate behavior.
    
    Args:
        report: UserReportCreate object containing report details
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        UserReportResponse: Details of the created report
        
    Raises:
        HTTPException: If there's an error creating the report
    """
    try:
        return await report_user(report, db, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list", response_model=List[FriendResponse])
async def get_friends_api(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get the list of all friends for the current user.
    
    Args:
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        List[FriendResponse]: List of all friends
        
    Raises:
        HTTPException: If there's an error retrieving the friends list
    """
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
    """
    Remove a friend from the current user's friend list.
    
    Args:
        friend_id: ID of the friend to remove
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        Success message if friend removed successfully
        
    Raises:
        HTTPException: If there's an error removing the friend
    """
    try:
        return await remove_friend(friend_id, db, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/blocked/list", response_model=List[BlockListResponse])
async def get_blocked_users_api(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get the list of all users blocked by the current user.
    
    Args:
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        List[BlockListResponse]: List of all blocked users
        
    Raises:
        HTTPException: If there's an error retrieving the blocked users list
    """
    try:
        return await get_blocked_users(db, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
