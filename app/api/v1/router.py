from fastapi import APIRouter

# Import existing routers to expose them under /api/v1 as well
from ...routers import tasks as tasks_router
from ...routers import auth as auth_router


api_router = APIRouter(prefix="/api/v1")

# Mount existing routers so endpoints are available at /api/v1/tasks and /api/v1/auth
api_router.include_router(tasks_router.router)
api_router.include_router(auth_router.router)
