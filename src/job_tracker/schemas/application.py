from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from ..models.application import ApplicationStatus
from .status import StatusHistoryResponse


class ApplicationBase(BaseModel):
    """Base application properties."""
    company: str = Field(..., description="Company name")
    role: str = Field(..., description="Applied role title")
    status: ApplicationStatus = Field(..., description="Current status of the application (one of the validated stages)")
    applied_date: Optional[datetime] = Field(None, description="Date applied")
    recruiter_name: Optional[str] = Field(None, description="Name of recruiter")
    recruiter_email: Optional[str] = Field(None, description="Email of recruiter")
    gmail_message_id: Optional[str] = Field(None, description="Gmail Message ID")
    gmail_thread_id: Optional[str] = Field(None, description="Gmail Thread ID")
    gmail_link: Optional[str] = Field(None, description="Gmail hyperlink")
    application_source: Optional[str] = Field(None, description="Source (e.g. LinkedIn)")
    resume_used: Optional[str] = Field(None, description="Resume file name")
    is_active: bool = Field(default=True, description="Whether the application is active")
    
    # Confidence metrics
    company_confidence: Optional[float] = Field(None, description="Company extraction confidence")
    role_confidence: Optional[float] = Field(None, description="Role extraction confidence")
    status_confidence: Optional[float] = Field(None, description="Status extraction confidence")
    overall_confidence: Optional[float] = Field(None, description="Overall parsing confidence")
    
    # Flag requesting manual user inspection
    needs_review: bool = Field(default=False, description="True if application requires candidate review")
    
    notes: Optional[str] = Field(None, description="Miscellaneous notes")


class ApplicationCreate(ApplicationBase):
    """Schema for creating a new job application."""
    pass


class ApplicationUpdate(BaseModel):
    """Schema for updating an existing job application status and fields."""
    status: Optional[ApplicationStatus] = Field(None, description="Updated job application status")
    applied_date: Optional[datetime] = Field(None, description="Override applied date")
    recruiter_name: Optional[str] = Field(None, description="Update recruiter name")
    recruiter_email: Optional[str] = Field(None, description="Update recruiter email")
    gmail_message_id: Optional[str] = Field(None, description="Update Gmail Message ID")
    gmail_thread_id: Optional[str] = Field(None, description="Update Gmail Thread ID")
    gmail_link: Optional[str] = Field(None, description="Update Gmail Link")
    application_source: Optional[str] = Field(None, description="Update application source")
    resume_used: Optional[str] = Field(None, description="Update resume name")
    last_email_date: Optional[datetime] = Field(None, description="Last email timestamp received")
    is_active: Optional[bool] = Field(None, description="Set activity state")
    
    # Confidence updates
    company_confidence: Optional[float] = Field(None, description="Update company confidence")
    role_confidence: Optional[float] = Field(None, description="Update role confidence")
    status_confidence: Optional[float] = Field(None, description="Update status confidence")
    overall_confidence: Optional[float] = Field(None, description="Update overall confidence")
    
    needs_review: Optional[bool] = Field(None, description="Update review requirement status")
    
    notes: Optional[str] = Field(None, description="Append or replace notes")


class ApplicationResponse(ApplicationBase):
    """Schema for serializing a complete job application, including history."""
    id: int = Field(..., description="Unique application DB entry ID")
    last_updated: datetime = Field(..., description="Timestamp of last update")
    created_at: datetime = Field(..., description="Database record creation timestamp")
    updated_at: datetime = Field(..., description="Database record last update timestamp")
    last_email_date: Optional[datetime] = Field(None, description="Timestamp of the latest job email processed")
    status_history: List[StatusHistoryResponse] = Field(default=[], description="List of all status changes")

    model_config = {
        "from_attributes": True
    }
