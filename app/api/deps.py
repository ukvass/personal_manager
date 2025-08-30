from typing import Optional, Literal

from fastapi import Query, HTTPException, Depends

from ..models import Status


# Shared order types
OrderBy = Literal["created_at", "priority", "status", "deadline"]
OrderDir = Literal["asc", "desc"]


def parse_status(status: Optional[str] = Query(None)) -> Optional[Status]:
    if status is None or status == "":
        return None
    if status in ("todo", "in_progress", "done"):
        return status  # type: ignore[return-value]
    raise HTTPException(
        status_code=422,
        detail=[{
            "type": "literal_error",
            "loc": ["query", "status"],
            "msg": "status must be one of: todo, in_progress, done",
            "input": status,
        }],
    )


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


def parse_order_dir(
    order_dir: Optional[str] = Query(None),
    order_by: OrderBy = Depends(parse_order_by),
) -> OrderDir:
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

