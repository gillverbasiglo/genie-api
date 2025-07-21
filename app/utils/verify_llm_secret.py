from fastapi import Request, HTTPException, status, Depends
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.init_db import get_db
from app.models.user import User

JWT_SECRET = settings.jwt_api_key.get_secret_value()
JWT_ALGORITHM = "HS256"

async def verify_secret(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """
    Verifies and decodes JWT token in Authorization header, and fetches the associated user.

    Returns:
        User: SQLAlchemy User object

    Raises:
        HTTPException 401: If token is missing, invalid, or user doesn't exist
    """
    auth_header = request.headers.get("authorization", "")

    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must start with 'Bearer'"
        )

    token = auth_header.removeprefix("Bearer ").strip()

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("userId")

        if not user_id:
            raise HTTPException(status_code=401, detail="Token missing userId")

        # Fetch user from DB
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return user

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")