# >>> PATCH: app/routers/web.py
# Что изменил:
# - Добавил _build_context(): возвращает {'request', 'user', 'user_email'}.
# - index() использует _build_context() и гарантированно прокидывает email.
# - Остальная логика без изменений.

from typing import Optional, List
from fastapi import APIRouter, Request, Depends, Form, status as http_status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from importlib import resources as ilres

from ..config import settings
from ..db_models import UserDB
from ..store_db import (
    get_db,
    list_tasks as db_list_tasks,
    create_task as db_create_task,
    delete_task as db_delete_task,
    count_tasks as db_count_tasks,
    bulk_delete_tasks as db_bulk_delete,
    bulk_complete_tasks as db_bulk_complete,
    update_task as db_update_task,
    get_task as db_get_task,
)
from ..auth import verify_password, create_access_token, get_access_token_ttl_minutes
from ..models import TaskCreate, TaskUpdate
from ..api.deps import (
    OrderBy,
    OrderDir,
    parse_status,
    parse_priority,
    parse_order_by,
    parse_order_dir,
)
from ..security import set_csrf_cookie, ensure_csrf

templates_dir = ilres.files("app").joinpath("templates")
templates = Jinja2Templates(directory=str(templates_dir))


router = APIRouter(tags=["web"])



def _get_user_from_cookie(request: Request, db: Session) -> Optional[UserDB]:
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


def _build_context(request: Request, db: Session) -> dict:
    """Common template context: request + user(+email) if logged in."""
    user = _get_user_from_cookie(request, db)
    return {
        "request": request,
        "user": user,
        "user_email": user.email if user else None,
    }


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    # user not required here; topbar can hide logout/email automatically
    ctx = {"request": request, "error": None}
    resp = templates.TemplateResponse("login.html", ctx)
    token = set_csrf_cookie(resp)
    ctx["csrf_token"] = token
    return resp


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    _csrf=Depends(ensure_csrf),
):
    email = (email or "").strip()
    password = (password or "")
    if not email or not password:
        ctx = {"request": request, "error": "Email and password are required."}
        resp = templates.TemplateResponse("login.html", ctx, status_code=http_status.HTTP_400_BAD_REQUEST)
        ctx["csrf_token"] = set_csrf_cookie(resp)
        return resp

    user = db.query(UserDB).filter(UserDB.email == email).one_or_none()
    if not user or not verify_password(password, user.password_hash):
        ctx = {"request": request, "error": "Invalid email or password."}
        resp = templates.TemplateResponse("login.html", ctx, status_code=http_status.HTTP_401_UNAUTHORIZED)
        ctx["csrf_token"] = set_csrf_cookie(resp)
        return resp

    token = create_access_token(email)
    minutes = get_access_token_ttl_minutes()
    resp = RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)
    resp.set_cookie("access_token", token, httponly=True, max_age=60 * minutes, samesite="lax")
    return resp


@router.post("/logout")
def logout(_csrf=Depends(ensure_csrf)):
    resp = RedirectResponse(url="/login", status_code=http_status.HTTP_303_SEE_OTHER)
    resp.delete_cookie("access_token")
    return resp


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    status: Optional[str] = Depends(parse_status),
    priority: Optional[int] = Depends(parse_priority),
    q: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    order_by: OrderBy = Depends(parse_order_by),
    order_dir: OrderDir = Depends(parse_order_dir),
    db: Session = Depends(get_db),
):
    ctx = _build_context(request, db)
    if not ctx["user"]:
        return RedirectResponse(url="/login", status_code=http_status.HTTP_303_SEE_OTHER)

    total = db_count_tasks(db, owner_id=ctx["user"].id, status=status, priority=priority, q=q)
    items = db_list_tasks(
        db,
        owner_id=ctx["user"].id,
        status=status, priority=priority, q=q,
        limit=limit, offset=offset, order_by=order_by, order_dir=order_dir,
    )

    ctx.update({
        "tasks": items, "total": total,
        "limit": limit, "offset": offset,
        "status": status, "priority": priority,
        "q": q or "", "order_by": order_by, "order_dir": order_dir,
    })
    # Ensure CSRF cookie/token for forms on the page
    resp = templates.TemplateResponse("index.html", ctx)
    token = request.cookies.get(settings.CSRF_COOKIE_NAME)
    if not token:
        token = set_csrf_cookie(resp)
    else:
        set_csrf_cookie(resp, token)
    ctx["csrf_token"] = token
    return resp


@router.post("/ui/tasks")
def create_task_web(
    request: Request,
    title: str = Form(...),
    priority: int = Form(1),
    # description removed
    db: Session = Depends(get_db),
    _csrf=Depends(ensure_csrf),
):
    user = _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=http_status.HTTP_303_SEE_OTHER)

    title = (title or "").strip()
    if not title:
        return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)

    data = TaskCreate(title=title, priority=priority, deadline=None)
    db_create_task(db, data=data, owner_id=user.id)
    return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)


@router.post("/ui/tasks/{task_id}/delete")
def delete_task_web(request: Request, task_id: int, db: Session = Depends(get_db), _csrf=Depends(ensure_csrf)):
    user = _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=http_status.HTTP_303_SEE_OTHER)
    db_delete_task(db, task_id, owner_id=user.id)
    return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)


@router.post("/ui/bulk_delete")
def bulk_delete_web(request: Request, ids: List[int] = Form(...), db: Session = Depends(get_db), _csrf=Depends(ensure_csrf)):
    user = _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=http_status.HTTP_303_SEE_OTHER)
    db_bulk_delete(db, ids, owner_id=user.id)
    return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)


@router.post("/ui/bulk_complete")
def bulk_complete_web(request: Request, ids: List[int] = Form(...), db: Session = Depends(get_db), _csrf=Depends(ensure_csrf)):
    user = _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=http_status.HTTP_303_SEE_OTHER)
    db_bulk_complete(db, ids, owner_id=user.id)
    return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)


@router.post("/ui/tasks/{task_id}/status", response_class=HTMLResponse)
def change_status_web(request: Request, task_id: int, status_new: str = Form(...), db: Session = Depends(get_db), _csrf=Depends(ensure_csrf)):
    user = _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=http_status.HTTP_303_SEE_OTHER)
    if status_new not in {"todo", "in_progress", "done"}:
        return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)

    data = TaskUpdate(status=status_new)
    updated = db_update_task(db, task_id, data, owner_id=user.id)
    if not updated:
        return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)

    if request.headers.get("HX-Request") == "true":
        row = db_get_task(db, task_id, owner_id=user.id)
        return templates.TemplateResponse("partials/status_cell.html", {"request": request, "t": row, "csrf_token": request.cookies.get(settings.CSRF_COOKIE_NAME, "")})
    return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)


@router.post("/ui/tasks/{task_id}/priority", response_class=HTMLResponse)
def change_priority_web(request: Request, task_id: int, priority_new: int = Form(...), db: Session = Depends(get_db), _csrf=Depends(ensure_csrf)):
    user = _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=http_status.HTTP_303_SEE_OTHER)

    try:
        p = int(priority_new)
    except (TypeError, ValueError):
        p = 1
    p = max(1, min(5, p))

    data = TaskUpdate(priority=p)
    updated = db_update_task(db, task_id, data, owner_id=user.id)
    if not updated:
        return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)

    if request.headers.get("HX-Request") == "true":
        row = db_get_task(db, task_id, owner_id=user.id)
        return templates.TemplateResponse("partials/priority_cell.html", {"request": request, "t": row, "csrf_token": request.cookies.get(settings.CSRF_COOKIE_NAME, "")})
    return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)


@router.post("/ui/tasks/{task_id}/title", response_class=HTMLResponse)
def change_title_web(request: Request, task_id: int, title_new: str = Form(...), db: Session = Depends(get_db), _csrf=Depends(ensure_csrf)):
    user = _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=http_status.HTTP_303_SEE_OTHER)

    title_new = (title_new or "").strip()
    if not title_new:
        title_new = "(untitled)"
    if len(title_new) > 120:
        title_new = title_new[:120]

    data = TaskUpdate(title=title_new)
    updated = db_update_task(db, task_id, data, owner_id=user.id)
    if not updated:
        return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)

    if request.headers.get("HX-Request") == "true":
        row = db_get_task(db, task_id, owner_id=user.id)
        return templates.TemplateResponse("partials/title_cell.html", {"request": request, "t": row, "csrf_token": request.cookies.get(settings.CSRF_COOKIE_NAME, "")})
    return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)
