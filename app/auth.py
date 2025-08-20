# app/auth.py
# PURPOSE: password hashing/verification + JWT issue/verify

from datetime import datetime, timedelta, timezone
from typing import Optional

from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .db import SessionLocal
from .db_models import UserDB
from .models import UserPublic

# Password hashing context (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 bearer token in Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# WARNING: for demo/dev only; in production put it in env variable
JWT_SECRET = "CHANGE_THIS_SECRET_IN_PROD"
JWT_ALG = "HS256"
JWT_EXPIRE_MIN = 60 * 24  # 24h

def hash_password(raw: str) -> str:
    """Hash plain password."""
    return pwd_context.hash(raw)

def verify_password(raw: str, hashed: str) -> bool:
    """Verify plain password against hash."""
    return pwd_context.verify(raw, hashed)

def create_access_token(user_id: int, expires_minutes: int = JWT_EXPIRE_MIN) -> str:
    """Issue JWT with user id in 'sub' claim."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expires_minutes)
    payload = {"sub": str(user_id), "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

# FastAPI dependency: get DB session
def get_db():
    """Yield a SQLAlchemy Session (same pattern as store_db.get_db)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserPublic:
    """Decode JWT, load user from DB, return public user schema."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        sub = payload.get("sub")
        if sub is None:
            raise credentials_error
        user_id = int(sub)
    except (JWTError, ValueError):
        raise credentials_error

    user_row = db.get(UserDB, user_id)
    if not user_row:
        raise credentials_error

    return UserPublic(id=user_row.id, email=user_row.email)
