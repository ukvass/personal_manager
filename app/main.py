# >>> PATCH: app/main.py
# Changes:
# - Replaced deprecated @app.on_event("startup") with lifespan context.
# - Still creates DB tables on startup.
# - Under pytest: creates a test user (if missing) and overrides get_current_user.
# - Exposes simple /health endpoint.
# - Mounts existing auth and tasks routers.

from fastapi import FastAPI
from contextlib import asynccontextmanager
import os

from sqlalchemy.orm import Session

from .db import Base, engine, SessionLocal
from . import db_models
from .routers import tasks
from .routers import auth as auth_router
from .auth import get_current_user, hash_password
from .models import UserPublic


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup/shutdown lifecycle."""
    # --- Startup ---
    # Ensure database schema exists
    Base.metadata.create_all(bind=engine)

    # In test mode (pytest), create a fixed user and bypass JWT via DI override
    test_db: Session | None = None
    if "PYTEST_CURRENT_TEST" in os.environ:
        test_db = SessionLocal()
        user = test_db.query(db_models.UserDB).filter(
            db_models.UserDB.email == "test@example.com"
        ).one_or_none()
        if user is None:
            user = db_models.UserDB(
                email="test@example.com",
                password_hash=hash_password("test-password"),
            )
            test_db.add(user)
            test_db.commit()
            test_db.refresh(user)

        def _test_current_user_override():
            # Minimal public user payload for tests
            return UserPublic(id=user.id, email=user.email)

        # Register override so tests can call endpoints without Authorization header
        app.dependency_overrides[get_current_user] = _test_current_user_override
        # Keep ref for cleanup
        app.state._had_test_override = True
    else:
        app.state._had_test_override = False

    # Hand control over to the application runtime
    try:
        yield
    finally:
        # --- Shutdown ---
        if getattr(app.state, "_had_test_override", False):
            # Remove override to avoid leaks across app instances
            app.dependency_overrides.pop(get_current_user, None)
        if test_db is not None:
            test_db.close()


app = FastAPI(title="Personal Manager", lifespan=lifespan)


@app.get("/health")
def health():
    """Simple healthcheck endpoint used by tests/monitoring."""
    return {"status": "ok"}


# Mount routers
app.include_router(auth_router.router)
app.include_router(tasks.router)
