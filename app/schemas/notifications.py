# schemas.py
from pydantic import BaseModel
from datetime import datetime

class NotificationBase(BaseModel):
    type: str
    title: str
    message: str
    data: str  # JSON data as string

class NotificationCreate(NotificationBase):
    user_id: int

class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    is_read: bool
    created_at: datetime
    
    class Config:
        orm_mode = True
        