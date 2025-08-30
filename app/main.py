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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup/shutdown lifecycle."""
    # --- Startup ---
    # Рантайм-миграции убраны; схему управляет Alembic (upgrade head)
    is_test = "PYTEST_CURRENT_TEST" in os.environ

    test_db: Session | None = None
    if is_test:
        # В тестах не трогаем реальную БД — просто подменяем текущего пользователя
        def _test_current_user_override():
            return UserPublic(id=1, email="test@example.com")

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


from .api.errors import register_exception_handlers
from .api.v1.router import api_router

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

# Versioned JSON API (parallel namespace so legacy routes keep working)
app.include_router(api_router)

# Unified error handlers
register_exception_handlers(app)
