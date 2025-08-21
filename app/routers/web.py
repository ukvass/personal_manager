# >>> PATCH: app/routers/web.py
# Fixes:
# - Added custom parser parse_priority() that treats empty string as None (no filter).
# - index() now depends on parse_priority() instead of Optional[int] directly.
# - Everything else (templates resolution, login flow, actions) remains the same.

from typing import Optional, List, Literal
from fastapi import APIRouter, Request, Depends, Form, status, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from importlib import resources as ilres

from ..config import settings
from ..db_models import UserDB
from ..models import Status
from ..store_db import (
    get_db,
    list_tasks as db_list_tasks,
    create_task as db_create_task,
    delete_task as db_delete_task,
    count_tasks as db_count_tasks,
    bulk_delete_tasks as db_bulk_delete,
    bulk_complete_tasks as db_bulk_complete,
)
from ..auth import verify_password, create_access_token, get_access_token_ttl_minutes

# Templates from the *package* directory app/templates (robust to CWD)
templates_dir = ilres.files("app").joinpath("templates")
must_have = ("base.html", "login.html", "index.html")
missing = [name for name in must_have if not templates_dir.joinpath(name).exists()]
if missing:
    raise HTTPException(
        status_code=500,
        detail=f"Templates missing: {', '.join(missing)} in {templates_dir}. "
               f"Ensure files are located at app/templates/."
    )
templates = Jinja2Templates(directory=str(templates_dir))

OrderBy = Literal["created_at", "priority", "deadline"]
OrderDir = Literal["asc", "desc"]

router = APIRouter(tags=["web"])


# --- Helpers ---------------------------------------------------------------

def parse_priority(priority: Optional[str] = Query(None)) -> Optional[int]:
    """
    Parse 'priority' query parameter for SSR page.
    - "" or missing -> None (no filter)
    - integer string -> int
    - anything else -> 422 (invalid)
    """
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


def _get_user_from_cookie(request: Request, db: Session) -> Optional[UserDB]:
    """Decode JWT from HttpOnly cookie and return a DB user row if valid."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        email = payload.get("sub")
        if not email:
            return None
    except JWTError:
        return None
    return db.query(UserDB).filter(UserDB.email == email).one_or_none()


# --- Auth pages ------------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    """Render the login form."""
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Validate credentials, issue JWT in HttpOnly cookie, redirect to '/'."""
    email = (email or "").strip()
    password = (password or "")
    if not email or not password:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Email and password are required."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = db.query(UserDB).filter(UserDB.email == email).one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        token = create_access_token(email)
    except Exception as ex:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": f"Authentication failed. {ex}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    minutes = get_access_token_ttl_minutes()
    resp = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(
        "access_token",
        token,
        httponly=True,
        max_age=60 * minutes,
        samesite="lax",
    )
    return resp


@router.post("/logout")
def logout():
    """Clear auth cookie and go to login page."""
    resp = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie("access_token")
    return resp


# --- Main page -------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    status_: Optional[Status] = None,
    priority: Optional[int] = Depends(parse_priority),  # ← custom parser
    q: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    order_by: OrderBy = "created_at",
    order_dir: OrderDir = "desc",
    db: Session = Depends(get_db),
):
    """Main tasks page with filters, search and bulk actions."""
    user = _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    total = db_count_tasks(
        db,
        owner_id=user.id,
        status=status_,
        priority=priority,
        q=q,
    )
    items = db_list_tasks(
        db,
        owner_id=user.id,
        status=status_,
        priority=priority,
        q=q,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_dir=order_dir,
    )
    ctx = {
        "request": request,
        "user": user,
        "tasks": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "status": status_,
        "priority": priority,
        "q": q or "",
        "order_by": order_by,
        "order_dir": order_dir,
    }
    return templates.TemplateResponse("index.html", ctx)


# --- Actions ---------------------------------------------------------------

@router.post("/ui/tasks")
def create_task_web(
    request: Request,
    title: str = Form(...),
    priority: int = Form(1),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Create a task from form and redirect back to list (works with/without HTMX)."""
    user = _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    title = (title or "").strip()
    if not title:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    data = type("Data", (), {})()
    data.title = title
    data.priority = priority
    data.description = description
    data.deadline = None

    db_create_task(db, data=data, owner_id=user.id)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ui/tasks/{task_id}/delete")
def delete_task_web(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
):
    """Delete a single task and redirect back to list."""
    user = _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    db_delete_task(db, task_id, owner_id=user.id)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ui/bulk_delete")
def bulk_delete_web(
    request: Request,
    ids: List[int] = Form(...),
    db: Session = Depends(get_db),
):
    """Bulk delete by IDs and redirect back to list."""
    user = _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    db_bulk_delete(db, ids, owner_id=user.id)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ui/bulk_complete")
def bulk_complete_web(
    request: Request,
    ids: List[int] = Form(...),
    db: Session = Depends(get_db),
):
    """Bulk mark as done by IDs and redirect back to list."""
    user = _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    db_bulk_complete(db, ids, owner_id=user.id)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
