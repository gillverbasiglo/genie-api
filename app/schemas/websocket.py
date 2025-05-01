from enum import Enum
from pydantic import BaseModel
from typing import Union

# Enum for type safety
class WebSocketMessageType(str, Enum):
    FRIEND_REQUEST = "FRIEND_REQUEST"
    FRIEND_REQUEST_ACCEPTED = "FRIEND_REQUEST_ACCEPTED"
    FRIEND_REQUEST_REJECTED = "FRIEND_REQUEST_REJECTED"
    PRIVATE_CHAT_MESSAGE = "newChatMessage"
    MESSAGE_UPDATE = "messageUpdate"
    TYPING_STATUS = "typingStatus"
    SHARED_ITEM = "sharedItem"
    USER_STATUS = "userStatus"
    USER_ACTIVITY = "userActivity"

# Base message schema
class BaseWebSocketMessage(BaseModel):
    type: WebSocketMessageType

# FRIEND_REQUEST message
class FriendRequestMessage(BaseWebSocketMessage):
    type: WebSocketMessageType = WebSocketMessageType.FRIEND_REQUEST
    from_user_id: str
    to_user_id: str

# FRIEND_REQUEST_ACCEPTED message
class FriendRequestAcceptedMessage(BaseWebSocketMessage):
    type: WebSocketMessageType = WebSocketMessageType.FRIEND_REQUEST_ACCEPTED
    from_user_id: str
    to_user_id: str

# FRIEND_REQUEST_REJECTED message
class FriendRequestRejectedMessage(BaseWebSocketMessage):
    type: WebSocketMessageType = WebSocketMessageType.FRIEND_REQUEST_REJECTED
    from_user_id: str
    to_user_id: str

# Union of all message types
WebSocketMessage = Union[
    FriendRequestMessage,
    FriendRequestAcceptedMessage,
    FriendRequestRejectedMessage,
]
