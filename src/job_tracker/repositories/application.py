from typing import Optional
from sqlalchemy.orm import Session
from .base import BaseRepository
from ..models.application import Application


class ApplicationRepository(BaseRepository[Application]):
    """Repository handling database operations for the Application model."""

    def __init__(self, db: Session):
        super().__init__(Application, db)

    def get_by_message_id(self, gmail_message_id: str) -> Optional[Application]:
        """Retrieves an application that matches the specific Gmail message ID.

        Args:
            gmail_message_id: The unique Gmail message identifier.

        Returns:
            The Application if found, else None.
        """
        if not gmail_message_id:
            return None
        return self.db.query(self.model).filter(self.model.gmail_message_id == gmail_message_id).first()
