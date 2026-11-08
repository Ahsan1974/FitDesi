import os
import shutil
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

def _database_url() -> str:
    url = get_settings().database_url
    if os.environ.get("VERCEL") and url.startswith("sqlite"):
        bundled = Path(__file__).resolve().parents[2] / "fitdesi.db"
        target = Path("/tmp/fitdesi.db")
        if bundled.exists() and not target.exists():
            shutil.copy(bundled, target)
        return "sqlite:////tmp/fitdesi.db"
    return url


_url = _database_url()
connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}
engine = create_engine(_url, connect_args=connect_args, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
