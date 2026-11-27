"""
Database Connection & Session Management
----------------------------------------
Initializes the SQLAlchemy database engine backed by PostgreSQL,
creates session factories, and provides a dependency generator
(`get_db`) for FastAPI route handlers.

Connection pooling is handled automatically by SQLAlchemy's
QueuePool (the default for PostgreSQL). Pool settings below are
tuned for a small-to-medium production deployment; adjust as needed.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

# SQLite requires 'check_same_thread: False' (threads differ per request).
# PostgreSQL has no such limitation, so we pass an empty dict for it.
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

_engine_kwargs = {
    "connect_args": _connect_args,
    "pool_pre_ping": True,
    "echo": False,
}
if not _is_sqlite:
    _engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 1800,
    })

engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

# SessionLocal: Factory for creating new database sessions per HTTP request
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base: Declarative base class from which all database models inherit
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides an isolated database session per request.

    Yields:
        Session: An active SQLAlchemy database session.

    Ensures:
        The session is guaranteed to close when the HTTP request finishes,
        even if an exception is raised inside the route handler.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
