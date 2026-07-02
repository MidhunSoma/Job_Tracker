from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from ..database.base import Base


class RawEmail(Base):
    """SQLAlchemy model representing the raw content of an ingested email and its AI pipeline processing state."""

    __tablename__ = "raw_emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String, unique=True, nullable=False, index=True)
    thread_id = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=True)
    sender = Column(String, nullable=False)
    received_at = Column(DateTime, nullable=False)
    snippet = Column(Text, nullable=True)
    body = Column(Text, nullable=True)
    
    # AI processing pipeline queue state: NEW, CLASSIFYING, EXTRACTING, COMPLETED, FAILED, IGNORED, DEAD_LETTER
    processing_state = Column(String, default="NEW", nullable=False, index=True)
    classification = Column(String, default="unclassified", nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    
    # Dead Letter Queue retry counter
    retry_count = Column(Integer, default=0, nullable=False)
    
    # LLM Telemetry and Auditing Columns
    raw_llm_json = Column(Text, nullable=True)
    prompt_version = Column(String, nullable=True)
    model = Column(String, nullable=True)
    temperature = Column(Float, nullable=True)
    token_usage = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def gmail_link(self) -> str:
        """Constructs a direct hyperlink to the email thread in the Gmail UI."""
        return f"https://mail.google.com/mail/u/0/#inbox/{self.thread_id}"

    def __repr__(self) -> str:
        return f"<RawEmail(id={self.id}, message_id='{self.message_id}', state='{self.processing_state}', retry={self.retry_count})>"
