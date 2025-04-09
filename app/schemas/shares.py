# schemas.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ShareBase(BaseModel):
    content_id: int
    content_type: str
    message: Optional[str] = None

class ShareCreate(ShareBase):
    from_user_id: int
    to_user_id: int

class ShareResponse(ShareBase):
    id: int
    from_user_id: int
    to_user_id: int
    created_at: datetime
    
    class Config:
        orm_mode = True
