"""Database configuration and session management for Supabase PostgreSQL.

Implements cached/shared SQLAlchemy Engine and SessionLocal session factory.
Uses NullPool connection strategy suitable for external poolers (Supabase Transaction Pooler)
and serverless environments (Vercel) to avoid client-side connection leaks.
"""

from typing import Generator, Optional
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

Base = declarative_base()

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """Retrieve shared, cached SQLAlchemy engine configured for Supabase Transaction Pooler.

    Uses NullPool and pool_pre_ping to avoid maintaining a large client-side pool,
    making it ideal for serverless environments (Vercel) and external PgBouncer poolers.
    Never logs or exposes DATABASE_URL in exception messages.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        if not url:
            raise ValueError("DATABASE_URL is not configured in settings.")
        _engine = create_engine(
            url,
            poolclass=NullPool,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    """Retrieve shared session factory bound to the cached engine."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )
    return _session_factory


def SessionLocal() -> Session:
    """Create a new database session from the shared session factory."""
    factory = get_session_factory()
    return factory()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session and ensuring proper close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

