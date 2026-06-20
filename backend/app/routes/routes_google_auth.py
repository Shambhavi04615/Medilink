# FILE: backend/app/routes/routes_google_auth.py

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
import os
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.database.models import User
from app.utils.jwt_handler import create_access_token

router = APIRouter(prefix="/auth/google", tags=["Google OAuth"])

# ------------------------------
# OAuth Setup
# ------------------------------
oauth = OAuth()

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ------------------------------
# Google Login
# ------------------------------
@router.get("/login")
async def google_login(request: Request):
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    return await oauth.google.authorize_redirect(request, redirect_uri)


# ------------------------------
# Google Callback
# ------------------------------
@router.get("/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google Auth failed: {e}")

    user_info = token.get("userinfo")
    if user_info is None:
        raise HTTPException(status_code=400, detail="Failed to fetch Google user info")

    google_email = user_info["email"]
    google_name = user_info.get("name", "Google User")

    # Check if user already exists
    user = db.query(User).filter(User.email == google_email).first()

    if not user:
        # Auto-create user with default 'customer' role
        user = User(
            name=google_name,
            email=google_email,
            role="customer",   # default role
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Issue a JWT token (your normal user token)
    jwt_token = create_access_token({"user_id": user.id, "role": user.role})

    # Redirect to frontend with token
    frontend_url = f"http://localhost:5500/#/auth/google/success?token={jwt_token}&name={user.name}&role={user.role}"

    return RedirectResponse(frontend_url)
