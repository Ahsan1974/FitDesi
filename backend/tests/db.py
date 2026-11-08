"""Shared in-memory database for API tests. Import this module, not conftest."""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DEBUG"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["SEED_DEMO"] = "false"
os.environ["ADMIN_EMAIL"] = ""
os.environ["ADMIN_PASSWORD"] = ""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.models.entities import Base

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def override_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def bind_app(app) -> None:
    app.dependency_overrides[get_db] = override_db
