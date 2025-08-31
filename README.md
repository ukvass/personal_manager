# Personal Manager

<!-- Replace OWNER and REPO below with your GitHub org/user and repo names -->
[![CI](https://github.com/ukvass/personal_manager/actions/workflows/ci.yml/badge.svg)](https://github.com/ukvass/personal_manager/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ukvass/personal_manager/branch/main/graph/badge.svg)](https://codecov.io/gh/ukvass/personal_manager)

A small, production‑like FastAPI app for task management with a clean JSON API, web UI, auth, CSRF, rate limiting, observability, and Docker setup.

## Features
- FastAPI + SQLAlchemy + Alembic migrations
- Auth (register/login), bcrypt hashing, JWT (cookie for web, Bearer for API)
- Tasks CRUD, filters, search, sorting, pagination, bulk actions
- Versioned API under `/api/v1` only
- Web UI with HTMX inline edits, CSRF protection
- Security headers + CORS
- Rate limiting on `/auth/*` (slowapi; Redis in Docker, in‑memory locally)
- Observability: `/live`, `/ready` (DB ping), Prometheus `/metrics`
- Dockerfile + docker-compose (app + Postgres + Redis)
- Quality: ruff, black, mypy, pre‑commit; tests with pytest

## Stack
- Python 3.12, FastAPI, SQLAlchemy, Alembic
- Pydantic v2, python‑jose, bcrypt
- HTMX, Jinja2
- slowapi, Redis (Docker)
- Prometheus FastAPI Instrumentator

## Quickstart (local)
Prereqs: Python 3.12 (Linux/macOS/WSL2), optional virtualenv `.venv`.

- Install and run (installs requirements automatically):
  - `make db-up`   # apply Alembic migrations to local SQLite
  - `make run`     # starts uvicorn, auto‑installs requirements

Open:
- Web UI: `http://localhost:8000/`
- API docs (Swagger): `http://localhost:8000/docs`

Seed demo data (optional):
- `make seed` (env: `SEED_EMAIL`, `SEED_PASSWORD` to override)

Tip: tests use an isolated temp SQLite DB and don’t require Postgres.

## Quickstart (Docker + Postgres)
- Docker Desktop (WSL2 on Windows): enable WSL integration
- Run: `docker compose up --build`
- App: `http://localhost:8000` (migrations auto‑applied in entrypoint)

## Configuration
All config via env vars (12‑factor). See `.env.example`.

Key vars:
- `DATABASE_URL` (default `sqlite:///./tasks.db`; Docker uses Postgres)
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MIN`
- CORS and security headers (`CORS_ALLOW_ORIGINS`, `SECURITY_*`)
- CSRF (`CSRF_*`) — enforced for web POST
- Rate limiting: `RATE_LIMIT_*`, `REDIS_URL` (in Docker)

## Database & Migrations
- Define models in `app/db_models.py`
- Migrations in `migrations/`
- Apply: `alembic upgrade head`
- New migration: `make migrate m="message"`

## API Overview (canonical under `/api/v1`)
- Auth:
  - `POST /api/v1/auth/register` → `{id, email}`
  - `POST /api/v1/auth/login` (OAuth2 password) → `{access_token, token_type}`
  - `GET  /api/v1/auth/me` → `{id, email}`
- Tasks:
  - `GET    /api/v1/tasks` (filters: `status`, `priority`, `q`; `limit/offset`; `order_by/dir`) + `X-Total-Count`
  - `POST   /api/v1/tasks` → Task
  - `GET    /api/v1/tasks/{id}` → Task
  - `PUT    /api/v1/tasks/{id}` → Task
  - `PATCH  /api/v1/tasks/{id}` → Task
  - `DELETE /api/v1/tasks/{id}` → 204
  - `POST   /api/v1/tasks/bulk_delete` → `{deleted}`
  - `POST   /api/v1/tasks/bulk_complete` → `{updated}`

### cURL examples
Register + login (bearer token):
```
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H 'content-type: application/json' \
  -d '{"email":"me@example.com","password":"secret"}'

TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'content-type: application/x-www-form-urlencoded' \
  -d 'username=me@example.com&password=secret' | jq -r .access_token)

curl -s -H "authorization: Bearer $TOKEN" http://localhost:8000/api/v1/auth/me
```
Create a task:
```
curl -s -X POST http://localhost:8000/api/v1/tasks \
  -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"title":"Buy milk","priority":2}'
```

## Postman
- Import `postman/PersonalManager.postman_collection.json`
- Set `baseUrl` (defaults to `http://localhost:8000`) and paste `token` after login.

## Web UI
- Login: `/login`, Register: `/register`, Tasks: `/`
- CSRF protected forms (hidden token + double submit cookie)
- Inline edit via HTMX partials

## Security & Observability
- CORS allowlist (dev: localhost)
- Security headers (CSP, X-Content-Type-Options, X-Frame-Options, HSTS in prod)
- CSRF for web forms
- Rate limiting on `/auth/*` (headers `X-RateLimit-*`)
- `/live` (liveness), `/ready` (DB ping), `/metrics` (Prometheus)

## Quality & Tests
- Lint: `make lint`
- Format: `make format`
- Types: `make type-check`
- Tests: `make test`
- Coverage: `make test-cov` (generates `coverage.xml`, fails CI under 80%)

## Badges & Coverage
- CI runs tests with coverage and uploads `coverage.xml` as an artifact.
- To view locally: `pytest --cov=app --cov-report=term-missing -q`.
- Codecov upload is enabled in CI (guarded by `CODECOV_TOKEN`). For private repos, add the token in GitHub → Settings → Secrets → Actions.

## Security & Dependencies
- Audit: `make audit` runs Bandit (code) + pip-audit (deps).
- Pre-commit includes Bandit and pip-audit hooks.
- Dependency pinning via pip-tools:
  - Edit `requirements.in`, then `make deps-compile` to regenerate pinned `requirements.txt`.
  - Sync your env: `make deps-sync`.
- Pre-commit: `make precommit-install` then commit as usual; or `make precommit-run`

## Notes
- JSON API is only under `/api/v1`.
- Swagger CSP relaxed only for `/docs` and `/redoc` to allow CDN assets.
- Local DB files are `.gitignore`d (`*.db`, `*.sqlite*`).
