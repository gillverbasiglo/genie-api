import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.init_db import get_db
from app.schemas.invitation import BulkInvitationCreate, InvitationResponse, PendingInvitationResponse
from app.models.invite_code_create import InviteCodeCreate
from app.common import get_current_user
from app.services.invitation_service import create_invite_code, get_invitation_stats, get_pending_invitations, send_invitation, validate_code

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invitations", tags=["invitations"])

@router.post("/validate-code/", dependencies=[Depends(get_current_user)])
async def validate_code_api(code: str, db: AsyncSession = Depends(get_db)):
    try:
        return await validate_code(code, db)
    except ValueError as e:
        raise e


@router.post("/create-invite-code/", dependencies=[Depends(get_current_user)])
async def create_invite_code_api(invite_code: InviteCodeCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await create_invite_code(invite_code, db)
    except ValueError as e:
        raise e


@router.post("/send", response_model=List[InvitationResponse])
async def send_invitation_api(
    invitation_data: BulkInvitationCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        return await send_invitation(invitation_data, current_user, db)
    except ValueError as e:
        raise e


@router.get("/stats", response_model=dict)
async def get_invitation_stats_api(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        return await get_invitation_stats(current_user, db)
    except ValueError as e:
        raise e

@router.post("/pending-invitations", response_model=List[PendingInvitationResponse])
async def get_pending_invitations_api(
    phone_numbers: List[str],
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        return await get_pending_invitations(phone_numbers, current_user, db)
    except ValueError as e:
        raise e

