from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class EmailMetadata(BaseModel):
    """Pydantic model representing raw email metadata fetched from Gmail."""
    id: str = Field(..., description="Unique Gmail message identifier")
    thread_id: str = Field(..., description="Gmail thread identifier")
    subject: str = Field(..., description="Email subject line")
    sender_name: Optional[str] = Field(None, description="Extracted sender display name")
    sender_email: str = Field(..., description="Sender email address")
    date: datetime = Field(..., description="Date and time when the email was received")
    body: str = Field(..., description="Full text body content of the email")
    gmail_link: str = Field(..., description="Direct hyperlink to the Gmail message thread")


class EmailExtractionResult(BaseModel):
    """Pydantic model representing structured job information extracted by the LLM."""
    company: str = Field(..., description="Fuzzy matched or exact company name")
    role: str = Field(..., description="Job role or title applied for")
    extracted_status: str = Field(..., description="Hiring stage status detected from the email text")
    recruiter_name: Optional[str] = Field(None, description="Name of the recruiter or sender if found")
    recruiter_email: Optional[str] = Field(None, description="Email of the recruiter if found")
    applied_date: Optional[datetime] = Field(None, description="Explicit date of application if mentioned")
    notes: Optional[str] = Field(None, description="Additional context or email summary notes")
    raw_email_id: str = Field(..., description="Reference back to the processed Gmail message ID")
    
    # Confidence metrics
    company_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score for Company")
    role_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score for Role")
    status_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score for Status")
    overall_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Overall LLM parsing confidence score")
