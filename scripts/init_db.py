"""Database initialization script.

Creates database tables in Supabase PostgreSQL according to models.py.
"""

import sys
from app.db.database import Base, get_engine
from app.db.models import WeatherForecast, FetchLog  # noqa: F401


def init_database():
    """Create all tables defined in models."""
    try:
        engine = get_engine()
        print("Connecting to PostgreSQL and creating tables...")
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully.")
    except Exception as exc:
        print(f"Database initialization failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    init_database()
