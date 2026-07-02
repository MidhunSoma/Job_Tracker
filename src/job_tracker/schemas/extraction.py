from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AIJobEmailExtraction(BaseModel):
    """Pydantic schema representing the structured extraction output of the LLM parser.

    Combines classification, extraction, and confidence scores in a single schema.
    """
    is_job_email: bool = Field(
        ...,
        description="True if the email is directly related to a job application, candidate screening, "
                    "technical tests, interviews, status updates, rejections, offers, or negotiations. "
                    "False if it is unrelated (spam, newsletters, marketing job board alerts)."
    )
    company: Optional[str] = Field(
        None,
        description="Cleaned, normalized name of the hiring company (e.g. 'Google', 'Microsoft', 'Netflix'). "
                    "Set to null if not a job email."
    )
    role: Optional[str] = Field(
        None,
        description="Job title/role (e.g., 'Senior AI Engineer', 'Software Developer'). Set to null if not a job email."
    )
    extracted_status: Optional[str] = Field(
        None,
        description="The raw application status or hiring stage mentioned in the email. Set to null if not a job email."
    )
    recruiter_name: Optional[str] = Field(
        None,
        description="Name of the recruiter, coordinator, or contact person who signed or sent the mail. "
                    "Set to null if not a job email."
    )
    recruiter_email: Optional[str] = Field(
        None,
        description="Email address of the recruiter or contact person. Set to null if not a job email."
    )
    applied_date: Optional[datetime] = Field(
        None,
        description="Date of application or event/interview mentioned, formatted in ISO format, else null."
    )
    notes: Optional[str] = Field(
        None,
        description="Concise 1-2 sentence summary of the email's core message. Set to null if not a job email."
    )

    # Confidence Scores
    company_confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Confidence score (0.0 to 1.0) on the company extraction."
    )
    role_confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Confidence score (0.0 to 1.0) on the role extraction."
    )
    status_confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Confidence score (0.0 to 1.0) on the status extraction."
    )
    overall_confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Overall confidence score (0.0 to 1.0) for the classification and extraction."
    )

    # LLM Reasoning
    llm_reason: str = Field(
        ...,
        description="Explain your classification and extraction reasoning, explaining why this email is or "
                    "is not job-related, and how you deduced the hiring stage."
    )
