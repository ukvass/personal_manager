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
from ..auth import verify_password, create_access_token, get_access_token_ttl_minutes, hash_password
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
    """Common template context: user(+email) if logged in (request is auto-injected)."""
    user = _get_user_from_cookie(request, db)
    return {
        "user": user,
        "user_email": user.email if user else None,
    }


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    # user not required here; topbar can hide logout/email automatically
    ctx = {"error": None}
    from ..security import generate_csrf_token

    csrf_token = generate_csrf_token()
    ctx["csrf_token"] = csrf_token
    resp = templates.TemplateResponse(request, "login.html", ctx)
    set_csrf_cookie(resp, csrf_token)
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
    password = password or ""
    if not email or not password:
        from ..security import generate_csrf_token

        csrf_token = generate_csrf_token()
        ctx = {"error": "Email and password are required.", "csrf_token": csrf_token}
        resp = templates.TemplateResponse(
            request, "login.html", ctx, status_code=http_status.HTTP_400_BAD_REQUEST
        )
        set_csrf_cookie(resp, csrf_token)
        return resp

    user = db.query(UserDB).filter(UserDB.email == email).one_or_none()
    if not user or not verify_password(password, user.password_hash):
        from ..security import generate_csrf_token

        csrf_token = generate_csrf_token()
        ctx = {"error": "Invalid email or password.", "csrf_token": csrf_token}
        resp = templates.TemplateResponse(
            request, "login.html", ctx, status_code=http_status.HTTP_401_UNAUTHORIZED
        )
        set_csrf_cookie(resp, csrf_token)
        return resp

    token = create_access_token(email)
    minutes = get_access_token_ttl_minutes()
    resp = RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)
    resp.set_cookie("access_token", token, httponly=True, max_age=60 * minutes, samesite="lax")
    return resp


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    # Render registration form with CSRF token
    ctx = {"error": None}
    from ..security import generate_csrf_token

    csrf_token = generate_csrf_token()
    ctx["csrf_token"] = csrf_token
    resp = templates.TemplateResponse(request, "register.html", ctx)
    set_csrf_cookie(resp, csrf_token)
    return resp


@router.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    _csrf=Depends(ensure_csrf),
):
    email = (email or "").strip()
    password = password or ""
    if not email or not password:
        from ..security import generate_csrf_token

        csrf_token = generate_csrf_token()
        ctx = {"error": "Email and password are required.", "csrf_token": csrf_token}
        resp = templates.TemplateResponse(
            request, "register.html", ctx, status_code=http_status.HTTP_400_BAD_REQUEST
        )
        set_csrf_cookie(resp, csrf_token)
        return resp

    # Check uniqueness
    exists = db.query(UserDB).filter(UserDB.email == email).one_or_none()
    if exists:
        from ..security import generate_csrf_token

        csrf_token = generate_csrf_token()
        ctx = {"error": "Email already registered.", "csrf_token": csrf_token}
        resp = templates.TemplateResponse(
            request, "register.html", ctx, status_code=http_status.HTTP_400_BAD_REQUEST
        )
        set_csrf_cookie(resp, csrf_token)
        return resp

    # Create user
    row = UserDB(email=email, password_hash=hash_password(password))
    db.add(row)
    db.commit()
    db.refresh(row)

    # Issue login cookie
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
        status=status,
        priority=priority,
        q=q,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_dir=order_dir,
    )

    ctx.update(
        {
            "tasks": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "status": status,
            "priority": priority,
            "q": q or "",
            "order_by": order_by,
            "order_dir": order_dir,
        }
    )
    # Ensure CSRF cookie/token for forms on the page
    from ..security import generate_csrf_token

    token = request.cookies.get(settings.CSRF_COOKIE_NAME)
    if not token:
        token = generate_csrf_token()
    ctx["csrf_token"] = token
    resp = templates.TemplateResponse(request, "index.html", ctx)
    set_csrf_cookie(resp, token)
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
def delete_task_web(
    request: Request, task_id: int, db: Session = Depends(get_db), _csrf=Depends(ensure_csrf)
):
    user = _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=http_status.HTTP_303_SEE_OTHER)
    db_delete_task(db, task_id, owner_id=user.id)
    return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)


@router.post("/ui/bulk_delete")
def bulk_delete_web(
    request: Request,
    ids: List[int] = Form(...),
    db: Session = Depends(get_db),
    _csrf=Depends(ensure_csrf),
):
    user = _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=http_status.HTTP_303_SEE_OTHER)
    db_bulk_delete(db, ids, owner_id=user.id)
    return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)


@router.post("/ui/bulk_complete")
def bulk_complete_web(
    request: Request,
    ids: List[int] = Form(...),
    db: Session = Depends(get_db),
    _csrf=Depends(ensure_csrf),
):
    user = _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=http_status.HTTP_303_SEE_OTHER)
    db_bulk_complete(db, ids, owner_id=user.id)
    return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)


@router.post("/ui/tasks/{task_id}/status", response_class=HTMLResponse)
def change_status_web(
    request: Request,
    task_id: int,
    status_new: str = Form(...),
    db: Session = Depends(get_db),
    _csrf=Depends(ensure_csrf),
):
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
        return templates.TemplateResponse(
            request,
            "partials/status_cell.html",
            {"t": row, "csrf_token": request.cookies.get(settings.CSRF_COOKIE_NAME, "")},
        )
    return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)


@router.post("/ui/tasks/{task_id}/priority", response_class=HTMLResponse)
def change_priority_web(
    request: Request,
    task_id: int,
    priority_new: int = Form(...),
    db: Session = Depends(get_db),
    _csrf=Depends(ensure_csrf),
):
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
        return templates.TemplateResponse(
            request,
            "partials/priority_cell.html",
            {"t": row, "csrf_token": request.cookies.get(settings.CSRF_COOKIE_NAME, "")},
        )
    return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)


@router.post("/ui/tasks/{task_id}/title", response_class=HTMLResponse)
def change_title_web(
    request: Request,
    task_id: int,
    title_new: str = Form(...),
    db: Session = Depends(get_db),
    _csrf=Depends(ensure_csrf),
):
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
        return templates.TemplateResponse(
            request,
            "partials/title_cell.html",
            {"t": row, "csrf_token": request.cookies.get(settings.CSRF_COOKIE_NAME, "")},
        )
    return RedirectResponse(url="/", status_code=http_status.HTTP_303_SEE_OTHER)
