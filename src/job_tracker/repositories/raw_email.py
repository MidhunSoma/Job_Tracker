from typing import List, Optional
from sqlalchemy.orm import Session
from .base import BaseRepository
from ..models.raw_email import RawEmail


class RawEmailRepository(BaseRepository[RawEmail]):
    """Repository handling database operations for the RawEmail model."""

    def __init__(self, db: Session):
        super().__init__(RawEmail, db)

    def get_by_message_id(self, message_id: str) -> Optional[RawEmail]:
        """Retrieves a RawEmail record that matches the specific Gmail message ID."""
        if not message_id:
            return None
        return self.db.query(self.model).filter(self.model.message_id == message_id).first()

    def get_unprocessed_emails(self) -> List[RawEmail]:
        """Retrieves all RawEmail records that are in NEW or FAILED processing state."""
        return (
            self.db.query(self.model)
            .filter(self.model.processing_state.in_(["NEW", "FAILED"]))
            .order_by(self.model.received_at.asc())
            .all()
        )
