from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from ..models.application import ApplicationStatus


class StatusHistoryBase(BaseModel):
    """Base schema for application status transition records."""
    old_status: Optional[ApplicationStatus] = Field(None, description="Previous status stage")
    new_status: ApplicationStatus = Field(..., description="Target status stage transitioning to")
    email_subject: Optional[str] = Field(None, description="Triggering email subject")
    email_date: Optional[datetime] = Field(None, description="Triggering email received time")
    gmail_message_id: Optional[str] = Field(None, description="Gmail Message ID tracking reference")
    llm_reason: Optional[str] = Field(None, description="LLM reasoning behind the status classification")
    
    # Confidence metrics
    status_confidence: Optional[float] = Field(None, description="Confidence of target status extraction")
    overall_confidence: Optional[float] = Field(None, description="Overall LLM extraction confidence")
    
    # Flag indicating whether this update required candidate inspection
    needs_review: bool = Field(default=False, description="True if this specific status transition was marked for manual review")
    
    notes: Optional[str] = Field(None, description="Audit transition notes")


class StatusHistoryCreate(StatusHistoryBase):
    """Schema for creating a new status history log entry."""
    application_id: int = Field(..., description="Foreign key application ID")


class StatusHistoryResponse(StatusHistoryBase):
    """Response schema for serializing a status history timeline entry."""
    id: int = Field(..., description="Unique status entry database ID")
    application_id: int = Field(..., description="Linked Application ID")
    changed_at: datetime = Field(..., description="Timestamp of status update")

    model_config = {
        "from_attributes": True
    }
