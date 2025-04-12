# schemas.py
from pydantic import BaseModel
from datetime import datetime

class DeviceTokenBase(BaseModel):
    token: str
    platform: str

class DeviceTokenCreate(DeviceTokenBase):
    user_id: str

class DeviceTokenResponse(DeviceTokenBase):
    id: str
    user_id: str
    is_active: bool
    created_at: datetime
    
    class Config:
        orm_mode = True
        
