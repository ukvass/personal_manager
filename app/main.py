# >>> PATCH: app/main.py
# Changes:
# - Call run_startup_migrations(engine) after metadata.create_all().
# - Everything else kept as-is.

from fastapi import FastAPI, HTTPException, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
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

tags_metadata = [
    {"name": "auth", "description": "Authentication: register, login, me."},
    {"name": "tasks", "description": "Task management: CRUD, filters, bulk operations."},
]

app = FastAPI(
    title="Personal Manager API",
    version="1.0.0",
    description=(
        "Versioned JSON API exposed under /api/v1. "
        "Use OAuth2 password flow to obtain a Bearer token and access protected endpoints."
    ),
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)


@app.get("/health")
def health():
    """Simple healthcheck endpoint."""
    return {"status": "ok"}


# Serve static from the *package* directory app/static, robust to CWD
static_dir = ilres.files("app").joinpath("static")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Mount routers
# Hide legacy JSON endpoints from the schema to make /api/v1 canonical
app.include_router(auth_router.router, include_in_schema=False)
app.include_router(tasks.router, include_in_schema=False)
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
        csp = settings.SECURITY_CSP
        path = request.url.path
        if path.startswith("/docs") or path.startswith("/redoc"):
            # Swagger/ReDoc need inline scripts and styles + CDN assets
            csp = (
                "default-src 'self'; "
                "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com 'unsafe-inline'; "
                "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
                "img-src 'self' https: data:; "
                "font-src 'self' https://cdn.jsdelivr.net data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )
        # Always set/override CSP for clarity on these routes
        response.headers["Content-Security-Policy"] = csp
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


# --- Legacy route deprecation helper ----------------------------------------

@app.middleware("http")
async def legacy_api_deprecation(request: Request, call_next):
    """Hard redirect legacy JSON endpoints (/auth, /tasks) to /api/v1 with 308.

    Preserves method and body; keeps query string intact.
    """
    path = request.url.path
    if not path.startswith("/api/v1") and (path.startswith("/auth") or path.startswith("/tasks")):
        successor = "/api/v1" + path
        if request.url.query:
            successor = successor + "?" + request.url.query
        from fastapi.responses import RedirectResponse as _RR
        return _RR(url=successor, status_code=308)
    return await call_next(request)
