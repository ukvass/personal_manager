from fastapi import FastAPI
from .routers import tasks

app = FastAPI(title="Personal Manager — Week 1–2")

@app.get("/health")
async def health():
    return {"status": "ok"}

app.include_router(tasks.router)
