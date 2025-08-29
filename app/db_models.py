# PURPOSE: define how a Task row looks in the database.

from sqlalchemy import Column, Integer, String, DateTime, Index, ForeignKey
from sqlalchemy.orm import relationship
from .db import Base
from datetime import datetime, timezone


def now_utc():
    """Return timezone-aware UTC datetime (stored in DB)."""
    return datetime.now(timezone.utc)


class TaskDB(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    status = Column(String, default="todo")  # todo | in_progress | done
    priority = Column(Integer, default=1)     # 1..5
    deadline = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # task owner

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)  # unique login
    password_hash = Column(String, nullable=False)  # store hash, not raw password
    created_at = Column(DateTime, default=now_utc)
    # relationship to tasks
    tasks = relationship("TaskDB", backref="owner")

# Helpful indexes for filtering/sorting
Index("ix_tasks_status", TaskDB.status)
Index("ix_tasks_priority", TaskDB.priority)
Index("ix_tasks_deadline", TaskDB.deadline)
