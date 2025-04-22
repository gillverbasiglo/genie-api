import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

from ...init_db import get_db
from ...common import get_current_user
from app.models import User, FriendRequest, Friend, UserBlock
from ...schemas.friends import (
    FriendRequestCreate,
    FriendRequestResponse,
    FriendRequestUpdate,
    FriendResponse,
    FriendStatusResponse,
    UserBlockCreate,
    UserBlockResponse,
    UserReportCreate,
    UserReportResponse,
    FriendRequestStatus
)

router = APIRouter(prefix="/friends", tags=["friends"])

# Configure logging
logger = logging.getLogger(__name__)

@router.post("/request", response_model=FriendRequestResponse)
async def send_friend_request(
    request: FriendRequestCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Send a friend request to another user
    """
    # Check if target user exists
    target_user = db.execute(select(User).where(User.id == request.to_user_id)).scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if users are already friends
    existing_friend = db.execute(
        select(Friend).where(
            or_(
                and_(Friend.user_id == current_user['uid'], Friend.friend_id == request.to_user_id),
                and_(Friend.user_id == request.to_user_id, Friend.friend_id == current_user['uid'])
            )
        )
    ).scalar_one_or_none()
    if existing_friend:
        raise HTTPException(status_code=400, detail="Users are already friends")

    # Check for existing friend request
    existing_request = db.execute(
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
    ).scalar_one_or_none()
    if existing_request:
        raise HTTPException(status_code=400, detail="Friend request already exists")

    # Check if either user has blocked the other
    block_exists = db.execute(
        select(UserBlock).where(
            or_(
                and_(UserBlock.blocker_id == current_user['uid'], UserBlock.blocked_id == request.to_user_id),
                and_(UserBlock.blocker_id == request.to_user_id, UserBlock.blocked_id == current_user['uid'])
            )
        )
    ).scalar_one_or_none()
    if block_exists:
        raise HTTPException(status_code=400, detail="Cannot send friend request to blocked user")

    # Create new friend request
    friend_request = FriendRequest(
        from_user_id=current_user['uid'],
        to_user_id=request.to_user_id,
        status=FriendRequestStatus.PENDING
    )
    db.add(friend_request)
    db.commit()
    db.refresh(friend_request)

    return friend_request

@router.get("/requests", response_model=List[FriendRequestResponse])
async def get_friend_requests(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all friend requests (sent and received)
    """
    requests = db.execute(
        select(FriendRequest).where(
            or_(
                FriendRequest.from_user_id == current_user['uid'],
                FriendRequest.to_user_id == current_user['uid']
            )
        )
    ).scalars().all()
    return requests

@router.patch("/request/{request_id}", response_model=FriendRequestResponse)
async def update_friend_request(
    request_id: str,
    update: FriendRequestUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Update a friend request status (accept/reject/cancel)
    """
    friend_request = db.execute(
        select(FriendRequest).where(
            FriendRequest.id == request_id,
            FriendRequest.to_user_id == current_user['uid']
        )
    ).scalar_one_or_none()

    if not friend_request:
        raise HTTPException(status_code=404, detail="Friend request not found")

    if friend_request.status != FriendRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Friend request is not pending")

    friend_request.status = update.status
    db.commit()
    db.refresh(friend_request)

    # If request is accepted, create friend relationship
    if update.status == FriendRequestStatus.ACCEPTED:
        # Create bidirectional friendship
        friendship1 = Friend(user_id=friend_request.from_user_id, friend_id=friend_request.to_user_id)
        friendship2 = Friend(user_id=friend_request.to_user_id, friend_id=friend_request.from_user_id)
        db.add_all([friendship1, friendship2])
        db.commit()

    return friend_request

@router.get("/status/{user_id}", response_model=FriendStatusResponse)
async def get_friend_status(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get the friendship status between current user and another user
    """
    # Check if users are friends
    is_friend = db.execute(
        select(Friend).where(
            or_(
                and_(Friend.user_id == current_user['uid'], Friend.friend_id == user_id),
                and_(Friend.user_id == user_id, Friend.friend_id == current_user['uid'])
            )
        )
    ).scalar_one_or_none() is not None

    # Check for pending friend request
    friend_request = db.execute(
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
    ).scalar_one_or_none()

    # Check if either user has blocked the other
    is_blocked = db.execute(
        select(UserBlock).where(
            UserBlock.blocker_id == current_user['uid'],
            UserBlock.blocked_id == user_id
        )
    ).scalar_one_or_none() is not None

    is_blocked_by = db.execute(
        select(UserBlock).where(
            UserBlock.blocker_id == user_id,
            UserBlock.blocked_id == current_user['uid']
        )
    ).scalar_one_or_none() is not None

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
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Block a user
    """
    # Check if target user exists
    target_user = db.execute(select(User).where(User.id == block.blocked_id)).scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already blocked
    existing_block = db.execute(
        select(UserBlock).where(
            UserBlock.blocker_id == current_user['uid'],
            UserBlock.blocked_id == block.blocked_id
        )
    ).scalar_one_or_none()
    if existing_block:
        raise HTTPException(status_code=400, detail="User is already blocked")

    # Create block
    user_block = UserBlock(
        blocker_id=current_user['uid'],
        blocked_id=block.blocked_id,
        reason=block.reason
    )
    db.add(user_block)

    # Remove any existing friend relationships
    db.execute(
        select(Friend).where(
            or_(
                and_(Friend.user_id == current_user['uid'], Friend.friend_id == block.blocked_id),
                and_(Friend.user_id == block.blocked_id, Friend.friend_id == current_user['uid'])
            )
        )
    ).scalars().all()

    # Cancel any pending friend requests
    db.execute(
        select(FriendRequest).where(
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
    ).scalars().all()

    db.commit()
    db.refresh(user_block)

    return user_block

@router.delete("/block/{user_id}")
async def unblock_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Unblock a user
    """
    block = db.execute(
        select(UserBlock).where(
            UserBlock.blocker_id == current_user['uid'],
            UserBlock.blocked_id == user_id
        )
    ).scalar_one_or_none()

    if not block:
        raise HTTPException(status_code=404, detail="User is not blocked")

    db.delete(block)
    db.commit()

    return {"message": "User unblocked successfully"}

@router.post("/report", response_model=UserReportResponse)
async def report_user(
    report: UserReportCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Report a user
    """
    # Check if target user exists
    target_user = db.execute(select(User).where(User.id == report.reported_id)).scalar_one_or_none()
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
    db.commit()
    db.refresh(user_report)

    return user_report

@router.get("/list", response_model=List[FriendResponse])
async def get_friends(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get list of all friends
    """
    friends = db.execute(
        select(Friend).where(Friend.user_id == current_user['uid'])
    ).scalars().all()
    return friends

@router.delete("/{friend_id}")
async def remove_friend(
    friend_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Remove a friend
    """
    # Remove bidirectional friendship
    db.execute(
        select(Friend).where(
            or_(
                and_(Friend.user_id == current_user['uid'], Friend.friend_id == friend_id),
                and_(Friend.user_id == friend_id, Friend.friend_id == current_user['uid'])
            )
        )
    ).scalars().all()

    db.commit()

    return {"message": "Friend removed successfully"}
