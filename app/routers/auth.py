# app/routers/auth.py
# PURPOSE: /auth/register, /auth/login, /auth/me

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from ..db import SessionLocal
from ..db_models import UserDB
from ..models import UserCreate, UserPublic, TokenResponse
from ..auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

# dependency to get DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
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
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
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
