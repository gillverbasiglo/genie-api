import firebase_admin
import google.auth
import json
import logging
import requests
import os

from cachetools import cached, TTLCache
from datetime import datetime
from exa_py import Exa
from fastapi import Depends, HTTPException, status
from jose import jwt
from openai import OpenAI, OpenAIError
from pydantic import BaseModel
from sqlalchemy.orm import Session
from tavily import TavilyClient

from .init_db import get_db
from .common import app, get_current_user
from .config import settings
from .database import engine, Base, SessionLocal
from .routers.google_places_endpoints import router as GooglePlacesEndpoints
from .identity_credentials import WorkloadIdentityCredentials
from .routers.trip_advisor_endpoints import router as TripAdvisorEndpoints
from .routers.invitations_endpoints import router as InvitationsEndpoints
from .routers.apple_site_association_endpoint import router as AppleSiteAssociationEndpoint
logger = logging.getLogger(__name__)

# Cache the JWKS for 1 hour to avoid fetching it on every request
cache = TTLCache(maxsize=1, ttl=3600)

# Include the TripAdvisor and Google Places routers
app.include_router(TripAdvisorEndpoints)
app.include_router(GooglePlacesEndpoints)
app.include_router(InvitationsEndpoints)
app.include_router(AppleSiteAssociationEndpoint)

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

class TextRequest(BaseModel):
    text: str
    provider: str = "groq"

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
                api_key=settings.groq_api_key.get_secret_value()
            )

            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "user", "content": request.text}
                ]
            )
        elif request.provider == "openai":
            client = OpenAI(
                api_key=settings.openai_api_key.get_secret_value()
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

class WebSearchRequest(BaseModel):
    query: str
    provider: str = "tavily"

@app.post("/web-search", dependencies=[Depends(get_current_user)], response_model=None)
async def web_search(request: WebSearchRequest):
    """
    Perform a web search using the specified provider.
    
    Args:
        request: The web search request containing a query and provider
        
    Returns:
        JSON containing the search results
        
    Raises:
        HTTPException: When API authentication fails or service is unavailable
    """
    try:
        if request.provider == "tavily":
            client = TavilyClient(settings.tavily_api_key.get_secret_value())
            results = client.search(request.query)
            return results
        elif request.provider == "exa":
            client = Exa(settings.exa_api_key.get_secret_value())
            results = client.search_and_contents(request.query, text=True)
            return results
        else:
            logger.error(f"Invalid provider: {request.provider}")
            raise HTTPException(
                status_code=400,
                detail="Invalid provider"
            )
    except Exception as e:
        logger.error(f"Error performing web search: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error performing web search: {str(e)}"
        )
