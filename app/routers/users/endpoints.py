import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, String, not_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from app.init_db import get_db
from app.models import User, Invitation, Friend
from app.schemas.invitation import ContactCheckResponse
from app.schemas.users import UserCreate, MeUserResponse, UpdateArchetypesAndKeywordsRequest
from app.common import get_current_user
from app.core.websocket.websocket_manager import manager
from app.services.user_service import check_contacts, check_contacts_list, delete_user, get_current_user_info, register_user, update_user_archetypes_and_keywords

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/update-archetypes-and-keywords", response_model=None)
async def update_archetypes_and_keywords_api(
    request: UpdateArchetypesAndKeywordsRequest, 
    db: AsyncSession = Depends(get_db), 
    current_user: dict = Depends(get_current_user)
    ):
    try:
        return await update_user_archetypes_and_keywords(request, db, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me", response_model=MeUserResponse)
async def get_current_user_info_api(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        return await get_current_user_info(current_user["uid"], db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/check-contacts", response_model=List[ContactCheckResponse])
async def check_contacts_api(
    phone_numbers: List[str],
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        return await check_contacts(phone_numbers, current_user["uid"], db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/register-user", response_model=dict)
async def register_user_api(
    user_data: UserCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        return await register_user(user_data, current_user["uid"], db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list", response_model=List[MeUserResponse])
async def check_contacts_list_api(
    phone_number: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        return await check_contacts_list(phone_number, current_user["uid"], db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/online-status")
async def check_user_online_status(user_id: str):
    return {"user_id": user_id, "online": manager.is_user_online(user_id)}

@router.delete("/delete/{identifier}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_api(
    identifier: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        return await delete_user(identifier, current_user["uid"], db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
