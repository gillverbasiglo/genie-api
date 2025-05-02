from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime

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

class Archetype(BaseModel):
    name: str
    similarity_score: float

class Keyword(BaseModel):
    name: str
    similarity_score: float

class MeUserResponse(UserCreate):
    id: str
    created_at: datetime
    invited_by: Optional[str] = None
    archetypes: Optional[List[Archetype]] = None
    keywords: Optional[List[Keyword]] = None

class UserFriendResponse(UserCreate):
    archetypes: Optional[List[str]]
    keywords: Optional[List[str]]

class UpdateArchetypesAndKeywordsRequest(BaseModel):
    archetypes: List[str]
    keywords: List[str]