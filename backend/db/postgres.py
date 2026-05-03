"""SQLAlchemy setup for PostgreSQL structured storage."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import settings


def _build_db_url(url: str) -> str:
    """Ensure sslmode=require is present — Supabase pooler requires it."""
    if "sslmode" not in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}sslmode=require"
    return url


# use_native_hstore=False stops psycopg2 from running the hstore OID introspection
# query on every new connection. Supabase Transaction Pooler (port 6543) closes
# the SSL connection during that query, causing OperationalError on connect.
engine = create_engine(
    _build_db_url(settings.database_url),
    use_native_hstore=False,
    pool_pre_ping=True,
    future=True,
    pool_recycle=55,
    pool_size=3,
    max_overflow=2,
    pool_timeout=10,
    connect_args={
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 20,
        "keepalives_interval": 5,
        "keepalives_count": 3,
        "options": "-c statement_timeout=30000",
    },
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield one session per request and always release resources."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
