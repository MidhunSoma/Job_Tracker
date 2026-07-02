import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from job_tracker.database.base import Base
from job_tracker.config.settings import settings

# Override settings database URL for testing
settings.db.url = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    """Session-wide engine for in-memory SQLite database."""
    test_engine = create_engine(
        settings.db.url,
        connect_args={"check_same_thread": False}
    )
    yield test_engine


@pytest.fixture(scope="function")
def db_session(engine) -> Session:
    """Function-scoped session creating and dropping tables for clean test isolation."""
    # Create tables for this test run
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    # Clean up tables after the test run
    Base.metadata.drop_all(bind=engine)
