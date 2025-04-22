import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from ...init_db import get_db
from app.models import User, Invitation
from ...schemas.invitation import ContactCheckResponse
from ...schemas.users import UserCreate, MeUserResponse, UpdateArchetypesAndKeywordsRequest
from ...common import get_current_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/update-archetypes-and-keywords", response_model=None)
async def update_archetypes_and_keywords(
    request: UpdateArchetypesAndKeywordsRequest, 
    db: AsyncSession = Depends(get_db), 
    current_user: dict = Depends(get_current_user)
    ):
    user = await db.execute(select(User).where(User.id == current_user["uid"]))
    user = user.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user.archetypes = request.archetypes
    user.keywords = request.keywords

    await db.commit()
    await db.refresh(user)

    return {
        "archetypes": user.archetypes,
        "keywords": user.keywords
    }

@router.get("/me", response_model=MeUserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Get user details from database
    stmt = select(User).where(User.id == current_user["uid"])
    user = await db.execute(stmt)
    user = user.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database"
        )

    return user


@router.post("/check-contacts", response_model=List[ContactCheckResponse])
async def check_contacts(
    phone_numbers: List[str],
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if user exists
    stmt = select(User).where(User.id == current_user["uid"])
    inviter = db.execute(stmt).scalar_one_or_none()
    if inviter is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Query users with these phone numbers
    stmt = select(User).where(User.phone_number.in_(phone_numbers))
    users = db.execute(stmt).scalars().all()
    user_map = {user.phone_number: user for user in users}
    
    # Query pending invitations for these phone numbers
    stmt = select(Invitation).where(
        Invitation.inviter_id == current_user["uid"],
        Invitation.invitee_phone.in_(phone_numbers),
        Invitation.status == "pending"
    )
    pending_invites = db.execute(stmt).scalars().all()
    invite_map = {invite.invitee_phone: invite for invite in pending_invites}
    
    # Create response for each phone number
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

@router.post("/register-user", response_model=dict)
async def register_user(
    user_data: UserCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Create new user
        new_user = User(
            id=current_user["uid"],
            phone_number= user_data.phone_number,
            email=user_data.email,
            display_name=user_data.display_name,
            created_at=datetime.now(timezone.utc)
        )

        # If invite code is provided, link it to the invitation
        if user_data.invite_code:
            invitation = db.execute(select(Invitation).where(
                Invitation.invite_code == user_data.invite_code,
                Invitation.status == "pending"
            )).scalar_one_or_none()

            if invitation:
                # Update invitation status
                invitation.status = "accepted"
                invitation.accepted_at = datetime.now(timezone.UTC)
                invitation.invitee_id = current_user["uid"]
                # Set the invited_by relationship
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
