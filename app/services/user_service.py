from app.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    query = select(User).where(User.id == user_id)
    query = await db.execute(query)
    return query.scalar_one_or_none()

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    query = select(User).where(User.email == email)
    query = await db.execute(query)
    return query.scalar_one_or_none()

async def get_user_by_phone(db: AsyncSession, phone: str) -> Optional[User]:
    query = select(User).where(User.phone == phone)
    query = await db.execute(query)
    return db.execute(query).scalar_one_or_none()

async def create_user(db: AsyncSession, user: User) -> User:
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
