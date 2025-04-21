from pydantic import BaseModel
from typing import Optional

class UserCreate(BaseModel):
    phone_number: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    invite_code: Optional[str] = None  # To track who invited them