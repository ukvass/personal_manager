# >>> PATCH: app/models.py
# What changed:
# - Replaced legacy `class Config: from_attributes = True` with Pydantic v2 style:
#   `model_config = ConfigDict(from_attributes=True)` where applicable.
# - Added minimal schemas for bulk operations.
# - Kept existing Task/User/Token schemas intact otherwise.

from typing import Optional, Literal, List
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from datetime import datetime

Status = Literal["todo", "in_progress", "done"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    priority: int = Field(default=1, ge=1, le=5)
    deadline: Optional[datetime] = None
    model_config = ConfigDict(extra='ignore')


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    status: Optional[Status] = None
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    deadline: Optional[datetime] = None
    model_config = ConfigDict(extra='ignore')


class TaskPut(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    status: Status
    priority: int = Field(ge=1, le=5)
    deadline: Optional[datetime] = None
    model_config = ConfigDict(extra='ignore')


class Task(BaseModel):
    id: int
    title: str
    status: Status
    priority: int
    deadline: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)  # ORM -> schema


# --- Bulk operation schemas ---

class TaskIdList(BaseModel):
    """Helper schema for bulk operations with ids."""
    ids: List[int] = Field(min_length=1)


# --- User / Auth schemas ---

class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    # Raw password only in create request
    password: str


class UserPublic(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)  # allow ORM -> schema


class TokenResponse(BaseModel):
    # Simple JWT response
    access_token: str
    token_type: Literal["bearer"] = "bearer"
