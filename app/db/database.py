"""Database configuration and session management for Supabase PostgreSQL.

Will be fully connected in Phase 3 according to design.md.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings

Base = declarative_base()


def get_engine():
    """Retrieve SQLAlchemy engine with pool_pre_ping enabled."""
    settings = get_settings()
    url = settings.database_url
    if not url:
        raise ValueError("DATABASE_URL environment variable is not set.")
    return create_engine(url, pool_pre_ping=True)


def get_db():
    """Dependency helper to yield database session."""
    engine = get_engine()
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
