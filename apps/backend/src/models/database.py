from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# ---------------------------------------------------------------------------
# Database path — can be overridden via the DB_PATH environment variable.
# Inside Docker the volume is mounted at /app/data.
# ---------------------------------------------------------------------------
def _find_root():
    # Try to find the root by looking for 'apps' directory or stopping at /
    curr = Path(__file__).resolve().parent
    for _ in range(10):
        if (curr / "apps").exists() or (curr / "data").exists():
            return curr
        if curr.parent == curr: # hit root
            break
        curr = curr.parent
    return Path("/app") # Fallback for Docker container runtime

ROOT_DIR = _find_root()
_DEFAULT_DB = ROOT_DIR / "data" / "agent_monitor.db"
DB_PATH = Path(os.environ.get("DB_PATH", str(_DEFAULT_DB)))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    # WAL mode is set via event so every connection inherits it
)

# Enable WAL on every new connection
from sqlalchemy import event as sa_event  # noqa: E402


@sa_event.listens_for(engine, "connect")
def _set_wal(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA synchronous=NORMAL")


SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine, autocommit=False, autoflush=False
)


# ---------------------------------------------------------------------------
# ORM Base & Models
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class CapturedEvent(Base):
    """
    Mirrors the agent-side ``captured_events`` table structure so the backend
    can ingest POSTed event batches and store them in its own database.
    """
    __tablename__ = "captured_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    event_type = Column(String(64), nullable=False, index=True)
    source_process = Column(String(128), nullable=True, index=True)
    raw_json = Column(Text, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CapturedEvent id={self.id} type={self.event_type}>"


def create_all() -> None:
    """Create all tables if they do not exist. Call once at startup."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI dependency that yields a DB session and closes it afterwards.

    Usage::

        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
