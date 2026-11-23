"""
Database Connection & Session Management
----------------------------------------
Initializes the SQLAlchemy database engine, creates session makers,
and provides a dependency generator (`get_db`) for FastAPI route handlers.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

# SQLite requires 'check_same_thread: False' because requests run on different threads.
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

# Database Engine: Manages the connection pool to the underlying SQL database
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

# SessionLocal: Factory for creating new database sessions for incoming HTTP requests
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base: Declarative base class from which all database models inherit
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides an isolated database session per request.

    Yields:
        Session: An active SQLAlchemy database session.

    Ensures:
        The session is guaranteed to close when the HTTP request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
