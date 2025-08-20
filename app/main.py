# PURPOSE: основной модуль приложения.

from fastapi import FastAPI
from .routers import tasks
from .routers import auth as auth_router
from . import db_models

app = FastAPI(title="Personal Manager")

app.include_router(auth_router.router)
app.include_router(tasks.router)
