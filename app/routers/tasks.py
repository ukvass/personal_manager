# PURPOSE: use DB-backed functions with FastAPI dependency injection for Session.

from fastapi import APIRouter, HTTPException, Response, status, Query, Depends
from typing import Optional, List, Literal
from sqlalchemy.orm import Session
from ..models import Task, TaskCreate, TaskUpdate, TaskPut, Status, UserPublic
from ..store_db import (
    get_db,
    list_tasks as db_list_tasks,
    create_task as db_create_task,
    get_task as db_get_task,
    replace_task as db_replace_task,
    update_task as db_update_task,
    delete_task as db_delete_task,
    count_tasks as db_count_tasks,
)
from ..auth import get_current_user

OrderBy = Literal["created_at", "priority", "deadline"]
OrderDir = Literal["asc", "desc"]

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=List[Task])
async def list_tasks(
    status: Optional[Status] = None,
    priority: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order_by: OrderBy = Query("created_at"),
    order_dir: OrderDir = Query("desc"),
    db: Session = Depends(get_db),
    user: UserPublic = Depends(get_current_user),
    response: Response = Response,
):
    tasks = db_list_tasks(
        db, status=status, priority=priority,
        limit=limit, offset=offset,
        order_by=order_by, order_dir=order_dir,
    )
    total = db_count_tasks(db, status=status, priority=priority)
    return db_list_tasks(db, owner_id=user.id, status=status, priority=priority, limit=limit, offset=offset)


@router.post("/", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task(item: TaskCreate, response: Response, db: Session = Depends(get_db), user: UserPublic = Depends(get_current_user)):
    task = db_create_task(db, item, owner_id=user.id)
    response.headers["Location"] = f"/tasks/{task.id}"
    return task


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: int, db: Session = Depends(get_db), user: UserPublic = Depends(get_current_user)):
    task = db_get_task(db, task_id, owner_id=user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=Task)
async def put_task(task_id: int, item: TaskPut, db: Session = Depends(get_db), user: UserPublic = Depends(get_current_user)):
    updated = db_replace_task(db, task_id, item, owner_id=user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated


@router.patch("/{task_id}", response_model=Task)
async def patch_task(task_id: int, item: TaskUpdate, db: Session = Depends(get_db), user: UserPublic = Depends(get_current_user)):
    updated = db_update_task(db, task_id, item, owner_id=user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, db: Session = Depends(get_db), user: UserPublic = Depends(get_current_user)):
    ok = db_delete_task(db, task_id, owner_id=user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
