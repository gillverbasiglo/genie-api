import firebase_admin
import google.auth
import json
import logging
import requests
import os

from cachetools import cached, TTLCache
from datetime import datetime
from fastapi import Depends, HTTPException, status
from jose import jwt
from openai import OpenAI, OpenAIError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .common import app, get_current_user
from .config import Settings
from .database import engine, Base, SessionLocal
from .google_places_endpoints import router as GooglePlacesEndpoints
from .identity_credentials import WorkloadIdentityCredentials
from .models import InvitationCode, InviteCodeCreate
from .secrets_manager import SecretsManager
from .trip_advisor_endpoints import router as TripAdvisorEndpoints

logger = logging.getLogger(__name__)

settings = Settings()
secrets = SecretsManager(region_name=settings.aws_region)

# Cache the JWKS for 1 hour to avoid fetching it on every request
cache = TTLCache(maxsize=1, ttl=3600)

# Include the TripAdvisor and Google Places routers
app.include_router(TripAdvisorEndpoints)
app.include_router(GooglePlacesEndpoints)

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class TextRequest(BaseModel):
    text: str
    provider: str = "groq"

@app.post("/validate-code/", dependencies=[Depends(get_current_user)])
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

@app.post("/create-invite-code/")
def create_invite_code(invite_code: InviteCodeCreate, db: Session = Depends(get_db), dependencies=[Depends(get_current_user)]):
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

@app.post("/process-text", dependencies=[Depends(get_current_user)], response_model=dict[str, str])
async def process_text(
    request: TextRequest
) -> dict[str, str]:
    """
    Process text input using Groq's LLM API.
    
    Args:
        request: The text request containing input to process
        
    Returns:
        Dictionary containing the LLM response text
        
    Raises:
        HTTPException: When API authentication fails or service is unavailable
    """
    try:
        if request.provider == "groq":
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=secrets.get_api_key("groq")
            )

            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "user", "content": request.text}
                ]
            )
        elif request.provider == "openai":
            client = OpenAI(
                api_key=secrets.get_api_key("openai")
            )

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": request.text}
                ]
            )

        return {"result": response.choices[0].message.content}
        
    except OpenAIError as e:
        if "authentication" in str(e).lower():
            raise HTTPException(
                status_code=401,
                detail="Failed to authenticate with LLM service. Please check API key."
            )
        elif "rate" in str(e).lower():
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded for LLM service. Please try again later."
            )
        else:
            raise HTTPException(
                status_code=503,
                detail=f"LLM service error: {str(e)}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

@app.get("/protected-route")
async def protected_route(current_user: dict = Depends(get_current_user)):
    try:
        # Get additional user information from Firebase
        user = auth.get_user(current_user["uid"])
        return {
            "uid": user.uid,
            "phone_number": user.phone_number,
            "provider_id": "phone",
            "display_name": user.display_name,
            "email": user.email
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user details: {str(e)}"
        )
