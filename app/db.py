# PURPOSE: create a SQLite engine and a Session factory.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite file placed in project root. For absolute path, use sqlite:///C:/... etc.
SQLALCHEMY_DATABASE_URL = "sqlite:///./tasks.db"

# connect_args is needed for SQLite when used in a single-threaded dev server
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# SessionLocal: we open/close this per-request in FastAPI
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base: parent class for all ORM models (tables)
Base = declarative_base()