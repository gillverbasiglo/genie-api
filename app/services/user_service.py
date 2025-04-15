from app.models import User
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional

def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    query = select(User).where(User.id == user_id)
    return db.execute(query).scalar_one_or_none()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    query = select(User).where(User.email == email)
    return db.execute(query).scalar_one_or_none()

def get_user_by_phone(db: Session, phone: str) -> Optional[User]:
    query = select(User).where(User.phone == phone)
    return db.execute(query).scalar_one_or_none()

def create_user(db: Session, user: User) -> User:
    db.add(user)
    db.commit()
