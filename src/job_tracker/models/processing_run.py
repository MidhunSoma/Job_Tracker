from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, Text, Float
from ..database.base import Base


class ProcessingRun(Base):
    """SQLAlchemy model representing telemetry and execution metadata for tracking agent runs."""

    __tablename__ = "processing_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    
    emails_scanned = Column(Integer, default=0, nullable=False)
    emails_processed = Column(Integer, default=0, nullable=False)
    new_applications = Column(Integer, default=0, nullable=False)
    updated_applications = Column(Integer, default=0, nullable=False)
    
    errors = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # AI Cost Metrics Tracking
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<ProcessingRun(id={self.id}, scanned={self.emails_scanned}, "
            f"processed={self.emails_processed}, cost_usd=${self.cost_usd:.4f})>"
        )
