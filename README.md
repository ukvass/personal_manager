# Personal Manager

A small, production‑like FastAPI app for task management with a clean JSON API, web UI, auth, CSRF, rate limiting, observability, and Docker setup. Built to be a solid junior portfolio project with a touch of mid‑level practices.

## Features
- FastAPI + SQLAlchemy + Alembic migrations
- Auth (register/login), bcrypt hashing, JWT (cookie for web, Bearer for API)
- Tasks CRUD, filters, search, sorting, pagination, bulk actions
- Versioned API under `/api/v1` (legacy `/auth` and `/tasks` redirect with 308)
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
- Pre-commit: `make precommit-install` then commit as usual; or `make precommit-run`

## Notes
- JSON API is only under `/api/v1` — legacy `/auth` and `/tasks` hard‑redirect (308) to v1.
- Swagger CSP relaxed only for `/docs` and `/redoc` to allow CDN assets.
- Local DB files are `.gitignore`d (`*.db`, `*.sqlite*`).

