import httpx

from app.config import settings
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/search", tags=["search"])

class FlightSearchRequest(BaseModel):
    flight_number: str

@router.get("/flight")
async def search_flight(flight_number: str):
    """
    Track flight information and status.
    """
    AVIANTION_STACK_URL = "https://api.aviationstack.com/v1/flights"
    print(flight_number)
    print(settings.aviation_stack_api_key.get_secret_value())

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(AVIANTION_STACK_URL, params={"flight_iata": flight_number, "access_key": settings.aviation_stack_api_key.get_secret_value()})
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.get("/movies")
async def search_movies():
    """
    Get trending movies from TMDB.
    """
    TMDB_URL = "https://api.themoviedb.org/3/trending/movie/day?language=en-US"

    headers = {
        "Authorization": f"Bearer {settings.tmdb_api_key.get_secret_value()}"
    }

    print(headers)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(TMDB_URL, headers=headers)
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
