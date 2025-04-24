import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete
from app.common import manager
from ...init_db import get_db
from ...common import get_current_user
from app.models import User, FriendRequest, Friend, UserBlock, UserReport
from ...schemas.websocket import FriendRequestAcceptedMessage, WebSocketMessageType
from ...schemas.friends import (
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
    FriendRequestStatus,
    FriendRequestType,
    FriendRequestResponse
)
import json

router = APIRouter(prefix="/friends", tags=["friends"])

# Configure logging
logger = logging.getLogger(__name__)

@router.post("/request", response_model=FriendRequestResponse)
async def send_friend_request(
    request: FriendRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Send a friend request to another user
    """

    if current_user["uid"] == request.to_user_id:
        raise HTTPException(status_code=400, detail="I know you're awesome but you can't be friend with yourself.")
    
    # Check if target user exists
    results = await db.execute(select(User).where(User.id == request.to_user_id))
    target_user = results.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if users are already friends
    stmt = select(Friend).where(
        or_(
            and_(Friend.user_id == current_user['uid'], Friend.friend_id == request.to_user_id),
            and_(Friend.user_id == request.to_user_id, Friend.friend_id == current_user['uid'])
        )
    )
    results = await db.execute(stmt)
    existing_friend = results.scalars().all()

    if existing_friend:
        raise HTTPException(status_code=400, detail="Users are already friends")

    # Check for existing friend request
    results = await db.execute(
        select(FriendRequest).where(
            or_(
                and_(
                    FriendRequest.from_user_id == current_user['uid'],
                    FriendRequest.to_user_id == request.to_user_id,
                    FriendRequest.status == FriendRequestStatus.PENDING
                ),
                and_(
                    FriendRequest.from_user_id == request.to_user_id,
                    FriendRequest.to_user_id == current_user['uid'],
                    FriendRequest.status == FriendRequestStatus.PENDING
                )
            )
        )
    )
    existing_request = results.scalar_one_or_none()
    
    if existing_request:
        raise HTTPException(status_code=400, detail="Friend request already exists")

    # Check if either user has blocked the other
    block_exists = await db.execute(
        select(UserBlock).where(
            or_(
                and_(UserBlock.blocker_id == current_user['uid'], UserBlock.blocked_id == request.to_user_id),
                and_(UserBlock.blocker_id == request.to_user_id, UserBlock.blocked_id == current_user['uid'])
            )
        )
    )
    block_exists = block_exists.scalar_one_or_none()
    if block_exists:
        raise HTTPException(status_code=400, detail="Cannot send friend request to blocked user")

    # Create new friend request
    friend_request = FriendRequest(
        from_user_id=current_user['uid'],
        to_user_id=request.to_user_id,
        status=FriendRequestStatus.PENDING
    )
    db.add(friend_request)
    await db.commit()
    await db.refresh(friend_request)

    # ✅ Send WebSocket notification if the user is connected
    try:
        notification = {
            "type": WebSocketMessageType.FRIEND_REQUEST,
            "message": f"{current_user['uid']} sent you a friend request.",
            "from_user_id": current_user['uid'],
            "to_user_id": request.to_user_id
        }
        await manager.send_notification(request.to_user_id, json.dumps(notification))
    except Exception as e:
        # Log it or silently continue
        logger.warning(f"Failed to send WebSocket notification: {e}")

    return friend_request

@router.get("/requests", response_model=List[GetFriendsRequestResponse])
async def get_friend_requests(
    request_type: FriendRequestType = FriendRequestType.ALL,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get friend requests with filtering options
    
    Parameters:
    - status: Filter by request status (default: PENDING)
    - request_type: Filter by request type: 
        'sent' - requests you sent
        'received' - requests you received
        'all' - both sent and received (default)
    """
    
    query = select(FriendRequest).options(
        joinedload(FriendRequest.from_user),
        joinedload(FriendRequest.to_user)
    )
    
    # Build conditions based on request_type
    user_conditions = []
    
    if request_type in [FriendRequestType.RECEIVED, FriendRequestType.ALL]:
        user_conditions.append(FriendRequest.to_user_id == current_user['uid'])
        
    if request_type in [FriendRequestType.SENT, FriendRequestType.ALL]:
        user_conditions.append(FriendRequest.from_user_id == current_user['uid'])
    
    # Combine conditions with OR if needed
    if len(user_conditions) > 1:
        user_condition = or_(*user_conditions)
    elif user_conditions:
        user_condition = user_conditions[0]
    else:
        user_condition = None
    
    # Final query with status filter
    if user_condition is not None:
        query = query.where(
            and_(
                user_condition,
                FriendRequest.status != FriendRequestStatus.CANCELLED
            )
        )
    else:
        query = query.where(and_(FriendRequest.status != FriendRequestStatus.CANCELLED))
    
    results = await db.execute(query)
    requests = results.scalars().unique().all()
    return requests

@router.patch("/request/{request_id}", response_model=FriendRequestResponse)
async def update_friend_request(
    request_id: str,
    update: FriendRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Update a friend request status (accept/reject/cancel)
    """

    result = await db.execute(
        select(FriendRequest).where(FriendRequest.id == request_id)
    )
    friend_request = result.scalar_one_or_none()

    if not friend_request:
        raise HTTPException(status_code=404, detail="Friend request not found")

    if friend_request.status != FriendRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Friend request is not pending")

    # Authorization checks
    if update.status == FriendRequestStatus.CANCELLED and friend_request.from_user_id != current_user['uid']:
        raise HTTPException(status_code=403, detail="Only the sender can cancel the request")

    if update.status in [FriendRequestStatus.ACCEPTED, FriendRequestStatus.REJECTED] and friend_request.to_user_id != current_user['uid']:
        raise HTTPException(status_code=403, detail="Only the recipient can accept or reject the request")

    friend_request.status = update.status
    await db.commit()
    await db.refresh(friend_request)

    # If request is accepted, create friend relationship
    if update.status == FriendRequestStatus.ACCEPTED:
        # Check if friendship already exists
        existing = await db.execute(
            select(Friend).where(
                (Friend.user_id == friend_request.from_user_id) &
                (Friend.friend_id == friend_request.to_user_id)
            )
        )
        if not existing.scalar():
            friendship1 = Friend(user_id=friend_request.from_user_id, friend_id=friend_request.to_user_id)
            friendship2 = Friend(user_id=friend_request.to_user_id, friend_id=friend_request.from_user_id)
            db.add_all([friendship1, friendship2])
            await db.commit()
        await db.refresh(friend_request)

    # ✅ Send WebSocket notification on ACCEPTED or REJECTED
    if update.status in [FriendRequestStatus.ACCEPTED, FriendRequestStatus.REJECTED]:
        print("sending ...")
        try:
            notification = {
                "type": WebSocketMessageType.FRIEND_REQUEST_ACCEPTED if update.status == FriendRequestStatus.ACCEPTED else WebSocketMessageType.FRIEND_REQUEST_REJECTED,
                "message": f"{current_user['name']} accepted your friend request." if update.status == FriendRequestStatus.ACCEPTED else f"{current_user['name']} rejected your friend request.",
                "from_user_id": current_user['uid'],
                "to_user_id": friend_request.from_user_id
            }
            await manager.send_notification(friend_request.from_user_id, json.dumps(notification))
        except Exception as e:
            logger.warning(f"Failed to send WebSocket notification: {e}")
    
    response_data = {
        "id": friend_request.id,
        "from_user_id": friend_request.from_user_id,
        "to_user_id": friend_request.to_user_id,
        "status": friend_request.status,
        "created_at": friend_request.created_at,
        "updated_at": friend_request.updated_at
    }

    return response_data
    
@router.get("/status/{user_id}", response_model=FriendStatusResponse)
async def get_friend_status(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get the friendship status between current user and another user
    """
    # Check if users are friends
    results = await db.execute(
        select(Friend).where(
            or_(
                and_(Friend.user_id == current_user['uid'], Friend.friend_id == user_id),
                and_(Friend.user_id == user_id, Friend.friend_id == current_user['uid'])
            )
        )
    )
    is_friend = results.scalars().first() is not None

    # Check for pending friend request
    results = await db.execute(
        select(FriendRequest).where(
            or_(
                and_(
                    FriendRequest.from_user_id == current_user['uid'],
                    FriendRequest.to_user_id == user_id,
                    FriendRequest.status == FriendRequestStatus.PENDING
                ),
                and_(
                    FriendRequest.from_user_id == user_id,
                    FriendRequest.to_user_id == current_user['uid'],
                    FriendRequest.status == FriendRequestStatus.PENDING
                )
            )
        )
    )
    friend_request = results.scalar_one_or_none()

    # Check if either user has blocked the other
    results = await db.execute(
        select(UserBlock).where(
            UserBlock.blocker_id == current_user['uid'],
            UserBlock.blocked_id == user_id
        )
    )
    is_blocked = results.scalar_one_or_none() is not None

    results = await db.execute(
        select(UserBlock).where(
            UserBlock.blocker_id == user_id,
            UserBlock.blocked_id == current_user['uid']
        )
    )
    is_blocked_by = results.scalar_one_or_none() is not None

    return FriendStatusResponse(
        is_friend=is_friend,
        friend_request_status=friend_request.status if friend_request else None,
        is_blocked=is_blocked,
        is_blocked_by=is_blocked_by,
        friend_request_id=friend_request.id if friend_request else None
    )

@router.post("/block", response_model=UserBlockResponse)
async def block_user(
    block: UserBlockCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Block a user
    """
    if current_user['uid'] == block.blocked_id:
        raise HTTPException(status_code=400, detail="You can't block yourself")

    # Check if target user exists
    target_user = await db.execute(select(User).where(User.id == block.blocked_id))
    target_user = target_user.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already blocked
    existing_block = await db.execute(
        select(UserBlock).where(
            UserBlock.blocker_id == current_user['uid'],
            UserBlock.blocked_id == block.blocked_id
        )
    )
    existing_block = existing_block.scalar_one_or_none()
    
    if existing_block:
        raise HTTPException(status_code=400, detail="User is already blocked")

    # Create block
    user_block = UserBlock(
        blocker_id=current_user['uid'],
        blocked_id=block.blocked_id,
        reason=block.reason
    )

    # Remove any existing friend relationships
    await db.execute(
        delete(Friend).where(
            or_(
                and_(Friend.user_id == current_user['uid'], Friend.friend_id == block.blocked_id),
                and_(Friend.user_id == block.blocked_id, Friend.friend_id == current_user['uid'])
            )
        )
    )

    # Cancel any pending friend requests
    await db.execute(
        delete(FriendRequest).where(
            or_(
                and_(
                    FriendRequest.from_user_id == current_user['uid'],
                    FriendRequest.to_user_id == block.blocked_id,
                    FriendRequest.status == FriendRequestStatus.PENDING
                ),
                and_(
                    FriendRequest.from_user_id == block.blocked_id,
                    FriendRequest.to_user_id == current_user['uid'],
                    FriendRequest.status == FriendRequestStatus.PENDING
                )
            )
        )
    )

    db.add(user_block)
    await db.commit()
    await db.refresh(user_block)

    return user_block

@router.delete("/unblock/{user_id}")
async def unblock_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Unblock a user
    """
    block = await db.execute(
        select(UserBlock).where(
            UserBlock.blocker_id == current_user['uid'],
            UserBlock.blocked_id == user_id
        )
    )
    block = block.scalar_one_or_none()

    if not block:
        raise HTTPException(status_code=404, detail="User is not blocked")

    await db.delete(block)
    await db.commit()

    return {"message": "User unblocked successfully"}

@router.post("/report", response_model=UserReportResponse)
async def report_user(
    report: UserReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Report a user
    """
    # Check if target user exists
    target_user = await db.execute(select(User).where(User.id == report.reported_id))
    target_user = target_user.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Create report
    user_report = UserReport(
        reporter_id=current_user['uid'],
        reported_id=report.reported_id,
        report_type=report.report_type,
        description=report.description
    )
    db.add(user_report)
    await db.commit()
    await db.refresh(user_report)

    return user_report

@router.get("/list", response_model=List[FriendResponse])
async def get_friends(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get list of all friends
    """
    friends = await db.execute(
        select(Friend)
        .options(joinedload(Friend.friend))
        .where(Friend.user_id == current_user['uid'])
    )
    friends = friends.scalars().all()
    return friends

@router.delete("/{friend_id}")
async def remove_friend(
    friend_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Remove a friend (bidirectional). Returns 404 if friendship doesn't exist.
    """
    uid = current_user['uid']

    # Check if the friendship exists (in either direction)
    result = await db.execute(
        select(Friend).where(
            or_(
                and_(Friend.user_id == uid, Friend.friend_id == friend_id),
                and_(Friend.user_id == friend_id, Friend.friend_id == uid)
            )
        )
    )
    existing_friendship = result.scalars().first()

    if not existing_friendship:
        raise HTTPException(status_code=404, detail="Friendship not found")

    # Delete both directions
    await db.execute(
        delete(Friend).where(
            or_(
                and_(Friend.user_id == uid, Friend.friend_id == friend_id),
                and_(Friend.user_id == friend_id, Friend.friend_id == uid)
            )
        )
    )

    await db.commit()

    return {"message": "Friend removed successfully"}


@router.get("/blocked/list", response_model=List[BlockListResponse])
async def get_blocked_users(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get a list of users that the current user has blocked.
    """
    uid = current_user['uid']

    result = await db.execute(
        select(UserBlock).where(UserBlock.blocker_id == current_user['uid'])
    )
    return result.scalars().all()
