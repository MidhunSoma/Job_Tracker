from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from ..config.settings import settings

# Extract path and ensure directory exists for SQLite database
if settings.db.url.startswith("sqlite:///"):
    db_path_str = settings.db.url.replace("sqlite:///", "")
    db_path = Path(db_path_str)
    db_path.parent.mkdir(parents=True, exist_ok=True)

# Connection configurations for thread concurrency in SQLite
connect_args = {}
if settings.db.url.startswith("sqlite:///"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.db.url,
    connect_args=connect_args,
    echo=False
)

# Session factory for transaction contexts
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency provider that yields a database session and closes it on cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
