from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from ..database.base import Base


class GmailSyncState(Base):
    """SQLAlchemy model representing the Gmail synchronization checkpoint coordinates."""

    __tablename__ = "gmail_sync_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    last_history_id = Column(String, nullable=True)
    last_sync_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_processed_message_id = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<GmailSyncState(id={self.id}, last_history_id='{self.last_history_id}', last_sync_time='{self.last_sync_time}')>"
