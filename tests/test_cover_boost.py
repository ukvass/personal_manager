import logging
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from jose import jwt

from app.api import deps as api_deps
from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.config import settings
from app.db import Base
from app.db_models import UserDB
from app.logging_utils import setup_logging


def test_api_deps_parsers():
    # status
    assert api_deps.parse_status(None) is None
    assert api_deps.parse_status("") is None
    assert api_deps.parse_status("todo") == "todo"
    with pytest.raises(Exception):
        api_deps.parse_status("nope")

    # priority
    assert api_deps.parse_priority(None) is None
    assert api_deps.parse_priority("7") == 7
    with pytest.raises(Exception):
        api_deps.parse_priority("x")

    # order_by
    assert api_deps.parse_order_by(None) == "created_at"
    assert api_deps.parse_order_by("status") == "status"
    with pytest.raises(Exception):
        api_deps.parse_order_by("foo")

    # order_dir (with dependency order_by provided explicitly)
    assert api_deps.parse_order_dir(None, order_by="priority") == "desc"
    assert api_deps.parse_order_dir("asc", order_by="priority") == "asc"
    with pytest.raises(Exception):
        api_deps.parse_order_dir("zzz", order_by="created_at")


def test_logging_utils_initializes_and_respects_existing_handlers():
    root = logging.getLogger()
    # Save and clear existing handlers to hit initialization branch
    saved = list(root.handlers)
    try:
        for h in saved:
            root.removeHandler(h)
        setup_logging("INFO")
        assert root.handlers, "setup_logging should add a handler when none present"
        assert root.level == logging.INFO
    finally:
        # Restore original handlers
        for h in list(root.handlers):
            root.removeHandler(h)
        for h in saved:
            root.addHandler(h)

    # Now with existing handlers, it should only adjust level and not add more
    initial_count = len(root.handlers)
    setup_logging("WARNING")
    assert len(root.handlers) == initial_count
    assert root.level == logging.WARNING


def test_main_security_headers_and_hsts_toggle(client):
    # Default security headers present
    r = client.get("/")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "no-referrer"
    assert r.headers.get("Permissions-Policy") is not None
    assert r.headers.get("Content-Security-Policy") is not None

    # Docs route should have relaxed CSP
    r_docs = client.get("/docs")
    csp = r_docs.headers.get("Content-Security-Policy", "")
    assert "cdn.jsdelivr.net" in csp and "unsafe-inline" in csp

    # Enable HSTS temporarily and verify header appears
    orig = settings.SECURITY_ENABLE_HSTS
    try:
        settings.SECURITY_ENABLE_HSTS = True
        r2 = client.get("/")
        assert r2.headers.get("Strict-Transport-Security", "").startswith("max-age=")
    finally:
        settings.SECURITY_ENABLE_HSTS = orig


def test_ready_unhealthy_returns_503(client, monkeypatch):
    # Cause engine.connect() to raise to hit the 503 path
    import app.main as main_mod

    def boom():  # not a context manager; raising at call site is fine
        raise RuntimeError("DB down")

    monkeypatch.setattr(main_mod.engine, "connect", boom)
    r = client.get("/ready")
    assert r.status_code == 503


# Legacy non-versioned API routes and redirect middleware were removed.


def test_api_v1_info_endpoint(client):
    r = client.get("/api/v1/")
    assert r.status_code == 200
    data = r.json()
    assert data.get("version") == "v1"
    assert "/api/v1/tasks" in data.get("tasks", "")


def _mk_temp_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def test_auth_password_and_jwt_and_get_current_user():
    # Password hash/verify
    pwd = "secret-xyz"
    ph = hash_password(pwd)
    assert verify_password(pwd, ph)
    assert not verify_password("nope", ph)

    # Prepare DB and user
    db = _mk_temp_session()
    user = UserDB(email="u@example.com", password_hash=ph)
    db.add(user)
    db.commit()

    token = create_access_token("u@example.com")
    me = get_current_user(token=token, db=db)
    assert me.email == "u@example.com"


def test_get_current_user_invalid_and_missing_sub():
    db = _mk_temp_session()

    # Completely invalid token
    with pytest.raises(Exception):
        get_current_user(token="not-a-token", db=db)

    # Validly signed token but without sub
    exp = datetime.now(UTC) + timedelta(minutes=5)
    raw = jwt.encode({"exp": exp}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(Exception):
        get_current_user(token=raw, db=db)


def test_auth_hash_and_verify_edge_cases(monkeypatch):
    # hash_password should raise TypeError on non-string input
    with pytest.raises(TypeError):
        hash_password(123)  # type: ignore[arg-type]

    # verify_password should safely handle bad hash input and return False
    assert verify_password("anything", password_hash=None) is False  # type: ignore[arg-type]


def test_get_db_generator_closes():
    # Exercise get_db generator to hit yield and finally: close()
    from app.auth import get_db as auth_get_db

    gen = auth_get_db()
    db = next(gen)
    # session object has close method
    assert hasattr(db, "close")
    gen.close()  # triggers finally: db.close()


def test_ttl_fallback_and_create_token_with_dict(monkeypatch):
    from app.auth import get_access_token_ttl_minutes

    # Force bad value in settings to trigger fallback
    orig = settings.JWT_EXPIRE_MIN
    try:
        settings.JWT_EXPIRE_MIN = "bad"  # type: ignore[assignment]
        assert get_access_token_ttl_minutes() == 60
    finally:
        settings.JWT_EXPIRE_MIN = orig

    # Create token from dict subject (covers setdefault branch)
    tok = create_access_token({"email": "dict@example.com"})
    assert isinstance(tok, str) and tok


def test_get_current_user_subject_not_found():
    # Token with valid signature and sub, but user does not exist in DB
    db = _mk_temp_session()
    token = create_access_token("ghost@example.com")
    with pytest.raises(Exception):
        get_current_user(token=token, db=db)
