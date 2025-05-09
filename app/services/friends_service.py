import logging
import json
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete
from sqlalchemy.orm import joinedload
from app.models import User, FriendRequest, Friend, UserBlock, UserReport
from app.models.notifications import Notification
from app.schemas.friends import FriendRequestCreate, FriendRequestType, FriendRequestUpdate, FriendRequestStatus
from app.schemas.friends import FriendStatusResponse, UserBlockCreate, UserReportCreate
from app.schemas.notifications import NotificationType
from app.schemas.websocket import WebSocketMessageType
from app.core.websocket.websocket_manager import manager

logger = logging.getLogger(__name__)

async def send_friend_request(
    request: FriendRequestCreate, db: AsyncSession, current_user: dict
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

    # Save in notification table
    notification = Notification(
        user_id=request.to_user_id,
        type=NotificationType.FRIEND_REQUEST,
        title="New friend request.",
        message=f"{current_user['uid']} sent you a friend request."
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

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

async def get_friend_requests(
    request_type: FriendRequestType, db: AsyncSession, current_user: dict
):
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

async def update_friend_request_status(
    request_id: str, update: FriendRequestUpdate, db: AsyncSession, current_user: dict
):
    # Fetch friend request
    result = await db.execute(
        select(FriendRequest).where(
            FriendRequest.id == request_id
            )
    )
    friend_request = result.scalar_one_or_none()

    # Check if friend request exists    
    if not friend_request:
        raise HTTPException(status_code=404, detail="Friend request not found")

    # Check if friend request is pending
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



    # Save in notification table
    if update.status in [FriendRequestStatus.ACCEPTED]:
        notification = Notification(
            user_id=friend_request.from_user_id,
            type=NotificationType.FRIEND_REQUEST,
            title="Friend request accepted.",
            message=f"{current_user['uid']} accepted your friend request."
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)

    # ✅ Send WebSocket notification on ACCEPTED or REJECTED
    if update.status in [FriendRequestStatus.ACCEPTED, FriendRequestStatus.REJECTED, FriendRequestStatus.CANCELLED]:
        try:
            if update.status == FriendRequestStatus.ACCEPTED:
                notification = {
                    "type": WebSocketMessageType.FRIEND_REQUEST_ACCEPTED,
                    "message": f"{current_user['name']} accepted your friend request.",
                    "from_user_id": current_user['uid'],
                    "to_user_id": friend_request.from_user_id
                }
            elif update.status == FriendRequestStatus.REJECTED:
                notification = {
                    "type": WebSocketMessageType.FRIEND_REQUEST_REJECTED,
                    "message": f"{current_user['name']} rejected your friend request.",
                    "from_user_id": current_user['uid'],
                    "to_user_id": friend_request.from_user_id
                }
            elif update.status == FriendRequestStatus.CANCELLED:
                notification = {
                    "type": WebSocketMessageType.FRIEND_REQUEST_CANCELLED,
                    "message": f"{current_user['name']} cancelled the friend request.",
                    "from_user_id": current_user['uid'],
                    "to_user_id": friend_request.from_user_id
                }
            else:
                return  # Ignore any other status
            
            # Send the notification to the 'from_user_id' of the friend request
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


async def get_friend_status(
    user_id: str, db: AsyncSession, current_user: dict
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


async def block_user(
    block: UserBlockCreate, db: AsyncSession, current_user: dict
):
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


async def unblock_user(
    user_id: str, db: AsyncSession, current_user: dict
):
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


async def report_user(
    report: UserReportCreate, db: AsyncSession, current_user: dict
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


async def get_friends(
    db: AsyncSession, current_user: dict
):
    friends = await db.execute(
        select(Friend)
        .options(joinedload(Friend.friend))
        .where(Friend.user_id == current_user['uid'])
    )
    friends = friends.scalars().all()
    return friends



async def remove_friend(
    friend_id: str, db: AsyncSession, current_user: dict
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


async def get_blocked_users(
    db: AsyncSession, current_user: dict
):
    """
    Get a list of users that the current user has blocked.
    """
    uid = current_user['uid']

    result = await db.execute(
        select(UserBlock).where(UserBlock.blocker_id == current_user['uid'])
    )
    return result.scalars().all()


async def are_friends(db: AsyncSession, user1_id: str, user2_id: str) -> bool:
    """
    Check if user1 and user2 are friends. Since friendships are stored bidirectionally,
    check both directions.
    """
    stmt = select(Friend).where(
        (Friend.user_id == user1_id) & (Friend.friend_id == user2_id)
    )
    
    result = await db.execute(stmt)
    friendship = result.scalar_one_or_none()

    return friendship is not None


