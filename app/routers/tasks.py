from fastapi import APIRouter, HTTPException, Response, status, Query
from typing import Optional, List
from ..models import Task, TaskCreate, TaskUpdate, TaskPut, Status
from .. import store

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.get("/", response_model=List[Task])
async def list_tasks(
    status: Optional[Status] = None,
    priority: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    return store.list_tasks(
        status=status,
        priority=priority,
        limit=limit,
        offset=offset,
    )

@router.post("/", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task(item: TaskCreate, response: Response):
    task = store.create_task(item)
    response.headers["Location"] = f"/tasks/{task.id}"
    return task

@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: int):
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.put("/{task_id}", response_model=Task)
async def put_task(task_id: int, item: TaskPut):
    updated = store.replace_task(task_id, item)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated

@router.patch("/{task_id}", response_model=Task)
async def patch_task(task_id: int, item: TaskUpdate):
    updated = store.update_task(task_id, item)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int):
    ok = store.delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    # 204 — тело пустое
    return Response(status_code=status.HTTP_204_NO_CONTENT)
