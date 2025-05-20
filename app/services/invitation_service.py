import uuid
import random
import string
import logging
from typing import List
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from app.models import Invitation, InvitationCode, User
from app.schemas.invitation import BulkInvitationCreate, PendingInvitationResponse
from app.models.invite_code_create import InviteCodeCreate
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

def generate_invite_code(length=6) -> str:
    """
    Generates a random invitation code of specified length.
    
    Args:
        length (int): Length of the invitation code (default: 6)
    
    Returns:
        str: Random invitation code containing uppercase letters and digits
    """
    # Create a pool of characters (uppercase letters and digits)
    characters = string.ascii_uppercase + string.digits
    # Generate a random code of specified length
    return ''.join(random.choice(characters) for _ in range(length))

async def validate_code(code: str, db: AsyncSession) -> dict:
    """
    Validates an invitation code by checking its existence, usage status, expiration, and active status.
    
    Args:
        code (str): The invitation code to validate
        db (AsyncSession): Database session
    
    Returns:
        dict: Message indicating code validity
    
    Raises:
        HTTPException: If code is invalid, used, expired, or inactive
    """
    db_code = db.query(InvitationCode).filter(InvitationCode.code == code).first()
    if not db_code:
        raise HTTPException(status_code=404, detail="Invite Code not found")
    if db_code.used_by:
        raise HTTPException(status_code=400, detail="Invite Code is already used")
    if db_code.expires_at and db_code.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invite Code has expired")
    if not db_code.is_active:
        raise HTTPException(status_code=400, detail="Invite Code is not active")
    return {"message": "Invite Code is valid"}

async def create_invite_code(invite_code: InviteCodeCreate, db: AsyncSession) -> dict:
    """
    Creates a new invitation code in the database.
    
    Args:
        invite_code (InviteCodeCreate): Invitation code creation data
        db (AsyncSession): Database session
    
    Returns:
        dict: Success message and created code
    
    Raises:
        HTTPException: If code already exists
    """
    db_code = db.query(InvitationCode).filter(InvitationCode.code == invite_code.code).first()
    if db_code:
        raise HTTPException(status_code=400, detail="Invitation code already exists")

    new_code = InvitationCode(
        code=invite_code.code,
        expires_at=invite_code.expires_at,
        is_active=invite_code.is_active
    )

    db.add(new_code)
    await db.commit()
    await db.refresh(new_code)

    return {"message": "Invitation code created successfully", "code": new_code.code}

async def send_invitation(invitation_data: BulkInvitationCreate, current_user: dict, db: AsyncSession) -> List[Invitation]:
    """
    Sends bulk invitations to multiple users.
    
    Args:
        invitation_data (BulkInvitationCreate): Bulk invitation data containing invitee details
        current_user (dict): Current user information
        db (AsyncSession): Database session
    
    Returns:
        List[Invitation]: List of created invitations
    
    Raises:
        HTTPException: If inviter user not found
    """
    # Check if user exists
    stmt = select(User).where(User.id == current_user["uid"])
    inviter = db.execute(stmt).scalar_one_or_none()
    if inviter is None:
        raise HTTPException(status_code=404, detail="User not found")

    new_invitations = []
    existing_phones = []
    # Check for existing invitations
    for invitee in invitation_data.invitees:
        existing_invite = db.execute(select(Invitation).where(
            Invitation.inviter_id == current_user["uid"],
            Invitation.invitee_phone == invitee.phone
        )).scalar_one_or_none()
        
        if existing_invite:
            existing_phones.append(invitee.phone)
            continue

        # Generate a unique invite code
        invite_code = generate_invite_code()
        while db.execute(select(Invitation).where(Invitation.invite_code == invite_code)).scalar_one_or_none():
            invite_code = generate_invite_code()

        # Create new invitation
        new_invitation = Invitation(
            id=str(uuid.uuid4()),
            inviter_id=current_user["uid"],
            invitee_phone=invitee.phone,
            invitee_email=invitee.email,
            invite_code=invite_code
        )
        new_invitations.append(new_invitation)
    
    if existing_phones:
        # If some invitations already exist, return a warning but continue with the rest
        logger.warning(f"Invitations already exist for phones: {existing_phones}")
    
    if new_invitations:
        db.add_all(new_invitations)
        await db.commit()
        for invitation in new_invitations:
            await db.refresh(invitation)
    
    return new_invitations

async def get_invitation_stats(current_user: dict, db: AsyncSession) -> dict:
    """
    Retrieves invitation statistics for the current user.
    
    Args:
        current_user (dict): Current user information
        db (AsyncSession): Database session
    
    Returns:
        dict: Statistics containing total and accepted invitations
    """
    # Get total invitations sent
    stmt = select(func.count()).select_from(Invitation).where(Invitation.inviter_id == current_user["uid"])
    total_invites = db.execute(stmt).scalar_one()
    
    # Get accepted invitations
    stmt = select(func.count()).select_from(Invitation).where(
        Invitation.inviter_id == current_user["uid"],
        Invitation.status == "accepted"
    )
    accepted_invites = db.execute(stmt).scalar_one()
    
    return {
        "total_invites": total_invites,
        "accepted_invites": accepted_invites
    }

async def get_pending_invitations(phone_numbers: List[str], current_user: dict, db: AsyncSession) -> List[PendingInvitationResponse]:
    """
    Retrieves pending invitations for specified phone numbers.
    
    Args:
        phone_numbers (List[str]): List of phone numbers to check
        current_user (dict): Current user information
        db (AsyncSession): Database session
    
    Returns:
        List[PendingInvitationResponse]: List of pending invitations with their details
    """
    # Get all pending invitations for these phone numbers
    stmt = select(Invitation).where(
        Invitation.inviter_id == current_user["uid"],
        Invitation.invitee_phone.in_(phone_numbers),
        Invitation.status == "pending"
    )
    pending_invites = db.execute(stmt).scalars().all()
    
    # Convert to response format
    response = [
        PendingInvitationResponse(
            phone_number=invite.invitee_phone,
            email=invite.invitee_email,
            invite_code=invite.invite_code,
            invited_at=invite.created_at,
            status=invite.status
        )
        for invite in pending_invites
    ]
    
    return response 
