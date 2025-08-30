# PURPOSE: create a SQLite engine and a Session factory.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings

# Choose engine based on DATABASE_URL; apply SQLite-specific connect_args only when needed.
db_url = settings.DATABASE_URL
connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}

engine = create_engine(db_url, connect_args=connect_args)

# SessionLocal: we open/close this per-request in FastAPI
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base: parent class for all ORM models (tables)
Base = declarative_base()
