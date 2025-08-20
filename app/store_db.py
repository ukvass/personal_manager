# >>> PATCH: app/store_db.py
# What changed (additions only, previous fixes preserved):
# - list_tasks/count_tasks: added optional `q` full-text search (ILIKE on title/description).
# - Added bulk operations: bulk_delete_tasks, bulk_complete_tasks (scoped by owner).
# - No breaking changes to existing signatures/behavior.

from typing import List, Optional, Literal
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy import asc, desc   # for ordering
from . import db_models, models
from .db import SessionLocal
from datetime import datetime, timezone

OrderBy = Literal["created_at", "priority", "deadline"]
OrderDir = Literal["asc", "desc"]


def now_utc():
    """Return timezone-aware UTC datetime (stored in DB)."""
    return datetime.now(timezone.utc)


def get_db():
    """Provide a SQLAlchemy Session per request and ensure it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def to_schema(row: db_models.TaskDB) -> models.Task:
    """Map ORM row -> Pydantic schema."""
    return models.Task(
        id=row.id,
        title=row.title,
        description=row.description,
        status=row.status,
        priority=row.priority,
        deadline=row.deadline,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_tasks(
    db: Session,
    *,
    owner_id: int,
    status: Optional[models.Status] = None,
    priority: Optional[int] = None,
    q: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    order_by: OrderBy = "created_at",
    order_dir: OrderDir = "desc",
) -> List[models.Task]:
    """Return tasks filtered and paginated from the DB."""
    stmt = select(db_models.TaskDB).where(db_models.TaskDB.owner_id == owner_id)

    if status is not None:
        stmt = stmt.where(db_models.TaskDB.status == status)
    if priority is not None:
        stmt = stmt.where(db_models.TaskDB.priority == priority)
    if q:
        # simple full-text search over title & description (case-insensitive)
        like = f"%{q}%"
        stmt = stmt.where(
            (db_models.TaskDB.title.ilike(like)) |
            (db_models.TaskDB.description.ilike(like))
        )

    col_map = {
        "created_at": db_models.TaskDB.created_at,
        "priority": db_models.TaskDB.priority,
        "deadline": db_models.TaskDB.deadline,
    }
    col = col_map.get(order_by, db_models.TaskDB.created_at)
    stmt = stmt.order_by(asc(col) if order_dir == "asc" else desc(col))

    stmt = stmt.offset(offset).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return [to_schema(r) for r in rows]


def create_task(db: Session, data: models.TaskCreate, owner_id: int) -> models.Task:
    row = db_models.TaskDB(
        title=data.title,
        description=data.description,
        status="todo",
        priority=data.priority or 1,
        deadline=data.deadline,
        created_at=now_utc(),
        updated_at=now_utc(),
        owner_id=owner_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return to_schema(row)


def get_task(db: Session, task_id: int, owner_id: int) -> Optional[models.Task]:
    row = db.get(db_models.TaskDB, task_id)
    if not row or row.owner_id != owner_id:
        return None
    return to_schema(row)


def replace_task(db: Session, task_id: int, data: models.TaskPut, owner_id: int) -> Optional[models.Task]:
    row = db.get(db_models.TaskDB, task_id)
    if not row or row.owner_id != owner_id:
        return None
    row.title = data.title
    row.description = data.description
    row.status = data.status
    row.priority = data.priority
    row.deadline = data.deadline
    row.updated_at = now_utc()
    db.commit()
    db.refresh(row)
    return to_schema(row)


def update_task(db: Session, task_id: int, data: models.TaskUpdate, owner_id: int) -> Optional[models.Task]:
    row = db.get(db_models.TaskDB, task_id)
    if not row or row.owner_id != owner_id:
        return None
    if data.title is not None:
        row.title = data.title
    if data.description is not None:
        row.description = data.description
    if data.status is not None:
        row.status = data.status
    if hasattr(data, "priority") and (data.priority is not None):
        row.priority = data.priority
    if data.deadline is not None:
        row.deadline = data.deadline
    row.updated_at = now_utc()
    db.commit()
    db.refresh(row)
    return to_schema(row)


def delete_task(db: Session, task_id: int, owner_id: int) -> bool:
    row = db.get(db_models.TaskDB, task_id)
    if not row or row.owner_id != owner_id:
        return False
    db.delete(row)
    db.commit()
    return True


def count_tasks(
    db: Session,
    *,
    owner_id: int,
    status: Optional[models.Status] = None,
    priority: Optional[int] = None,
    q: Optional[str] = None,
) -> int:
    stmt = select(func.count()).select_from(db_models.TaskDB).where(db_models.TaskDB.owner_id == owner_id)
    if status is not None:
        stmt = stmt.where(db_models.TaskDB.status == status)
    if priority is not None:
        stmt = stmt.where(db_models.TaskDB.priority == priority)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (db_models.TaskDB.title.ilike(like)) |
            (db_models.TaskDB.description.ilike(like))
        )
    return db.execute(stmt).scalar_one()


# --- Bulk operations (scoped to owner) ---

def bulk_delete_tasks(db: Session, ids: List[int], owner_id: int) -> int:
    """Delete tasks by IDs if they belong to owner. Returns number of deleted rows."""
    count = 0
    for tid in ids:
        row = db.get(db_models.TaskDB, tid)
        if row and row.owner_id == owner_id:
            db.delete(row)
            count += 1
    if count:
        db.commit()
    return count


def bulk_complete_tasks(db: Session, ids: List[int], owner_id: int) -> int:
    """Set status='done' for tasks by IDs if they belong to owner. Returns number of updated rows."""
    count = 0
    for tid in ids:
        row = db.get(db_models.TaskDB, tid)
        if row and row.owner_id == owner_id and row.status != "done":
            row.status = "done"
            row.updated_at = now_utc()
            count += 1
    if count:
        db.commit()
    return count
