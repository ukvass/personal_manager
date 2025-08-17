from typing import Dict, List, Optional
from .models import Task, TaskCreate, TaskUpdate, TaskPut, Status, now_utc

TASKS: Dict[int, Task] = {}
NEXT_ID: int = 1

def list_tasks(
 status: Optional[Status] = None,
 priority: Optional[int] = None,
 limit: int = 20,
 offset: int = 0
) -> List[Task]:
    items = list(TASKS.values())
    if status is not None:
        items = [t for t in items if t.status == status]
    if priority is not None:
        items = [t for t in items if t.priority == priority]
    return items[offset: offset + limit]

def create_task(data: TaskCreate) -> Task:
    global NEXT_ID
    tid = NEXT_ID
    NEXT_ID += 1
    now = now_utc()
    task = Task(
        id=tid,
        title=data.title,
        description=data.description,
        status="todo",
        priority=data.priority,
        created_at=now,
        updated_at=now,
    )
    TASKS[tid] = task
    return task

def get_task(task_id: int) -> Optional[Task]:
    return TASKS.get(task_id)

def update_task(task_id: int, data: TaskUpdate) -> Optional[Task]:
    task = TASKS.get(task_id)
    if not task:
        return None

    new_title = task.title
    new_description = task.description
    new_status = task.status
    new_priority = task.priority

    if data.title is not None:
        new_title = data.title
    if data.description is not None:
        new_description = data.description
    if data.status is not None:
        new_status = data.status
    if data.priority is not None:
        new_priority = data.priority

    updated = task.model_copy(update={
        "title": new_title,
        "description": new_description,
        "status": new_status,
        "priority": new_priority,
        "updated_at": now_utc(),
    })
    TASKS[task_id] = updated
    return updated

def replace_task(task_id: int, data: TaskPut) -> Optional[Task]:
    task = TASKS.get(task_id)
    if not task:
        return None
    updated = task.model_copy(update={
        "title": data.title,
        "description": data.description,
        "status": data.status,
        "priority": data.priority,
        "updated_at": now_utc(),
    })
    TASKS[task_id] = updated
    return updated

def delete_task(task_id: int) -> bool:
    return TASKS.pop(task_id, None) is not None
