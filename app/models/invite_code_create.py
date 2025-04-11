from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class InviteCodeCreate(BaseModel):
    code: str
    expires_at: Optional[datetime] = None
    is_active: bool = True
