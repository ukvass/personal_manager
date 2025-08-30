# >>> PATCH: app/routers/tasks.py
# Changes:
# - Allowed 'status' in OrderBy; parsers read order_by/order_dir by name.
# - priority empty string -> None (no filter) unchanged.

from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException, Response, status, Depends
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

from ..api.deps import (
    OrderBy,
    OrderDir,
    parse_priority,
    parse_order_by,
    parse_order_dir,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])



@router.get("/", response_model=List[Task])
async def list_tasks(
    status: Optional[Status] = None,
    priority: Optional[int] = Depends(parse_priority),
    q: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    order_by: OrderBy = Depends(parse_order_by),
    order_dir: OrderDir = Depends(parse_order_dir),
    db: Session = Depends(get_db),
    user: UserPublic = Depends(get_current_user),
    response: Response = None,
):
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
    task = db_create_task(db, item, owner_id=user.id)
    response.headers["Location"] = f"/tasks/{task.id}"
    return task


@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: UserPublic = Depends(get_current_user),
):
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
    ok = db_delete_task(db, task_id, owner_id=user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/bulk_delete", status_code=status.HTTP_200_OK)
async def bulk_delete(payload: TaskIdList, db: Session = Depends(get_db), user: UserPublic = Depends(get_current_user)) -> Dict[str, int]:
    deleted = db_bulk_delete(db, payload.ids, owner_id=user.id)
    return {"deleted": deleted}


@router.post("/bulk_complete", status_code=status.HTTP_200_OK)
async def bulk_complete(payload: TaskIdList, db: Session = Depends(get_db), user: UserPublic = Depends(get_current_user)) -> Dict[str, int]:
    updated = db_bulk_complete(db, payload.ids, owner_id=user.id)
    return {"updated": updated}
