# schemas.py
from pydantic import BaseModel
from typing import Any, Dict, Optional, List, Union
from datetime import datetime

from app.schemas.users import MeUserResponse

class ShareBase(BaseModel):
    content_id: str
    content_type: str
    message: Optional[str] = None
    title: Optional[str] = None

class ShareCreate(ShareBase):
    to_user_id: str

class ShareListResponse(BaseModel):
    id: str
    from_user: MeUserResponse
    to_user_id: str
    created_at: datetime
    content_id: str
    content_type: str
    is_Seen: bool
    message: Optional[str] = None
    title: Optional[str] = None

class ResponsePayload(BaseModel):
    success: Optional[bool] = None
    message: Optional[str] = None
    apnsId: Optional[str] = None
    apnsUniqueId: Optional[str] = None
    error: Optional[str] = None
    details: Optional[Union[str, Dict[str, Any]]] = None

class NotificationResponse(BaseModel):
    device_token: str
    status_code: int
    response: Optional[ResponsePayload] = None
    error: Optional[str] = None

class ShareResponse(ShareBase):
    id: str
    from_user_id: str
    to_user_id: str
    created_at: datetime
    is_Seen: bool
    notification_responses: List[NotificationResponse]
    
    class Config:
        from_attributes = True
        
