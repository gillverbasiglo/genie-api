import uuid
import random
import string
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from ..init_db import get_db
from ..models.User import User
from ..models.invitation import Invitation
from ..schemas.invitation import InvitationResponse, ContactCheckResponse
from ..common import get_current_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invitations", tags=["invitations"])

def generate_invite_code(length=6):
    # Create a pool of characters (uppercase letters and digits)
    characters = string.ascii_uppercase + string.digits
    # Generate a random code of specified length
    return ''.join(random.choice(characters) for _ in range(length))

# First, let's update the schema for multiple invitations
class InviteeInfo(BaseModel):
    phone: str
    email: Optional[str] = None

class BulkInvitationCreate(BaseModel):
    invitees: List[InviteeInfo]

class UserCreate(BaseModel):
    phone_number: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    invite_code: Optional[str] = None  # To track who invited them

class PendingInvitationResponse(BaseModel):
    phone_number: str
    email: Optional[str]
    invite_code: str
    invited_at: datetime
    status: str

@router.post("/send", response_model=List[InvitationResponse])
async def send_invitation(
    invitation_data: BulkInvitationCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if user exists
    inviter = db.query(User).filter(User.id == current_user["uid"]).first()
    if not inviter:
        raise HTTPException(status_code=404, detail="User not found")

    new_invitations = []
    existing_phones = []
    # Check for existing invitations
    for invitee in invitation_data.invitees:
        existing_invite = db.query(Invitation).filter(
            Invitation.inviter_id == current_user["uid"],
            Invitation.invitee_phone == invitee.phone
        ).first()
        
        if existing_invite:
            existing_phones.append(invitee.phone)
            continue

        # Generate a unique invite code
        invite_code = generate_invite_code()
        while db.query(Invitation).filter(Invitation.invite_code == invite_code).first():
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
        db.commit()
        for invitation in new_invitations:
            db.refresh(invitation)
    
    return new_invitations

@router.post("/check-contacts", response_model=List[ContactCheckResponse])
async def check_contacts(
    phone_numbers: List[str],
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if user exists
    inviter = db.query(User).filter(User.id == current_user["uid"]).first()
    if not inviter:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Query users with these phone numbers
    users = db.query(User).filter(User.phone_number.in_(phone_numbers)).all()
    user_map = {user.phone_number: user for user in users}
    
    # Query pending invitations for these phone numbers
    pending_invites = db.query(Invitation).filter(
        Invitation.inviter_id == current_user["uid"],
        Invitation.invitee_phone.in_(phone_numbers),
        Invitation.status == "pending"
    ).all()
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

@router.get("/stats", response_model=dict)
async def get_invitation_stats(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get total invitations sent
    total_invites = db.query(Invitation).filter(
        Invitation.inviter_id == current_user["uid"]
    ).count()
    
    # Get accepted invitations
    accepted_invites = db.query(Invitation).filter(
        Invitation.inviter_id == current_user["uid"],
        Invitation.status == "accepted"
    ).count()
    
    return {
        "total_invites": total_invites,
        "accepted_invites": accepted_invites
    }

@router.post("/register-user", response_model=dict)
async def register_user(
    user_data: UserCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
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
            invitation = db.query(Invitation).filter(
                Invitation.invite_code == user_data.invite_code,
                Invitation.status == "pending"
            ).first()

            if invitation:
                # Update invitation status
                invitation.status = "accepted"
                invitation.accepted_at = datetime.now(timezone.UTC)
                invitation.invitee_id = current_user["uid"]
                # Set the invited_by relationship
                new_user.invited_by = invitation.inviter_id

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {
            "message": "User registered successfully",
            "user_id": new_user.id,
            "invited_by": new_user.invited_by if new_user.invited_by else None
        }

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this phone number or email already exists"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error registering user: {str(e)}"
        )

@router.post("/pending-invitations", response_model=List[PendingInvitationResponse])
async def get_pending_invitations(
    phone_numbers: List[str],
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get all pending invitations for these phone numbers
    pending_invites = db.query(Invitation).filter(
        Invitation.inviter_id == current_user["uid"],
        Invitation.invitee_phone.in_(phone_numbers),
        Invitation.status == "pending"
    ).all()
    
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

