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


def _table_exists_sqlite(engine: Engine, table: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
            {"t": table},
        ).fetchone()
    return row is not None


def run_startup_migrations(engine: Engine) -> None:
    """Run lightweight, idempotent migrations on app startup."""
    # If tasks table doesn't exist yet, let SQLAlchemy create it later
    if not _table_exists_sqlite(engine, "tasks"):
        return

    # 1) tasks.owner_id
    if not _column_exists_sqlite(engine, "tasks", "owner_id"):
        with engine.begin() as conn:
            # Add nullable owner_id to not break existing rows;
            # Foreign key reference to users(id) for future inserts.
            conn.execute(text("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"))
            # (Optional) You could backfill owner_id here if you want:
            # e.g., set to NULL or set to a specific user id.
            # We leave it NULL to avoid assumptions.
    
    # 2) Drop tasks.description column if present
    if _column_exists_sqlite(engine, "tasks", "description"):
        try:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE tasks DROP COLUMN description"))
        except Exception:
            # Fallback for older SQLite: table copy without the column
            with engine.begin() as conn:
                # Ensure foreign keys are not enforced during table swap
                conn.execute(text("PRAGMA foreign_keys=OFF"))
                # Create new table without description
                conn.execute(text(
                    """
                    CREATE TABLE IF NOT EXISTS tasks_new (
                        id INTEGER PRIMARY KEY,
                        title VARCHAR NOT NULL,
                        status VARCHAR DEFAULT 'todo',
                        priority INTEGER DEFAULT 1,
                        deadline DATETIME NULL,
                        created_at DATETIME,
                        updated_at DATETIME,
                        owner_id INTEGER NULL REFERENCES users(id)
                    )
                    """
                ))
                # Copy data
                conn.execute(text(
                    """
                    INSERT INTO tasks_new (id, title, status, priority, deadline, created_at, updated_at, owner_id)
                    SELECT id, title, status, priority, deadline, created_at, updated_at, owner_id FROM tasks
                    """
                ))
                # Replace old table
                conn.execute(text("DROP TABLE tasks"))
                conn.execute(text("ALTER TABLE tasks_new RENAME TO tasks"))
                conn.execute(text("PRAGMA foreign_keys=ON"))
