# schemas.py
from pydantic import BaseModel
from datetime import datetime

class DeviceTokenBase(BaseModel):
    token: str
    platform: str

class DeviceTokenCreate(DeviceTokenBase):
    user_id: int

class DeviceTokenResponse(DeviceTokenBase):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        orm_mode = True
