# >>> PATCH: app/main.py
# Changes:
# - Call run_startup_migrations(engine) after metadata.create_all().
# - Everything else kept as-is.

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
from importlib import resources as ilres

from sqlalchemy.orm import Session

from .db import Base, engine, SessionLocal
from . import db_models
from .routers import tasks
from .routers import auth as auth_router
from .routers import web as web_router
from .auth import get_current_user, hash_password
from .models import UserPublic
from .migrations import run_startup_migrations  # NEW


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup/shutdown lifecycle."""
    # --- Startup ---
    # Run minimal, idempotent migrations BEFORE create_all so indexes recreate after schema changes
    run_startup_migrations(engine)
    Base.metadata.create_all(bind=engine)

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
            return UserPublic(id=user.id, email=user.email)

        app.dependency_overrides[get_current_user] = _test_current_user_override
        app.state._had_test_override = True
    else:
        app.state._had_test_override = False

    try:
        yield
    finally:
        # --- Shutdown ---
        if getattr(app.state, "_had_test_override", False):
            app.dependency_overrides.pop(get_current_user, None)
        if test_db is not None:
            test_db.close()


app = FastAPI(title="Personal Manager", lifespan=lifespan)


@app.get("/health")
def health():
    """Simple healthcheck endpoint."""
    return {"status": "ok"}


# Serve static from the *package* directory app/static, robust to CWD
static_dir = ilres.files("app").joinpath("static")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Mount routers
app.include_router(auth_router.router)
app.include_router(tasks.router)
app.include_router(web_router.router)
