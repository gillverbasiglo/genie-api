from datetime import datetime, timezone
from sqlite3 import IntegrityError
from fastapi import HTTPException, logger, status, Request
from app.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import String, not_, or_, select
from typing import Dict, List, Optional

from app.models.friends.friend_requests import FriendRequest
from app.models.friends.friends import Friend
from app.models.invitation import Invitation
from app.models.notifications import Notification
from app.schemas.invitation import ContactCheckResponse
from app.schemas.users import UpdateArchetypesAndKeywordsRequest, UserCreate

async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    """
    Retrieve a user by their unique identifier.
    
    Args:
        db: AsyncSession - Database session for executing queries
        user_id: str - Unique identifier of the user
        
    Returns:
        Optional[User]: User object if found, None otherwise
    """
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """
    Retrieve a user by their email address.
    
    Args:
        db: AsyncSession - Database session for executing queries
        email: str - Email address of the user
        
    Returns:
        Optional[User]: User object if found, None otherwise
    """
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_user_by_phone(db: AsyncSession, phone: str) -> Optional[User]:
    """
    Retrieve a user by their phone number.
    
    Args:
        db: AsyncSession - Database session for executing queries
        phone: str - Phone number of the user
        
    Returns:
        Optional[User]: User object if found, None otherwise
    """
    query = select(User).where(User.phone == phone)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, user: User) -> User:
    """
    Create a new user in the database.
    
    Args:
        db: AsyncSession - Database session for executing queries
        user: User - User object to be created
        
    Returns:
        User: Created user object with updated database fields
    """
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def update_user_archetypes_and_keywords(
    request: UpdateArchetypesAndKeywordsRequest,
    db: AsyncSession,
    current_user: dict
):
    """
    Update a user's archetypes and keywords preferences.
    
    Args:
        request: UpdateArchetypesAndKeywordsRequest - Request containing new archetypes and keywords
        db: AsyncSession - Database session for executing queries
        current_user: dict - Current authenticated user information
        
    Returns:
        dict: Updated archetypes and keywords
        
    Raises:
        HTTPException: If user is not found
    """
    # Fetch user from database
    result = await db.execute(select(User).where(User.id == current_user["uid"]))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # Update user preferences
    user.archetypes = [archetype.model_dump() for archetype in request.archetypes]
    user.keywords = [keyword.model_dump() for keyword in request.keywords]

    await db.commit()
    await db.refresh(user)

    return {
        "archetypes": user.archetypes,
        "keywords": user.keywords
    }

async def get_current_user_info(user_id: str, db: AsyncSession):
    """
    Retrieve detailed information about the current user.
    
    Args:
        user_id: str - Unique identifier of the user
        db: AsyncSession - Database session for executing queries
        
    Returns:
        User: User object containing user information
        
    Raises:
        HTTPException: If user is not found
    """
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database"
        )

    return user

async def check_contacts(
    phone_numbers: List[str],
    user_id: str,
    db: AsyncSession
) -> List[ContactCheckResponse]:
    """
    Check the status of contacts (phone numbers) in the system.
    Verifies if contacts are registered users and if they have pending invitations.
    
    Args:
        phone_numbers: List[str] - List of phone numbers to check
        user_id: str - ID of the user performing the check
        db: AsyncSession - Database session for executing queries
        
    Returns:
        List[ContactCheckResponse]: List of contact status responses
        
    Raises:
        HTTPException: If the checking user is not found
    """
    # Verify the checking user exists
    stmt = select(User).where(User.id == user_id)
    query_result = await db.execute(stmt)
    inviter = query_result.scalar_one_or_none()
    if inviter is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Find registered users with the provided phone numbers
    stmt = select(User).where(User.phone_number.in_(phone_numbers))
    query_result = await db.execute(stmt)
    users = query_result.scalars().all()
    user_map = {user.phone_number: user for user in users}
    
    # Check for pending invitations
    stmt = select(Invitation).where(
        Invitation.inviter_id == user_id,
        Invitation.invitee_phone.in_(phone_numbers),
        Invitation.status == "pending"
    )
    query_result = await db.execute(stmt)
    pending_invites = query_result.scalars().all()
    invite_map = {invite.invitee_phone: invite for invite in pending_invites}
    
    # Generate response for each phone number
    response = []
    for phone in phone_numbers:
        user = user_map.get(phone)
        invite = invite_map.get(phone)
        
        response.append(ContactCheckResponse(
            phone_number=phone,
            is_registered=user is not None,
            is_invited=invite is not None,
            user_id=user.id if user else None,
            display_name=user.display_name if user else None,
            invite_code=invite.invite_code if invite else None,
            invited_at=invite.created_at if invite else None
        ))
    
    return response

async def register_user(
    user_data: UserCreate,
    user_id: str,
    db: AsyncSession
) -> Dict[str, str]:
    """
    Register a new user in the system.
    Handles user creation and invitation acceptance if an invite code is provided.
    
    Args:
        user_data: UserCreate - User registration data
        user_id: str - Unique identifier for the new user
        db: AsyncSession - Database session for executing queries
        
    Returns:
        Dict[str, str]: Registration success message and user details
        
    Raises:
        HTTPException: If registration fails due to duplicate data or other errors
    """

    logger.info(f"Starting registration for user_id={user_id}, email={user_data.email}, phone_number={user_data.phone_number}")
    try:

        # Check if user already exists by phone number or email
        existing_user_query = await db.execute(
            select(User).where(
                (User.phone_number == user_data.phone_number) |
                (User.email == user_data.email)
            )
        )
        existing_user = existing_user_query.scalar_one_or_none()

        if existing_user:
            logger.warning(f"User already exists with email={user_data.email} or phone={user_data.phone_number}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this phone number or email already exists."
            )
        
        # Create new user instance
        new_user = User(
            id=user_id,
            phone_number= user_data.phone_number,
            email=user_data.email,
            display_name=user_data.display_name,
            created_at=datetime.now(timezone.utc)
        )
        logger.info(f"Creating user with ID {user_id}")

        # Handle invitation if invite code is provided
        if user_data.invite_code:
            logger.info(f"Checking invitation for invite_code={user_data.invite_code}")
            query_result = await db.execute(select(Invitation).where(
                Invitation.invite_code == user_data.invite_code,
                Invitation.status == "pending"
            ))
            invitation = query_result.scalar_one_or_none()

            if invitation:
                logger.info(f"Invite code {user_data.invite_code} accepted by user_id={user_id}")
                # Update invitation status and link to new user
                invitation.status = "accepted"
                invitation.accepted_at = datetime.now(timezone.UTC)
                invitation.invitee_id = user_id
                new_user.invited_by = invitation.inviter_id

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info(f"User registered successfully: user_id={new_user.id}")
        return {
            "message": "User registered successfully",
            "user_id": new_user.id,
            "invited_by": new_user.invited_by if new_user.invited_by else None
        }

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is either logged in or this phone or email already exists"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error registering user: {str(e)}"
        )
    
async def check_contacts_list(
    phone_number: str,
    current_user_id: str,
    db: AsyncSession
) -> List[User]:
    """
    Search for users by phone number, excluding current user and existing friends.
    
    Args:
        phone_number: str - Phone number to search for (partial match)
        current_user_id: str - ID of the current user
        db: AsyncSession - Database session for executing queries
        
    Returns:
        List[User]: List of matching users
    """
    # Get IDs of existing friends (both directions)
    friend_ids_stmt = select(Friend.friend_id).where(Friend.user_id == current_user_id)
    reverse_friend_ids_stmt = select(Friend.user_id).where(Friend.friend_id == current_user_id)

    friend_ids_result = await db.execute(friend_ids_stmt)
    reverse_friend_ids_result = await db.execute(reverse_friend_ids_stmt)

    friend_ids = set(friend_ids_result.scalars().all()) | set(reverse_friend_ids_result.scalars().all())

    # Search for users matching the phone number
    stmt = select(User).where(
        User.phone_number.cast(String).like(f"%{phone_number}%"),
        User.id != current_user_id,
        not_(User.id.in_(friend_ids))
    )

    result = await db.execute(stmt)
    users = result.scalars().all()

    return users

async def delete_user(
    identifier: str,
    current_user_id: str,
    db: AsyncSession
):
    """
    Delete a user and all associated data from the system.
    Only allows users to delete their own account.
    
    Args:
        identifier: str - User ID or phone number to identify the user
        current_user_id: str - ID of the current authenticated user
        db: AsyncSession - Database session for executing queries
        
    Raises:
        HTTPException: If user not found, unauthorized, or deletion fails
    """
    # Find user by ID or phone number
    stmt = select(User).where(
        or_(
            User.id == identifier,
            User.phone_number == identifier
        )
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Verify user is deleting their own account
    if user.id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete this user"
        )

    try:
        # Delete friend relationships
        await db.execute(
            select(Friend).where(
                or_(
                    Friend.user_id == user.id,
                    Friend.friend_id == user.id
                )
            ).execution_options(synchronize_session="fetch")
        )

        # Delete friend request relationships
        await db.execute(
            select(FriendRequest).where(
                or_(
                    FriendRequest.from_user_id == user.id,
                    FriendRequest.to_user_id == user.id
                )
            ).execution_options(synchronize_session="fetch")
        )

        # Delete notifications
        await db.execute(
            select(Notification).where(
                Notification.user_id == user.id
            ).execution_options(synchronize_session="fetch")
        )

        # Delete invitations
        await db.execute(
            select(Invitation).where(
                or_(
                    Invitation.inviter_id == user.id,
                    Invitation.invitee_id == user.id
                )
            ).execution_options(synchronize_session="fetch")
        )

        # Delete user record
        await db.delete(user)
        await db.commit()

    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting user {identifier}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )
    
async def get_user_ip_address(request: Request):
    """
    Get the IP address of the user.
    """
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.client.host
    return ip
