from typing import Optional, Literal
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

Status = Literal["todo", "in_progress", "done"]

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

# ==== User schemas ====

class UserBase(BaseModel):
    # Simple public fields
    email: EmailStr

class UserCreate(UserBase):
    # Raw password only in create request
    password: str

class UserPublic(UserBase):
    id: int
    class Config:
        from_attributes = True  # allow ORM -> schema

class TokenResponse(BaseModel):
    # Simple JWT response
    access_token: str
    token_type: Literal["bearer"] = "bearer"