# PURPOSE: same API as in-memory store, but using the database.

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
    return datetime.now(timezone.utc)


def get_db():
    """FastAPI dependency: open a DB session for each request and close it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def to_schema(row: db_models.TaskDB) -> models.Task:
    """Map ORM row (TaskDB) → Pydantic schema (Task)."""
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


# ---------- CRUD ----------

def list_tasks(
    db: Session,
    *,
    status: Optional[models.Status] = None,
    priority: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
    order_by: OrderBy = "created_at",   # default sort
    order_dir: OrderDir = "desc",       # default dir
) -> List[models.Task]:
    """Return tasks filtered and paginated from the DB."""
    stmt = select(db_models.TaskDB)
    # filter by status
    if status is not None:
        stmt = stmt.where(db_models.TaskDB.status == status)
    # filter by priority
    if priority is not None:
        stmt = stmt.where(db_models.TaskDB.priority == priority)

    # map order_by -> ORM column
    col_map = {
        "created_at": db_models.TaskDB.created_at,
        "priority": db_models.TaskDB.priority,
        "deadline": db_models.TaskDB.deadline,
    }
    col = col_map.get(order_by, db_models.TaskDB.created_at)
    stmt = stmt.order_by(asc(col) if order_dir == "asc" else desc(col))

    # apply limit/offset
    stmt = stmt.offset(offset).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return [to_schema(r) for r in rows]


def create_task(db: Session, data: models.TaskCreate) -> models.Task:
    """Insert a new task row and return it as Pydantic model."""
    row = db_models.TaskDB(
        title=data.title,
        description=data.description,
        status="todo",
        priority=data.priority or 1,
        deadline=data.deadline,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)  # populate row.id and other defaults
    return to_schema(row)


def get_task(db: Session, task_id: int) -> Optional[models.Task]:
    """Return one task by id or None."""
    row = db.get(db_models.TaskDB, task_id)
    if not row:
        return None
    return to_schema(row)


def replace_task(db: Session, task_id: int, data: models.TaskPut) -> Optional[models.Task]:
    """Full replace: set ALL modifiable fields (PUT)."""
    row = db.get(db_models.TaskDB, task_id)
    if not row:
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


def update_task(db: Session, task_id: int, data: models.TaskUpdate) -> Optional[models.Task]:
    """Partial update (PATCH): change only provided fields."""
    row = db.get(db_models.TaskDB, task_id)
    if not row:
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


def delete_task(db: Session, task_id: int) -> bool:
    """Delete a task. Return True if deleted, False if not found."""
    row = db.get(db_models.TaskDB, task_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True

def count_tasks(
    db: Session,
    *,
    status: Optional[models.Status] = None,
    priority: Optional[int] = None,
) -> int:
    """Return total count of tasks (with same filters)."""
    stmt = select(func.count()).select_from(db_models.TaskDB)
    if status is not None:
        stmt = stmt.where(db_models.TaskDB.status == status)
    if priority is not None:
        stmt = stmt.where(db_models.TaskDB.priority == priority)
    return db.execute(stmt).scalar_one()