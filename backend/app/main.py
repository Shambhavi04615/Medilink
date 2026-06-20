# FILE: backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import os

from app.config import *
from app.database.connection import init_db

# Routers (CLEANED)
from app.routes.routes_users import router as users_router
from app.routes.manufacturer.routes_blockchain import router as blockchain_router
from app.routes.pharmacist.routes_inventory import router as inventory_router
from app.routes.pharmacist.routes_prices import router as prices_router
from app.routes.manufacturer.routes_batch_events import router as batch_events_router
from app.routes.customer.routes_alerts import router as alerts_router
from app.routes.customer.routes_customer_dashboard import router as customer_dashboard_router
from app.routes.notifications.routes_notifications import router as notifications_router
from app.routes.analytics.routes_dashboard import router as analytics_router
from app.routes.iot_route import router as iot_router
from app.routes.routes_google_auth import router as google_auth_router
from app.routes.routes_chatbot import router as chatbot_router

# ----------------------------------------------------
# Initialize FastAPI
# ----------------------------------------------------
app = FastAPI(
    title="MediLink Blockchain Backend",
    description="Unified Pharma Supply Chain",
    version="2.0.0"
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "SUPER_SECRET_KEY")
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Initialize DB
init_db()

# ----------------------------------------------------
# Include Routers (ONLY CLEANED ONES)
# ----------------------------------------------------
app.include_router(users_router)
app.include_router(blockchain_router)
app.include_router(inventory_router)
app.include_router(prices_router)
app.include_router(batch_events_router)
app.include_router(alerts_router)
app.include_router(customer_dashboard_router)
app.include_router(notifications_router)
app.include_router(analytics_router)
app.include_router(iot_router)
app.include_router(google_auth_router)
app.include_router(chatbot_router)

# QR Serving
app.mount("/qrcodes", StaticFiles(directory="app/qrcodes"), name="qrcodes")

# Root
@app.get("/")
def home():
    return {"status": "OK", "message": "MediLink backend running"}
