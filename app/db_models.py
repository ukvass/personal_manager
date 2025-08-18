# PURPOSE: define how a Task row looks in the database.

from sqlalchemy import Column, Integer, String, DateTime
from .db import Base
from datetime import datetime, timezone


def now_utc():
    """Return timezone-aware UTC datetime (stored in DB)."""
    return datetime.now(timezone.utc)


class TaskDB(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(String, default="todo")  # todo | in_progress | done
    priority = Column(Integer, default=1)     # 1..5
    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc)