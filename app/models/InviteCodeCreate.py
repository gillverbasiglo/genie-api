from pydantic import BaseModel
from datetime import datetime

class InviteCodeCreate(BaseModel):
    code: str
    expires_at: datetime | None = None
    is_active: bool = True
