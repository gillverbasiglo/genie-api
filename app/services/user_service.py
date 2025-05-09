from datetime import datetime, timezone
from sqlite3 import IntegrityError
from fastapi import HTTPException, logger, status
from app.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import String, not_, or_, select
from typing import Dict, List, Optional

from app.models.friends.friends import Friend
from app.models.invitation import Invitation
from app.schemas.invitation import ContactCheckResponse
from app.schemas.users import UpdateArchetypesAndKeywordsRequest, UserCreate

async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def get_user_by_phone(db: AsyncSession, phone: str) -> Optional[User]:
    query = select(User).where(User.phone == phone)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, user: User) -> User:
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def update_user_archetypes_and_keywords(
    request: UpdateArchetypesAndKeywordsRequest,
    db: AsyncSession,
    current_user: dict
):
    result = await db.execute(select(User).where(User.id == current_user["uid"]))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user.archetypes = [archetype.model_dump() for archetype in request.archetypes]
    user.keywords = [keyword.model_dump() for keyword in request.keywords]

    await db.commit()
    await db.refresh(user)

    return {
        "archetypes": user.archetypes,
        "keywords": user.keywords
    }

async def get_current_user_info(user_id: str, db: AsyncSession):
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
    # Validate inviter exists
    result = await db.execute(select(User).where(User.id == user_id))
    inviter = result.scalar_one_or_none()
    if inviter is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Get registered users
    result = await db.execute(
        select(User).where(User.phone_number.in_(phone_numbers))
    )
    users = result.scalars().all()
    user_map = {user.phone_number: user for user in users}

    # Get pending invitations
    result = await db.execute(
        select(Invitation).where(
            Invitation.inviter_id == user_id,
            Invitation.invitee_phone.in_(phone_numbers),
            Invitation.status == "pending"
        )
    )
    pending_invites = result.scalars().all()
    invite_map = {invite.invitee_phone: invite for invite in pending_invites}

    # Build response
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
    try:
        # Create a new user instance
        new_user = User(
            id=user_id,
            phone_number=user_data.phone_number,
            email=user_data.email,
            display_name=user_data.display_name,
            created_at=datetime.now(timezone.UTC)
        )

        # Handle invitation logic if invite code is provided
        if user_data.invite_code:
            result = await db.execute(select(Invitation).where(
                Invitation.invite_code == user_data.invite_code,
                Invitation.status == "pending"
            ))
            invitation = result.scalar_one_or_none()

            if invitation:
                invitation.status = "accepted"
                invitation.accepted_at = datetime.now(timezone.UTC)
                invitation.invitee_id = user_id
                new_user.invited_by = invitation.inviter_id

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        return {
            "message": "User registered successfully",
            "user_id": new_user.id,
            "invited_by": new_user.invited_by if new_user.invited_by else None
        }

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is either already registered or the phone/email is already in use"
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error registering user: {str(e)}"
        )
    
async def check_contacts(
    phone_number: str,
    current_user_id: str,
    db: AsyncSession
) -> List[User]:
    # Get IDs of user's friends (both directions)
    friend_ids_stmt = select(Friend.friend_id).where(Friend.user_id == current_user_id)
    reverse_friend_ids_stmt = select(Friend.user_id).where(Friend.friend_id == current_user_id)

    friend_ids_result = await db.execute(friend_ids_stmt)
    reverse_friend_ids_result = await db.execute(reverse_friend_ids_stmt)

    friend_ids = set(friend_ids_result.scalars().all()) | set(reverse_friend_ids_result.scalars().all())

    # Query users matching the phone number (partial match), excluding current user and existing friends
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
    # Fetch user by ID or phone number
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

    # Ensure user is deleting their own account
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

        # Delete invitations
        await db.execute(
            select(Invitation).where(
                or_(
                    Invitation.inviter_id == user.id,
                    Invitation.invitee_id == user.id
                )
            ).execution_options(synchronize_session="fetch")
        )

        # Delete user
        await db.delete(user)
        await db.commit()

    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting user {identifier}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )
    