from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import relationship
from ..database.base import Base


class StatusHistory(Base):
    """SQLAlchemy model representing a Status Transition History log with email and review context."""

    __tablename__ = "status_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    
    old_status = Column(String, nullable=True)
    new_status = Column(String, nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Audit trail and debugging details from emails
    email_subject = Column(String, nullable=True)
    email_date = Column(DateTime, nullable=True)
    gmail_message_id = Column(String, nullable=True, index=True)
    llm_reason = Column(Text, nullable=True)
    
    # Confidence scores for this specific event transition
    status_confidence = Column(Float, nullable=True)
    overall_confidence = Column(Float, nullable=True)
    
    # Flag indicating whether this status update requested manual review
    needs_review = Column(Boolean, default=False, nullable=False, index=True)
    
    notes = Column(Text, nullable=True)

    # Relationships
    application = relationship("Application", back_populates="status_history")

    def __repr__(self) -> str:
        return (
            f"<StatusHistory(id={self.id}, application_id={self.application_id}, "
            f"old_status='{self.old_status}', new_status='{self.new_status}', needs_review={self.needs_review})>"
        )
