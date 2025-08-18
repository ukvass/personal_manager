# PURPOSE: use DB-backed functions with FastAPI dependency injection for Session.

from fastapi import APIRouter, HTTPException, Response, status, Query, Depends
from typing import Optional, List
from sqlalchemy.orm import Session
from ..models import Task, TaskCreate, TaskUpdate, TaskPut, Status
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

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=List[Task])
async def list_tasks(
    status: Optional[Status] = None,
    priority: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    response: Response = None,  # add Response
):
    tasks = db_list_tasks(db, status=status, priority=priority, limit=limit, offset=offset)
    total = db_count_tasks(db, status=status, priority=priority)
    response.headers["X-Total-Count"] = str(total)
    return tasks


@router.post("/", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task(item: TaskCreate, response: Response, db: Session = Depends(get_db)):
    task = db_create_task(db, item)
    response.headers["Location"] = f"/tasks/{task.id}"
    return task


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db_get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=Task)
async def put_task(task_id: int, item: TaskPut, db: Session = Depends(get_db)):
    updated = db_replace_task(db, task_id, item)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated


@router.patch("/{task_id}", response_model=Task)
async def patch_task(task_id: int, item: TaskUpdate, db: Session = Depends(get_db)):
    updated = db_update_task(db, task_id, item)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, db: Session = Depends(get_db)):
    ok = db_delete_task(db, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
