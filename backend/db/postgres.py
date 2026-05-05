"""SQLAlchemy setup for PostgreSQL structured storage."""

from collections.abc import Generator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from config import settings


def _build_db_url(url: str) -> str:
    """Return a Supabase-safe Postgres URL."""
    if not url:
        return url

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["sslmode"] = "require"

    hostname = parts.hostname or ""
    if hostname.endswith(".pooler.supabase.com"):
        query.setdefault("gssencmode", "disable")

    return urlunsplit((
        parts.scheme,
        parts.netloc,
        parts.path,
        urlencode(query),
        parts.fragment,
    ))


def _uses_supabase_pooler(url: str) -> bool:
    """Detect Supavisor pooler hosts."""
    try:
        parts = urlsplit(url)
        hostname = parts.hostname or ""
        return hostname.endswith(".pooler.supabase.com")
    except ValueError:
        return False


db_url = _build_db_url(settings.database_url)
connect_args = {
    "connect_timeout": 20,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
}

engine_kwargs = {
    "use_native_hstore": False,
    "future": True,
    "connect_args": connect_args,
}

if _uses_supabase_pooler(db_url):
    # Supavisor already pools connections. Do not layer SQLAlchemy's QueuePool
    # or session-level SET options on top of it.
    engine_kwargs["poolclass"] = NullPool
else:
    connect_args["options"] = "-c statement_timeout=60000"
    engine_kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_recycle": 180,
            "pool_size": 5,
            "max_overflow": 5,
            "pool_timeout": 20,
        }
    )


engine = create_engine(db_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield one session per request and always release resources."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
