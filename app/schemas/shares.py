# schemas.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ShareBase(BaseModel):
    content_id: str
    content_type: str
    message: Optional[str] = None
    title: Optional[str] = None

class ShareCreate(ShareBase):
    to_user_id: str

class ResponsePayload(BaseModel):
    success: bool
    message: str
    apnsId: Optional[str] = None
    apnsUniqueId: Optional[str] = None

class NotificationResponse(BaseModel):
    device_token: str
    status_code: int
    response: ResponsePayload

class ShareResponse(ShareBase):
    id: str
    from_user_id: str
    to_user_id: str
    created_at: datetime
    notification_responses: List[NotificationResponse]
    
    class Config:
        from_attributes = True
        
