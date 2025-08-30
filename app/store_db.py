# >>> PATCH: app/store_db.py
# Changes:
# - _apply_ordering(): added 'status' ordering using SQL CASE:
#     todo -> 0, in_progress -> 1, done -> 2 (desc shows done first).
# - Kept priority NULL-safe (COALESCE) and stable secondary ordering.

from __future__ import annotations

from typing import Optional, Sequence, List, Any

from sqlalchemy import func, case
from sqlalchemy.orm import Session

from .db_models import TaskDB, now_utc


# --- Session dependency ----------------------------------------------------


def get_db():
    """Yield a SQLAlchemy session (used as a FastAPI dependency)."""
    from .db import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Helpers ---------------------------------------------------------------


def _apply_common_filters(
    query,
    *,
    owner_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[int] = None,
    q: Optional[str] = None,
):
    """Apply shared filters to a TaskDB query."""
    if owner_id is not None:
        query = query.filter(TaskDB.owner_id == owner_id)
    if status:
        query = query.filter(TaskDB.status == status)
    if priority is not None:
        query = query.filter(TaskDB.priority == priority)
    if q:
        like = f"%{q}%"
        query = query.filter(TaskDB.title.ilike(like))
    return query


def _apply_ordering(query, *, order_by: str, order_dir: str):
    """
    Apply ordering with a safe allow-list of columns.
    Allowed: created_at, priority, status, deadline(fallback to created_at).
    Includes stable secondary ordering for deterministic results.
    """
    # primary key expression
    if order_by == "priority":
        primary: Any = func.coalesce(TaskDB.priority, 0)
    elif order_by == "status":
        # Map textual status to integer rank: todo(0) < in_progress(1) < done(2)
        primary = case(
            (TaskDB.status == "todo", 0),
            (TaskDB.status == "in_progress", 1),
            (TaskDB.status == "done", 2),
            else_=0,
        )
    elif order_by == "created_at":
        primary = TaskDB.created_at
    elif order_by == "deadline":
        # Put rows with a deadline first (by deadline), then fall back to created_at
        primary = func.coalesce(TaskDB.deadline, TaskDB.created_at)
    else:
        primary = TaskDB.created_at

    # stable secondary ordering
    secondary_desc = [TaskDB.created_at.desc(), TaskDB.id.desc()]
    secondary_asc = [TaskDB.created_at.asc(), TaskDB.id.asc()]

    if order_dir == "asc":
        return query.order_by(primary.asc(), *secondary_asc)
    return query.order_by(primary.desc(), *secondary_desc)


# --- CRUD: Tasks -----------------------------------------------------------


def list_tasks(
    db: Session,
    *,
    owner_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[int] = None,
    q: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "created_at",
    order_dir: str = "desc",
) -> List[TaskDB]:
    """Return a paginated list of tasks with filters and ordering applied."""
    query = db.query(TaskDB)
    query = _apply_common_filters(
        query,
        owner_id=owner_id,
        status=status,
        priority=priority,
        q=q,
    )
    query = _apply_ordering(query, order_by=order_by, order_dir=order_dir)
    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)
    return query.all()


def count_tasks(
    db: Session,
    *,
    owner_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[int] = None,
    q: Optional[str] = None,
) -> int:
    """Return total count for the given filters (no pagination)."""
    query = db.query(func.count(TaskDB.id))
    query = _apply_common_filters(
        query,
        owner_id=owner_id,
        status=status,
        priority=priority,
        q=q,
    )
    return int(query.scalar() or 0)


def create_task(db: Session, data, *, owner_id: Optional[int] = None) -> TaskDB:
    """Create a task from a Pydantic-like object; owner_id is optional."""
    now = now_utc()
    row = TaskDB(
        title=data.title,
        status=getattr(data, "status", "todo"),
        priority=getattr(data, "priority", 1),
        deadline=getattr(data, "deadline", None),
        owner_id=owner_id,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_task(db: Session, task_id: int, *, owner_id: Optional[int] = None):
    """Fetch a single task; if owner_id is given, enforce ownership."""
    query = db.query(TaskDB).filter(TaskDB.id == task_id)
    if owner_id is not None:
        query = query.filter(TaskDB.owner_id == owner_id)
    return query.one_or_none()


def replace_task(db: Session, task_id: int, data, *, owner_id: Optional[int] = None):
    """Full replace of a task (PUT). Returns updated row or None if not found."""
    row = get_task(db, task_id, owner_id=owner_id)
    if not row:
        return None
    row.title = data.title
    row.status = getattr(data, "status", "todo")
    row.priority = getattr(data, "priority", 1)
    row.deadline = getattr(data, "deadline", None)
    row.updated_at = now_utc()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_task(db: Session, task_id: int, data, *, owner_id: Optional[int] = None):
    """Partial update (PATCH). Returns updated row or None if not found."""
    row = get_task(db, task_id, owner_id=owner_id)
    if not row:
        return None
    for field in ("title", "status", "priority", "deadline"):
        if hasattr(data, field) and getattr(data, field) is not None:
            setattr(row, field, getattr(data, field))
    row.updated_at = now_utc()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_task(db: Session, task_id: int, *, owner_id: Optional[int] = None) -> bool:
    """Delete a task; returns True if deleted, False if not found/forbidden."""
    row = get_task(db, task_id, owner_id=owner_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


# --- Bulk ops --------------------------------------------------------------


def bulk_delete_tasks(db: Session, ids: Sequence[int], *, owner_id: Optional[int] = None) -> int:
    """Delete many tasks by IDs; only deletes owned tasks if owner_id is set."""
    if not ids:
        return 0
    q = db.query(TaskDB).filter(TaskDB.id.in_(list(ids)))
    if owner_id is not None:
        q = q.filter(TaskDB.owner_id == owner_id)
    deleted = 0
    for row in q.all():
        db.delete(row)
        deleted += 1
    db.commit()
    return deleted


def bulk_complete_tasks(db: Session, ids: Sequence[int], *, owner_id: Optional[int] = None) -> int:
    """Mark many tasks as 'done'; only affects owned tasks if owner_id is set."""
    if not ids:
        return 0
    q = db.query(TaskDB).filter(TaskDB.id.in_(list(ids)))
    if owner_id is not None:
        q = q.filter(TaskDB.owner_id == owner_id)
    updated = 0
    for row in q.all():
        row.status = "done"
        db.add(row)
        updated += 1
    db.commit()
    return updated
