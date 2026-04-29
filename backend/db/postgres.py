"""SQLAlchemy setup for PostgreSQL structured storage."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import settings


engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield one session per request and always release resources."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
