from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class InvitationCreate(BaseModel):
    invitee_phone: str
    invitee_email: Optional[EmailStr] = None

class InvitationResponse(BaseModel):
    id: str
    inviter_id: str
    invitee_phone: str
    invitee_email: Optional[str]
    invite_code: str
    status: str
    created_at: datetime
    accepted_at: Optional[datetime]
    invitee_id: Optional[str]

    class Config:
        from_attributes = True

class ContactCheckResponse(BaseModel):
    phone_number: str
    is_registered: bool
    is_invited: bool
    user_id: Optional[str]
    display_name: Optional[str]
    invite_code: Optional[str]
    invited_at: Optional[datetime]

    class Config:
        from_attributes = True 