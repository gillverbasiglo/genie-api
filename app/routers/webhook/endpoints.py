import logging
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.init_db import get_db
from app.utils.verify_llm_secret import verify_secret
from app.models.user import User
from app.schemas.users import MeUserResponse, Archetype, Keyword

router = APIRouter(prefix="/webhook", tags=["webhook"])
logger = logging.getLogger(__name__)

@router.post("/get_archetype_keywords", response_model=MeUserResponse)
async def handle_llm_webhook(
    request: Request,
    user: User = Depends(verify_secret),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"🔐 Verified LLM webhook from user: {user.id}")

    # Convert user.archetypes/keywords JSON fields to Pydantic types
    archetypes = (
        [Archetype(**a) for a in user.archetypes] if user.archetypes else None
    )
    keywords = (
        [Keyword(**k) for k in user.keywords] if user.keywords else None
    )

    response = MeUserResponse(
        id=user.id,
        phone_number=user.phone_number,
        email=user.email,
        display_name=user.display_name,
        invite_code=None,  # You can update this if stored separately
        created_at=user.created_at,
        invited_by=user.invited_by,
        archetypes=archetypes,
        keywords=keywords,
    )

    logger.info(f"🔐 User info: {response.dict()}")
    return response