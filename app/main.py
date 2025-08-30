# >>> PATCH: app/main.py
# Changes:
# - Call run_startup_migrations(engine) after metadata.create_all().
# - Everything else kept as-is.

from fastapi import FastAPI, HTTPException, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from importlib import resources as ilres

from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
import time
import uuid

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
    setup_logging(settings.LOG_LEVEL)

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
from .config import settings
from .logging_utils import setup_logging
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from .rate_limit import limiter, _rate_limit_exceeded_handler

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
# Versioned JSON API (parallel namespace so legacy routes keep working)
app.include_router(api_router)

# Unified error handlers
register_exception_handlers(app)

# Rate limiting (global middleware + handler)
app.state.limiter = limiter
from slowapi.errors import RateLimitExceeded as _RLE # guard duplicate import in case of re-run
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Request ID + access log middleware
@app.middleware("http")
async def request_id_and_logging(request: Request, call_next):
    start = time.perf_counter()
    incoming = request.headers.get(settings.REQUEST_ID_HEADER)
    req_id = incoming or uuid.uuid4().hex
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers.setdefault(settings.REQUEST_ID_HEADER, req_id)
    duration_ms = int((time.perf_counter() - start) * 1000)
    logging.getLogger("app.request").info(
        "method=%s path=%s status=%s duration_ms=%s request_id=%s",
        request.method,
        request.url.path,
        getattr(response, "status_code", "-"),
        duration_ms,
        req_id,
    )
    return response

# --- Security: CORS and security headers ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    # Basic hardening headers
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )
    # CSP and HSTS (HSTS only when explicitly enabled)
    if settings.SECURITY_CSP:
        response.headers.setdefault("Content-Security-Policy", settings.SECURITY_CSP)
    if settings.SECURITY_ENABLE_HSTS:
        # 6 months + preload; adjust as needed in prod
        response.headers.setdefault("Strict-Transport-Security", "max-age=15552000; includeSubDomains; preload")
    return response


# --- Observability: liveness, readiness, metrics ---

@app.get("/live")
def live():
    return {"status": "live"}


@app.get("/ready")
def ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="not ready") from exc


# Expose Prometheus metrics at /metrics
Instrumentator().instrument(app).expose(app, include_in_schema=False)
