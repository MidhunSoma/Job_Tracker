from typing import List
from sqlalchemy.orm import Session
from .base import BaseRepository
from ..models.status_history import StatusHistory


class StatusHistoryRepository(BaseRepository[StatusHistory]):
    """Repository handling database operations for the StatusHistory model."""

    def __init__(self, db: Session):
        super().__init__(StatusHistory, db)

    def get_by_application_id(self, application_id: int) -> List[StatusHistory]:
        """Retrieves all status history entries for a specific application, sorted by date.

        Args:
            application_id: The ID of the application.

        Returns:
            A list of StatusHistory records.
        """
        return (
            self.db.query(self.model)
            .filter(self.model.application_id == application_id)
            .order_by(self.model.changed_at.desc())
            .all()
        )
