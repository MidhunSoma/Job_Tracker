from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float
from sqlalchemy.orm import relationship
from ..database.base import Base


class ApplicationStatus(str, Enum):
    """Enumeration representing the allowed hiring stages of a job application."""
    APPLIED = "Applied"
    APPLICATION_RECEIVED = "Application Received"
    UNDER_REVIEW = "Under Review"
    SHORTLISTED = "Shortlisted"
    ASSESSMENT_ROUND = "Assessment Round"
    ASSIGNMENT_ROUND = "Assignment Round"
    ONLINE_TEST = "Online Test"
    CODING_CHALLENGE = "Coding Challenge"
    TECHNICAL_INTERVIEW = "Technical Interview"
    HR_INTERVIEW = "HR Interview"
    FINAL_INTERVIEW = "Final Interview"
    INTERVIEW_SCHEDULED = "Interview Scheduled"
    INTERVIEW_COMPLETED = "Interview Completed"
    OFFER_RECEIVED = "Offer Received"
    OFFER_ACCEPTED = "Offer Accepted"
    OFFER_DECLINED = "Offer Declined"
    REJECTED = "Rejected"
    POSITION_CLOSED = "Position Closed"
    WITHDRAWN = "Withdrawn"
    JOINED = "Joined"


class Application(Base):
    """SQLAlchemy model representing a Job Application."""

    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False, index=True)
    
    status = Column(String, nullable=False, index=True)
    
    applied_date = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Recruiter details
    recruiter_name = Column(String, nullable=True)
    recruiter_email = Column(String, nullable=True)
    
    # Gmail tracking fields
    gmail_message_id = Column(String, unique=True, nullable=True, index=True)
    gmail_thread_id = Column(String, nullable=True)
    gmail_link = Column(String, nullable=True)
    
    # Extended auditing and logic fields
    application_source = Column(String, nullable=True)
    resume_used = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_email_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Confidence metrics from LLM parsing
    company_confidence = Column(Float, nullable=True)
    role_confidence = Column(Float, nullable=True)
    status_confidence = Column(Float, nullable=True)
    overall_confidence = Column(Float, nullable=True)
    
    # Flag to request candidate manual inspection (e.g. low-confidence parsing)
    needs_review = Column(Boolean, default=False, nullable=False, index=True)
    
    notes = Column(Text, nullable=True)

    # Relationships
    status_history = relationship(
        "StatusHistory",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="StatusHistory.changed_at.desc()"
    )

    def __repr__(self) -> str:
        return f"<Application(id={self.id}, company='{self.company}', role='{self.role}', status='{self.status}', needs_review={self.needs_review})>"
