from pydantic import BaseModel
from typing import Optional
from enum import Enum

class UserCreate(BaseModel):
    phone_number: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    invite_code: Optional[str] = None  # To track who invited them

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BANNED = "banned"