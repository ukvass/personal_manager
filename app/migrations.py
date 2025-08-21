# >>> NEW FILE: app/migrations.py
# Purpose:
# - Minimal, idempotent startup migrations for SQLite.
# - Currently:
#     * ensure tasks.owner_id exists; if missing -> ALTER TABLE ADD COLUMN owner_id INTEGER REFERENCES users(id)
# - Safe to call multiple times.

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _column_exists_sqlite(engine: Engine, table: str, column: str) -> bool:
    """Return True if `column` exists in `table` for SQLite."""
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).mappings().all()
    return any(r["name"] == column for r in rows)


def run_startup_migrations(engine: Engine) -> None:
    """Run lightweight, idempotent migrations on app startup."""
    # 1) tasks.owner_id
    if not _column_exists_sqlite(engine, "tasks", "owner_id"):
        with engine.begin() as conn:
            # Add nullable owner_id to not break existing rows;
            # Foreign key reference to users(id) for future inserts.
            conn.execute(text("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"))
            # (Optional) You could backfill owner_id here if you want:
            # e.g., set to NULL or set to a specific user id.
            # We leave it NULL to avoid assumptions.
