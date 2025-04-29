from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum as PyEnum
from .users import UserFriendResponse, MeUserResponse

class FriendRequestStatus(str, PyEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class ReportType(str, PyEnum):
    SPAM = "spam"
    HARASSMENT = "harassment"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    OTHER = "other"

class FriendRequestBase(BaseModel):
    to_user_id: str

class FriendRequestCreate(FriendRequestBase):
    pass

class GetFriendsRequestResponse(FriendRequestBase):
    id: str
    from_user: MeUserResponse
    to_user: MeUserResponse
    status: FriendRequestStatus
    created_at: datetime
    updated_at: Optional[datetime] = None


class FriendRequestResponse(FriendRequestBase):
    id: str
    from_user_id: str
    status: FriendRequestStatus
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class FriendRequestUpdate(BaseModel):
    status: FriendRequestStatus

class FriendResponse(BaseModel):
    id: str
    user_id: str
    friend_id: str
    created_at: datetime
    friend: UserFriendResponse

    class Config:
        from_attributes = True

class UserBlockBase(BaseModel):
    blocked_id: str
    reason: Optional[str] = None

class UserBlockCreate(UserBlockBase):
    pass

class UserBlockResponse(UserBlockBase):
    id: str
    blocker_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class UserReportBase(BaseModel):
    reported_id: str
    report_type: ReportType
    description: Optional[str] = None

class UserReportCreate(UserReportBase):
    pass

class UserReportResponse(UserReportBase):
    id: str
    reporter_id: str
    created_at: datetime
    status: str
    admin_notes: Optional[str] = None

    class Config:
        from_attributes = True

class FriendStatusResponse(BaseModel):
    is_friend: bool
    friend_request_status: Optional[FriendRequestStatus] = None
    is_blocked: bool
    is_blocked_by: bool
    friend_request_id: Optional[str] = None 


class FriendRequestType(str, PyEnum):
    SENT = "sent"
    RECEIVED = "received"
    ALL = "all"


class BlockListResponse(BaseModel):
    id: str
    blocker_id: str
    blocked_id: str
    reason: str
    created_at: datetime  # or Optional[datetime] if nullable

    class Config:
        orm_mode = True
