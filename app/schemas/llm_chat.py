from enum import Enum
from pydantic import BaseModel
from typing import Dict, Literal, List, Optional, Union
from datetime import datetime

class Sender(str, Enum):
    user = "user"
    llm = "llm"


class SaveChatRequest(BaseModel):
    session_id: str
    is_new_session: bool 
    sender: Sender
    content: str  

class ChatMessageResponse(BaseModel):
    id: str
    sender: Sender
    content: str
    created_at: datetime

class PaginatedChatMessages(BaseModel):
    total: int
    messages: List[ChatMessageResponse]

class SaveChatResponse(BaseModel):
    message: str
    session_id: str

