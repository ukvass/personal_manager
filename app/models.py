from typing import Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime, timezone

Status = Literal["todo", "in_progress", "done"]

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    priority: int = Field(default=1, ge=1, le=5)
    deadline: Optional[datetime] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[Status] = None
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    deadline: Optional[datetime] = None

class TaskPut(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    status: Status
    priority: int = Field(ge=1, le=5)
    deadline: Optional[datetime] = None

class Task(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: Status
    priority: int
    created_at: datetime
    updated_at: datetime
