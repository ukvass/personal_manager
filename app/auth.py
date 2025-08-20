# >>> PATCH: app/auth.py
# Changes:
# - Replaced passlib with direct bcrypt usage to remove DeprecationWarning.
# - Public API unchanged: hash_password(), verify_password(), create_access_token(), get_current_user().
# - Reads JWT config from app.config.settings as before.

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
import bcrypt
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal
from .db_models import UserDB
from .models import UserPublic

# OAuth2 password flow
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# --- Password helpers (bcrypt, no passlib) ---

def hash_password(password: str) -> str:
    """Return a bcrypt hash for the given plain password."""
    if not isinstance(password, str):
        raise TypeError("password must be a string")
    salt = bcrypt.gensalt()
    # store as utf-8 string
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plain password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except Exception:
        # In case of malformed hash or encoding issues.
        return False


# --- DB dependency ---

def get_db():
    """Yield a SQLAlchemy Session; mirrors store_db.get_db usage pattern."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- JWT helpers ---

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(subject: str | Dict[str, Any]) -> str:
    """
    Create a signed JWT for a user.
    - `subject` can be email (str) or payload dict; we always include `sub`.
    - Expiration controlled by settings.JWT_EXPIRE_MIN.
    """
    if isinstance(subject, str):
        payload: Dict[str, Any] = {"sub": subject}
    else:
        payload = {**subject}
        payload.setdefault("sub", subject.get("email") or subject.get("sub"))

    expire = _now_utc() + timedelta(minutes=settings.JWT_EXPIRE_MIN)
    payload.update({"exp": expire})
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> UserPublic:
    """Decode JWT, load user by email (sub), return public user schema."""
    cred_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        subject = payload.get("sub")
        if subject is None:
            raise cred_error
    except JWTError:
        raise cred_error

    row = db.query(UserDB).filter(UserDB.email == subject).one_or_none()
    if row is None:
        raise cred_error

    return UserPublic(id=row.id, email=row.email)
