from fastapi import APIRouter

# Import existing routers to expose them under /api/v1 as well
from ...routers import tasks as tasks_router
from ...routers import auth as auth_router


api_router = APIRouter(prefix="/api/v1")

# Mount existing routers so endpoints are available at /api/v1/tasks and /api/v1/auth
api_router.include_router(tasks_router.router)
api_router.include_router(auth_router.router)


@api_router.get("/", tags=["auth"])  # lightweight meta endpoint
def api_info():
    return {
        "name": "Personal Manager API",
        "version": "v1",
        "docs": "/docs",
        "auth": {
            "register": "/api/v1/auth/register",
            "login": "/api/v1/auth/login",
            "me": "/api/v1/auth/me",
        },
        "tasks": "/api/v1/tasks",
    }
