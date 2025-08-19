# PURPOSE: create tables on startup (if not exist).

from fastapi import FastAPI
from .routers import tasks
from .db import Base, engine
from . import db_models

app = FastAPI(title="Personal Manager — Week 1–2")

@app.get("/health")
async def health():
    return {"status": "ok"}

app.include_router(tasks.router)
