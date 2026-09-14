"""SQLAlchemy engine, session factory and declarative base."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import settings

_engine_kwargs: dict = {"pool_pre_ping": True, "future": True}
if not settings.database_url.startswith("sqlite"):
    # SQLite's default pool (SingletonThreadPool/NullPool) doesn't accept
    # pool_size/max_overflow. Production always uses MySQL; SQLite is only
    # ever used for local/test runs (see backend/tests/conftest.py).
    _engine_kwargs["pool_size"] = settings.db_pool_size
    _engine_kwargs["max_overflow"] = settings.db_max_overflow

engine = create_engine(settings.database_url, **_engine_kwargs)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session]:
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Used by /ready. Returns True if a simple query succeeds."""
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return True
    except Exception:  # noqa: BLE001 - /ready must report False on *any* DB failure
        return False
