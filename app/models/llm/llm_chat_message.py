import enum
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from sqlalchemy import Text

from app.models.llm.llm_chat_session import LLMChatSession

class Sender(str, enum.Enum):
    user = "user"
    llm = "llm"

class LLMChatMessage(Base):
    __tablename__ = "llm_chat_messages"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("llm_chat_sessions.id"), nullable=False)
    sender = Column(Enum(Sender, name="sender"), nullable=False)
    content = Column(Text, nullable=False)  # <-- Updated
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship(LLMChatSession, back_populates="messages")
