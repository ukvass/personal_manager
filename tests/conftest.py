# tests/conftest.py
# PURPOSE: create a TestClient and override DB dependency to use a temp SQLite file.

# Ensure project root is on sys.path so `import app` works when running pytest.
import sys, os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db import Base  # DB metadata
from app.main import app  # FastAPI app
from app.store_db import get_db  # original dependency to override


@pytest.fixture()
def client():
    # 1) Create a temporary SQLite file (so data is isolated per test run)
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    test_db_url = f"sqlite:///{tmp.name}"

    # 2) Create a new engine/session factory for tests
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 3) Create tables for tests
    Base.metadata.create_all(bind=engine)

    # 4) Override the app's get_db dependency to use our TestingSessionLocal
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # 5) Yield a TestClient (context manager ensures proper startup/shutdown)
    with TestClient(app) as c:
        yield c

    # 6) Cleanup: remove overrides, drop tables, dispose engine, delete temp file
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    os.unlink(tmp.name)
