from typing import Optional
from sqlalchemy.orm import Session
from .base import BaseRepository
from ..models.processing_run import ProcessingRun


class ProcessingRunRepository(BaseRepository[ProcessingRun]):
    """Repository handling database operations for the ProcessingRun model."""

    def __init__(self, db: Session):
        super().__init__(ProcessingRun, db)

    def get_latest_run(self) -> Optional[ProcessingRun]:
        """Retrieves the latest execution run telemetry log."""
        return self.db.query(self.model).order_by(self.model.start_time.desc()).first()
