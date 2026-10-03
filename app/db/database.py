"""Database configuration and session management for Supabase PostgreSQL.

Will be fully connected in Phase 3 according to design.md.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

Base = declarative_base()


def get_engine():
    """Retrieve SQLAlchemy engine with pool_pre_ping enabled."""
    url = os.getenv("DATABASE_URL")
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
