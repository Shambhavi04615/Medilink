# FILE: backend/app/routes/routes_users.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pydantic import BaseModel
from fastapi.security import HTTPBearer

from app.database.session import SessionLocal
from app.database.models import User
from app.utils.jwt_handler import create_access_token, decode_token

router = APIRouter(prefix="/users", tags=["Users"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Create HTTPBearer instance
security = HTTPBearer()      # ★ FIXED — this was missing


# ------------------------------
# Database Dependency
# ------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ------------------------------
# Pydantic Schemas
# ------------------------------
class RegisterUser(BaseModel):
    name: str
    email: str
    password: str
    role: str


class LoginUser(BaseModel):
    email: str
    password: str


# ------------------------------
# Register User
# ------------------------------
@router.post("/register")
def register_user(payload: RegisterUser, db: Session = Depends(get_db)):

    if payload.role not in ["manufacturer", "pharmacist", "customer"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = pwd_context.hash(payload.password)

    user = User(
        name=payload.name,
        email=payload.email,
        password=hashed_pw,
        role=payload.role
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "message": "User registered successfully",
        "user_id": user.id,
        "name": user.name,
        "role": user.role
    }


# ------------------------------
# Login User
# ------------------------------
@router.post("/login")
def login(payload: LoginUser, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not pwd_context.verify(payload.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"user_id": user.id, "role": user.role})

    return {
        "success": True,
        "message": "Login successful",
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
        "role": user.role
    }


# ------------------------------
# Get Logged-in User Using Token
# ------------------------------
@router.get("/me")
def get_user_me(credentials = Depends(security), db: Session = Depends(get_db)):

    token = credentials.credentials
    payload = decode_token(token)

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role
    }
