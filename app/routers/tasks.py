# >>> PATCH: app/routers/tasks.py
# Changes:
# - Allowed 'status' in OrderBy; parsers read order_by/order_dir by name.
# - priority empty string -> None (no filter) unchanged.

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

OrderBy = Literal["created_at", "priority", "status", "deadline"]
OrderDir = Literal["asc", "desc"]

router = APIRouter(prefix="/tasks", tags=["tasks"])


def parse_priority(priority: Optional[str] = Query(None)) -> Optional[int]:
    if priority is None or priority == "":
        return None
    try:
        return int(priority)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail=[{
                "type": "int_parsing",
                "loc": ["query", "priority"],
                "msg": "Input should be a valid integer, unable to parse string as an integer",
                "input": priority,
            }],
        )


def parse_order_by(order_by: Optional[str] = Query(None)) -> OrderBy:
    if not order_by:
        return "created_at"
    if order_by in ("created_at", "priority", "status", "deadline"):
        return order_by  # type: ignore[return-value]
    raise HTTPException(status_code=422, detail=[{
        "type": "literal_error",
        "loc": ["query", "order_by"],
        "msg": "order_by must be one of: created_at, priority, status, deadline",
        "input": order_by,
    }])


def parse_order_dir(order_dir: Optional[str] = Query(None), order_by: OrderBy = Depends(parse_order_by)) -> OrderDir:
    if not order_dir:
        return "desc"
    if order_dir in ("asc", "desc"):
        return order_dir  # type: ignore[return-value]
    raise HTTPException(status_code=422, detail=[{
        "type": "literal_error",
        "loc": ["query", "order_dir"],
        "msg": "order_dir must be 'asc' or 'desc'",
        "input": order_dir,
    }])


@router.get("/", response_model=List[Task])
async def list_tasks(
    status: Optional[Status] = None,
    priority: Optional[int] = Depends(parse_priority),
    q: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
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
