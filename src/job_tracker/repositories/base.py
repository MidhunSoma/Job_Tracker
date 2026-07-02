from typing import Generic, Type, TypeVar, List, Optional
from sqlalchemy.orm import Session
from ..database.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Generic repository implementing standard CRUD operations."""

    def __init__(self, model: Type[T], db: Session):
        """Initializes the repository.

        Args:
            model: The SQLAlchemy model class.
            db: The SQLAlchemy Session instance.
        """
        self.model = model
        self.db = db

    def get(self, id: int) -> Optional[T]:
        """Fetches a record by its integer primary key."""
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(self) -> List[T]:
        """Fetches all records in the table."""
        return self.db.query(self.model).all()

    def create(self, obj: T) -> T:
        """Saves a new instance to the database."""
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, obj: T) -> T:
        """Saves modifications of an existing instance to the database."""
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, id: int) -> bool:
        """Deletes a record by id. Returns True if deleted, False otherwise."""
        obj = self.get(id)
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False
