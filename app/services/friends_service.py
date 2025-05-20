import logging
import json
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete
from sqlalchemy.orm import joinedload
from app.models import User, FriendRequest, Friend, UserBlock, UserReport
from app.models.device_token import DeviceToken
from app.models.notifications import Notification
from app.schemas.friends import FriendRequestCreate, FriendRequestType, FriendRequestUpdate, FriendRequestStatus
from app.schemas.friends import FriendStatusResponse, UserBlockCreate, UserReportCreate
from app.schemas.notifications import NotificationResponse, NotificationType
from app.schemas.websocket import WebSocketMessageType
from app.core.websocket.websocket_manager import manager
from app.services.shared_content_service import send_push_notifications

# Configure logging for this module
logger = logging.getLogger(__name__)

async def send_friend_request(
    request: FriendRequestCreate, db: AsyncSession, current_user: dict
):
    """
    Send a friend request to another user.
    
    Args:
        request: FriendRequestCreate object containing the target user ID
        db: AsyncSession for database operations
        current_user: Dictionary containing current user information
        
    Returns:
        FriendRequest: The created friend request object
        
    Raises:
        HTTPException: If users are already friends, request exists, or user is blocked
    """
    # Prevent self-friending
    if current_user["uid"] == request.to_user_id:
        raise HTTPException(status_code=400, detail="I know you're awesome but you can't be friend with yourself.")
    
    # Verify target user exists
    results = await db.execute(select(User).where(User.id == request.to_user_id))
    target_user = results.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prepare target user data for notifications
    target_user_dict = {
        "id": target_user.id,
        "phone_number": target_user.phone_number,
        "email": target_user.email,
        "display_name": target_user.display_name,
        "created_at": target_user.created_at.isoformat() if target_user.created_at else None,
    }

    # Verify sender user exists
    results = await db.execute(select(User).where(User.id == current_user['uid']))
    sender_user = results.scalar_one_or_none()
    if not sender_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prepare sender user data for notifications
    sender_user_dict = {
        "id": sender_user.id,
        "phone_number": sender_user.phone_number,
        "email": sender_user.email,
        "display_name": sender_user.display_name,
        "created_at": sender_user.created_at.isoformat() if sender_user.created_at else None,
        "updated_at": sender_user.updated_at.isoformat() if sender_user.updated_at else None,
    }

    # Check for existing friendship
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

    # Check for existing pending friend request
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

    # Check for existing blocks between users
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

    # Create and save new friend request
    friend_request = FriendRequest(
        from_user_id=current_user['uid'],
        to_user_id=request.to_user_id,
        status=FriendRequestStatus.PENDING
    )
    db.add(friend_request)
    await db.commit()
    await db.refresh(friend_request)

    # Create notification for the recipient
    notification = Notification(
        user_id=request.to_user_id,
        type=NotificationType.FRIEND_REQUEST,
        title="New friend request.",
        message=f"{current_user['uid']} sent you a friend request."
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    # Handle real-time notification delivery
    is_user_online = manager.is_user_online(request.to_user_id)
    logger.info(f"Recipient user online: {is_user_online}")
    
    if is_user_online:
        # Send WebSocket notification for online users
        try:
            notification_data = {
                "id": friend_request.id,
                "type": WebSocketMessageType.FRIEND_REQUEST,
                "message": f"{sender_user_dict['display_name'] or sender_user_dict['id']} sent you a friend request.",
                "from_user": sender_user_dict,
                "to_user": target_user_dict,
                "status": "PENDING",
                "created_at": friend_request.created_at.isoformat() if friend_request.created_at else None,
                "updated_at": friend_request.updated_at.isoformat() if friend_request.updated_at else None,
            }
            await manager.send_notification(request.to_user_id, notification_data)
        except Exception as e:
            logger.warning(f"Failed to send WebSocket notification: {e}")
    else:
        # Send push notification for offline users
        stmt = select(DeviceToken).where(
            DeviceToken.is_active == True,
            DeviceToken.user_id == request.to_user_id,
            DeviceToken.platform == "ios"
        )
        device_tokens_result = await db.execute(stmt)
        device_tokens = device_tokens_result.scalars().all()

        if not device_tokens:
            logger.info(f"No active iOS device tokens found for user {request.to_user_id}")

        try:
            notification_responses = await send_push_notifications(device_tokens, notification)
            logger.info(f"Push notifications sent: {notification_responses} responses")
        except Exception as e:
            logger.exception("Error while sending push notifications.")
        
    return friend_request

async def get_friend_requests(
    request_type: FriendRequestType, db: AsyncSession, current_user: dict
):
    """
    Retrieve friend requests based on the specified type (sent, received, or all).
    
    Args:
        request_type: Type of friend requests to retrieve (SENT, RECEIVED, or ALL)
        db: AsyncSession for database operations
        current_user: Dictionary containing current user information
        
    Returns:
        List[FriendRequest]: List of friend requests matching the criteria
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

async def update_friend_request_status(
    request_id: str, update: FriendRequestUpdate, db: AsyncSession, current_user: dict
):
    """
    Update the status of a friend request (accept, reject, or cancel).
    
    Args:
        request_id: ID of the friend request to update
        update: FriendRequestUpdate object containing the new status
        db: AsyncSession for database operations
        current_user: Dictionary containing current user information
        
    Returns:
        dict: Updated friend request data
        
    Raises:
        HTTPException: If request not found, invalid status, or unauthorized
    """
    # Fetch and validate friend request
    result = await db.execute(
        select(FriendRequest).where(
            FriendRequest.id == request_id
            )
    )
    friend_request = result.scalar_one_or_none()
    
    # Verify target user exists
    results = await db.execute(select(User).where(User.id == friend_request.to_user_id))
    target_user = results.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prepare user data for notifications
    target_user_dict = {
        "id": target_user.id,
        "phone_number": target_user.phone_number,
        "email": target_user.email,
        "display_name": target_user.display_name,
        "created_at": target_user.created_at.isoformat() if target_user.created_at else None,
    }

    # Verify sender user exists
    results = await db.execute(select(User).where(User.id == current_user['uid']))
    sender_user = results.scalar_one_or_none()
    if not sender_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    sender_user_dict = {
        "id": sender_user.id,
        "phone_number": sender_user.phone_number,
        "email": sender_user.email,
        "display_name": sender_user.display_name,
        "created_at": sender_user.created_at.isoformat() if sender_user.created_at else None,
        "updated_at": sender_user.updated_at.isoformat() if sender_user.updated_at else None,
    }

    # Check if users are already friends
    stmt = select(Friend).where(
        or_(
            and_(Friend.user_id == current_user['uid'], Friend.friend_id == friend_request.to_user_id),
            and_(Friend.user_id == friend_request.to_user_id, Friend.friend_id == current_user['uid'])
        )
    )

    # Check if friend request exists    
    if not friend_request:
        raise HTTPException(status_code=404, detail="Friend request not found")
    if friend_request.status != FriendRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Friend request is not pending")

    # Verify user has permission to update request
    if update.status == FriendRequestStatus.CANCELLED and friend_request.from_user_id != current_user['uid']:
        raise HTTPException(status_code=403, detail="Only the sender can cancel the request")
    if update.status in [FriendRequestStatus.ACCEPTED, FriendRequestStatus.REJECTED] and friend_request.to_user_id != current_user['uid']:
        raise HTTPException(status_code=403, detail="Only the recipient can accept or reject the request")

    # Update request status
    friend_request.status = update.status
    await db.commit()
    await db.refresh(friend_request)

    # Create friendship if request is accepted
    if update.status == FriendRequestStatus.ACCEPTED:
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

    # Create notification for status update
    notification = Notification(
            user_id=friend_request.from_user_id,
            type=NotificationType.FRIEND_REQUEST,
            title="Friend request accepted.",
            message=f"{current_user['uid']} accepted your friend request."
        )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    # Handle real-time notification delivery
    is_user_online = manager.is_user_online(friend_request.from_user_id)
    logger.info(f"Recipient user online: {is_user_online}")
    
    if is_user_online:
        # Send WebSocket notification for online users
        if update.status in [FriendRequestStatus.ACCEPTED, FriendRequestStatus.REJECTED, FriendRequestStatus.CANCELLED]:
            try:
                if update.status == FriendRequestStatus.ACCEPTED:
                    notification = {
                        "id": friend_request.id,
                        "type": WebSocketMessageType.FRIEND_REQUEST_ACCEPTED,
                        "message": f"{friend_request.from_user_id} accepted your friend request.",
                        "from_user": sender_user_dict,
                        "to_user": target_user_dict,
                        "status": "ACCEPTED",
                        "created_at": friend_request.created_at.isoformat() if friend_request.created_at else None,
                        "updated_at": friend_request.updated_at.isoformat() if friend_request.updated_at else None
                    }
                    await manager.send_notification(friend_request.from_user_id, notification)
                elif update.status == FriendRequestStatus.REJECTED:
                    notification = {
                        "id": friend_request.id,
                        "type": WebSocketMessageType.FRIEND_REQUEST_REJECTED,
                        "message": f"{friend_request.from_user_id} rejected your friend request.",
                        "from_user": sender_user_dict,
                        "to_user": target_user_dict,
                        "status": "REJECTED",
                        "created_at": friend_request.created_at.isoformat() if friend_request.created_at else None,
                        "updated_at": friend_request.updated_at.isoformat() if friend_request.updated_at else None
                    }
                    await manager.send_notification(friend_request.from_user_id, notification)
                elif update.status == FriendRequestStatus.CANCELLED:
                    notification = {
                        "id": friend_request.id,
                        "type": WebSocketMessageType.FRIEND_REQUEST_CANCELLED,
                        "message": f"{friend_request.from_user_id} cancelled the friend request.",
                        "from_user": sender_user_dict,
                        "to_user": target_user_dict,
                        "status": "CANCELLED",
                        "created_at": friend_request.created_at.isoformat() if friend_request.created_at else None,
                        "updated_at": friend_request.updated_at.isoformat() if friend_request.updated_at else None
                    }
                    await manager.send_notification(friend_request.to_user_id, notification)
            except Exception as e:
                logger.warning(f"Failed to send WebSocket notification: {e}")
    else:
        # Send push notification for offline users
        stmt = select(DeviceToken).where(
            DeviceToken.is_active == True,
            DeviceToken.user_id == friend_request.from_user_id,
            DeviceToken.platform == "ios"
        )
        device_tokens_result = await db.execute(stmt)
        device_tokens = device_tokens_result.scalars().all()

        if not device_tokens:
            logger.info(f"No active iOS device tokens found for user {friend_request.from_user_id}")

        try:
            notification_responses = await send_push_notifications(device_tokens, notification)
            logger.info(f"Push notifications sent: {len(notification_responses)} responses")
        except Exception as e:
            logger.exception("Error while sending push notifications.")
            notification_responses = []
    
    # Prepare response data
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
    Get the friendship status between current user and another user.
    
    Args:
        user_id: ID of the user to check status with
        db: AsyncSession for database operations
        current_user: Dictionary containing current user information
        
    Returns:
        FriendStatusResponse: Object containing friendship status information
    """
    # Check friendship status
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

    # Check block status
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
    """
    Block a user and remove any existing friendship or pending requests.
    
    Args:
        block: UserBlockCreate object containing block details
        db: AsyncSession for database operations
        current_user: Dictionary containing current user information
        
    Returns:
        UserBlock: The created block object
        
    Raises:
        HTTPException: If user tries to block themselves or block already exists
    """
    # Prevent self-blocking
    if current_user['uid'] == block.blocked_id:
        raise HTTPException(status_code=400, detail="You can't block yourself")

    # Verify target user exists
    target_user = await db.execute(select(User).where(User.id == block.blocked_id))
    target_user = target_user.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check for existing block
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

    # Remove existing friendship
    await db.execute(
        delete(Friend).where(
            or_(
                and_(Friend.user_id == current_user['uid'], Friend.friend_id == block.blocked_id),
                and_(Friend.user_id == block.blocked_id, Friend.friend_id == current_user['uid'])
            )
        )
    )

    # Remove pending friend requests
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
    """
    Remove a block between the current user and another user.
    
    Args:
        user_id: ID of the user to unblock
        db: AsyncSession for database operations
        current_user: Dictionary containing current user information
        
    Returns:
        dict: Success message
        
    Raises:
        HTTPException: If block doesn't exist
    """
    # Find and remove block
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
    Create a report against another user.
    
    Args:
        report: UserReportCreate object containing report details
        db: AsyncSession for database operations
        current_user: Dictionary containing current user information
        
    Returns:
        UserReport: The created report object
        
    Raises:
        HTTPException: If reported user doesn't exist
    """
    # Verify reported user exists
    target_user = await db.execute(select(User).where(User.id == report.reported_id))
    target_user = target_user.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Create and save report
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
    """
    Get all friends of the current user.
    
    Args:
        db: AsyncSession for database operations
        current_user: Dictionary containing current user information
        
    Returns:
        List[Friend]: List of friend relationships
    """
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
    Remove a friendship between the current user and another user.
    
    Args:
        friend_id: ID of the user to remove as friend
        db: AsyncSession for database operations
        current_user: Dictionary containing current user information
        
    Returns:
        dict: Success message
        
    Raises:
        HTTPException: If friendship doesn't exist
    """
    uid = current_user['uid']

    # Remove any pending friend requests
    await db.execute(
        delete(FriendRequest).where(
            or_(
                and_(FriendRequest.from_user_id == uid, FriendRequest.to_user_id == friend_id),
                and_(FriendRequest.from_user_id == friend_id, FriendRequest.to_user_id == uid)
            )
        )
    )

    # Verify friendship exists
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

    # Remove friendship in both directions
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
    Get all users that the current user has blocked.
    
    Args:
        db: AsyncSession for database operations
        current_user: Dictionary containing current user information
        
    Returns:
        List[UserBlock]: List of block relationships
    """
    uid = current_user['uid']

    result = await db.execute(
        select(UserBlock).where(UserBlock.blocker_id == current_user['uid'])
    )
    return result.scalars().all()

async def are_friends(db: AsyncSession, user1_id: str, user2_id: str) -> bool:
    """
    Check if two users are friends.
    
    Args:
        db: AsyncSession for database operations
        user1_id: ID of first user
        user2_id: ID of second user
        
    Returns:
        bool: True if users are friends, False otherwise
    """
    stmt = select(Friend).where(
        (Friend.user_id == user1_id) & (Friend.friend_id == user2_id)
    )
    
    result = await db.execute(stmt)
    friendship = result.scalar_one_or_none()

    return friendship is not None
