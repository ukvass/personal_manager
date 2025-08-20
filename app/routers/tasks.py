# >>> PATCH: app/routers/tasks.py
# What changed:
# - Added optional `q` query for simple full-text search.
# - Added two bulk endpoints:
#     POST /tasks/bulk_delete  { "ids": [...] } -> { "deleted": N }
#     POST /tasks/bulk_complete { "ids": [...] } -> { "updated": N }
# - Kept user isolation and X-Total-Count behavior.

from typing import Optional, List, Literal, Dict
from fastapi import APIRouter, HTTPException, Response, status, Query, Depends
from sqlalchemy.orm import Session

from ..models import Task, TaskCreate, TaskUpdate, TaskPut, Status, UserPublic, TaskIdList
from ..store_db import (
    get_db,
    list_tasks as db_list_tasks,
    create_task as db_create_task,
    get_task as db_get_task,
    replace_task as db_replace_task,
    update_task as db_update_task,
    delete_task as db_delete_task,
    count_tasks as db_count_tasks,
    bulk_delete_tasks as db_bulk_delete,
    bulk_complete_tasks as db_bulk_complete,
)
from ..auth import get_current_user

OrderBy = Literal["created_at", "priority", "deadline"]
OrderDir = Literal["asc", "desc"]

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=List[Task])
async def list_tasks(
    status: Optional[Status] = None,
    priority: Optional[int] = None,
    q: Optional[str] = Query(default=None, description="Search in title/description"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order_by: OrderBy = Query("created_at"),
    order_dir: OrderDir = Query("desc"),
    db: Session = Depends(get_db),
    user: UserPublic = Depends(get_current_user),
    response: Response = None,
):
    """Return paginated tasks for the current user; sets X-Total-Count header."""
    total = db_count_tasks(db, owner_id=user.id, status=status, priority=priority, q=q)
    items = db_list_tasks(
        db, owner_id=user.id,
        status=status, priority=priority, q=q,
        limit=limit, offset=offset,
        order_by=order_by, order_dir=order_dir,
    )
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return items


@router.post("/", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task(
    item: TaskCreate,
    response: Response,
    db: Session = Depends(get_db),
    user: UserPublic = Depends(get_current_user),
):
    """Create a task owned by the current user and set Location header."""
    task = db_create_task(db, item, owner_id=user.id)
    response.headers["Location"] = f"/tasks/{task.id}"
    return task


@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: UserPublic = Depends(get_current_user),
):
    """Get one task owned by the current user."""
    task = db_get_task(db, task_id, owner_id=user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=Task)
async def put_task(
    task_id: int,
    item: TaskPut,
    db: Session = Depends(get_db),
    user: UserPublic = Depends(get_current_user),
):
    """Full replace the task owned by the current user."""
    updated = db_replace_task(db, task_id, item, owner_id=user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated


@router.patch("/{task_id}", response_model=Task)
async def patch_task(
    task_id: int,
    item: TaskUpdate,
    db: Session = Depends(get_db),
    user: UserPublic = Depends(get_current_user),
):
    """Partial update the task owned by the current user."""
    updated = db_update_task(db, task_id, item, owner_id=user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: UserPublic = Depends(get_current_user),
):
    """Delete the task owned by the current user."""
    ok = db_delete_task(db, task_id, owner_id=user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Bulk operations ---

@router.post("/bulk_delete", status_code=status.HTTP_200_OK)
async def bulk_delete(payload: TaskIdList, db: Session = Depends(get_db), user: UserPublic = Depends(get_current_user)) -> Dict[str, int]:
    """Delete multiple tasks by IDs (only tasks owned by the current user are affected)."""
    deleted = db_bulk_delete(db, payload.ids, owner_id=user.id)
    return {"deleted": deleted}


@router.post("/bulk_complete", status_code=status.HTTP_200_OK)
async def bulk_complete(payload: TaskIdList, db: Session = Depends(get_db), user: UserPublic = Depends(get_current_user)) -> Dict[str, int]:
    """Mark multiple tasks as done (only tasks owned by the current user are affected)."""
    updated = db_bulk_complete(db, payload.ids, owner_id=user.id)
    return {"updated": updated}
