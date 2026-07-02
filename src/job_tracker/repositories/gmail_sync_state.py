from typing import Optional
from sqlalchemy.orm import Session
from .base import BaseRepository
from ..models.gmail_sync_state import GmailSyncState


class GmailSyncStateRepository(BaseRepository[GmailSyncState]):
    """Repository handling database operations for the GmailSyncState model."""

    def __init__(self, db: Session):
        super().__init__(GmailSyncState, db)

    def get_latest_state(self) -> Optional[GmailSyncState]:
        """Retrieves the latest synchronized checkpoint state from the database."""
        return self.db.query(self.model).order_by(self.model.last_sync_time.desc()).first()
