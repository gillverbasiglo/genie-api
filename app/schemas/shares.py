# schemas.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ShareBase(BaseModel):
    content_id: str
    content_type: str
    message: Optional[str] = None
    title: Optional[str] = None

class ShareCreate(ShareBase):
    to_user_id: str

class ShareResponse(ShareBase):
    id: str
    from_user_id: str
    to_user_id: str
    created_at: datetime
    
    class Config:
        orm_mode = True
        
