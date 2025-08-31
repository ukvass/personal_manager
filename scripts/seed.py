#!/usr/bin/env python3
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.auth import hash_password
from app.db import Base, SessionLocal, engine
from app.db_models import TaskDB, UserDB


def ensure_schema():
    # For SQLite local dev this is convenient; on Postgres use Alembic migrations.
    Base.metadata.create_all(bind=engine)


def upsert_demo_user(email: str = "demo@example.com", password: str = "secret") -> UserDB:
    with SessionLocal() as db:
        user = db.execute(select(UserDB).where(UserDB.email == email)).scalar_one_or_none()
        if user is None:
            user = UserDB(email=email, password_hash=hash_password(password))
            db.add(user)
            db.commit()
            db.refresh(user)
        return user


def seed_tasks(user: UserDB, *, count: int = 6) -> None:
    presets = [
        ("Buy milk", 2, "todo"),
        ("Finish report", 3, "in_progress"),
        ("Book tickets", 1, "done"),
        ("Plan sprint", 5, "todo"),
        ("Refactor module", 2, "in_progress"),
        ("Read article", 1, "todo"),
    ][:count]
    # Use timezone-aware UTC for future-proof timestamps
    now = datetime.now(UTC)
    with SessionLocal() as db:
        existing = db.execute(select(TaskDB).where(TaskDB.owner_id == user.id)).all()
        if existing:
            return
        for i, (title, prio, status) in enumerate(presets):
            t = TaskDB(
                title=title,
                priority=prio,
                status=status,
                owner_id=user.id,
                deadline=(now + timedelta(days=7 + i)) if i % 2 == 0 else None,
            )
            db.add(t)
        db.commit()


def main():
    ensure_schema()
    email = os.getenv("SEED_EMAIL", "demo@example.com")
    password = os.getenv("SEED_PASSWORD", "secret")
    user = upsert_demo_user(email=email, password=password)
    seed_tasks(user)
    print(f"Seeded demo data for {user.email}. Password: {password}")


if __name__ == "__main__":
    main()
