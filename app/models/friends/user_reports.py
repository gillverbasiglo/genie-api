from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ...database import Base
from ...schemas.friends import ReportType

class UserReport(Base):
    __tablename__ = "user_reports"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    reporter_id = Column(String, ForeignKey("users.id"), index=True)
    reported_id = Column(String, ForeignKey("users.id"), index=True)
    report_type = Column(Enum(ReportType))
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, default="pending")  # pending, reviewed, resolved
    admin_notes = Column(Text, nullable=True)

    # Relationships
    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="reports_filed")
    reported = relationship("User", foreign_keys=[reported_id], back_populates="reports_received") 
