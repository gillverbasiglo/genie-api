import requests
import json

from cachetools import cached, TTLCache
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from openai import OpenAI, OpenAIError
from pydantic import BaseModel

from app.config import Settings

app = FastAPI()
security = HTTPBearer()

# Configure Cognito settings
CLIENT_ID = "3jrpf1q7jiguprenuqam7tpkf5"
COGNITO_JWKS_URL = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
REGION = "us-east-1"
USER_POOL_ID = "us-east-1_fhyOsjWSR"

# Cache the JWKS for 1 hour to avoid fetching it on every request
cache = TTLCache(maxsize=1, ttl=3600)

@cached(cache)
def get_jwks():
    return requests.get(COGNITO_JWKS_URL).json()

async def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    # Get the Key ID from the token header
    try:
        payload = jwt.get_unverified_header(token)
        kid = payload.get("kid")
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    # Get the JWKS from the Cognito JWKS URL
    jwks = get_jwks()
    key = None

    # Find the correct key from the JWKS
    for key in jwks["keys"]:
        if key["kid"] == kid:
            key = jwk
            break

    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    # Construct the public key
    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))

    # Decode the token
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=COGNITO_JWKS_URL
        )

        return payload
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=Settings().groq_api_key
)

class TextRequest(BaseModel):
    text: str

@app.post("/process-text", response_model=dict[str, str])
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
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
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
