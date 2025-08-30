# app/routers/auth.py
# PURPOSE: /auth/register, /auth/login, /auth/me

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..config import settings
from ..db_models import UserDB
from ..models import TokenResponse, UserCreate, UserPublic
from ..rate_limit import limiter
from ..store_db import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_REGISTER)
def register_user(
    request: Request, response: Response, payload: UserCreate, db: Session = Depends(get_db)
):
    # Check unique email
    existing = db.query(UserDB).filter(UserDB.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = UserDB(
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserPublic(id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # OAuth2PasswordRequestForm expects fields: username, password
    user = db.query(UserDB).filter(UserDB.email == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    # subject should be the email, as get_current_user expects to look up by email
    token = create_access_token(user.email)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserPublic)
def me(user: UserPublic = Depends(get_current_user)):
    # If token is valid, user is injected
    return user
