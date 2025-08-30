# >>> PATCH: app/models.py
# What changed:
# - Replaced legacy `class Config: from_attributes = True` with Pydantic v2 style:
#   `model_config = ConfigDict(from_attributes=True)` where applicable.
# - Added minimal schemas for bulk operations.
# - Kept existing Task/User/Token schemas intact otherwise.

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Status = Literal["todo", "in_progress", "done"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    priority: int = Field(default=1, ge=1, le=5)
    deadline: datetime | None = None
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {"title": "Buy milk", "priority": 2},
                {"title": "Plan trip", "priority": 3, "deadline": "2025-12-31T18:00:00Z"},
            ]
        },
    )


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    status: Status | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    deadline: datetime | None = None
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {"status": "in_progress"},
                {"priority": 5},
                {"title": "New title"},
            ]
        },
    )


class TaskPut(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    status: Status
    priority: int = Field(ge=1, le=5)
    deadline: datetime | None = None
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {"title": "Full replace", "status": "todo", "priority": 1},
            ]
        },
    )


class Task(BaseModel):
    id: int
    title: str
    status: Status
    priority: int
    deadline: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)  # ORM -> schema


# --- Bulk operation schemas ---


class TaskIdList(BaseModel):
    """Helper schema for bulk operations with ids."""

    ids: list[int] = Field(min_length=1)


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
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"access_token": "<jwt>", "token_type": "bearer"}]}
    )
