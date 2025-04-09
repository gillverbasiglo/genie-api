# Routers for invitations and inivte code endpoints
import logging

from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from sqlalchemy.orm import Session
from ..models import InvitationCode, InviteCodeCreate
from ..init_db import get_db

from ..common import get_current_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.post("/validate-code/", dependencies=[Depends(get_current_user)])
async def validate_code(code: str, db: Session = Depends(get_db)):
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

@router.post("/create-invite-code/", dependencies=[Depends(get_current_user)])
def create_invite_code(invite_code: InviteCodeCreate, db: Session = Depends(get_db)):
    # Check if code already exists
    db_code = db.query(InvitationCode).filter(InvitationCode.code == invite_code.code).first()
    if db_code:
        raise HTTPException(status_code=400, detail="Invitation code already exists")

    new_code = InvitationCode(
        code=invite_code.code,
        expires_at=invite_code.expires_at,
        is_active=invite_code.is_active
    )

    db.add(new_code)
    db.commit()
    db.refresh(new_code)

    return {"message": "Invitation code created successfully", "code": new_code.code}
