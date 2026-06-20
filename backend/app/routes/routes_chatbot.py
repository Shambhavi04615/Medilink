# FILE: backend/app/routes/routes_chatbot.py

import os
import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.database.session import SessionLocal
from app.database.models import Inventory
from app.utils.jwt_handler import get_current_user  # allow all authenticated users


router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


# -------------------------------
# Load ENV variables
# -------------------------------
DEEPSEEK_URL = os.getenv("DEEPSEEK_URL")       # LLM endpoint
DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY")       # API key for DeepSeek


# -------------------------------
# Database Dependency
# -------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------
# Request & Response Schemas
# -------------------------------
class ChatQuery(BaseModel):
    message: str


class ChatReply(BaseModel):
    reply: str
    source: str  # "inventory", "template", "deepseek", "fallback"


# -------------------------------
# Inventory Search Helper
# -------------------------------
def search_inventory(db: Session, user_id: int, query: str) -> List[Inventory]:
    """
    Simple substring search in pharmacist's inventory.
    Only checks items belonging to this pharmacist.
    """
    lowered = query.lower()
    items = db.query(Inventory).filter(Inventory.user_id == user_id).all()

    results = []
    for item in items:
        if item.medicine_name and lowered in item.medicine_name.lower():
            results.append(item)

    return results


# -------------------------------
# DeepSeek API Call
# -------------------------------
def call_deepseek(message: str) -> str | None:
    """
    Call DeepSeek ONLY if API URL and KEY are set.
    """

    print("\n=== DeepSeek Debug ===")
    print("DEEPSEEK_URL =", DEEPSEEK_URL)
    print("DEEPSEEK_KEY =", DEEPSEEK_KEY)
    print("User message:", message)
    print("======================\n")

    if not DEEPSEEK_URL or not DEEPSEEK_KEY:
        print("DeepSeek not configured. Skipping.")
        return None

    try:
        response = requests.post(
            DEEPSEEK_URL,
            json={
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are MediLink AI assistant. Provide short, accurate answers."
                    },
                    {"role": "user", "content": message}
                ],
            },
            headers={
                "Authorization": f"Bearer {DEEPSEEK_KEY}",
                "Content-Type": "application/json",
            },
            timeout=15
        )

        response.raise_for_status()
        data = response.json()

        # DeepSeek-like structure
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()

        if "reply" in data:
            return str(data["reply"]).strip()

        print("DeepSeek returned unexpected format:", data)
        return None

    except Exception as e:
        print("DeepSeek Error:", e)
        return None


# -------------------------------
# Main Chatbot Endpoint
# -------------------------------
@router.post("/query", response_model=ChatReply)
def chatbot_query(
    payload: ChatQuery,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)  # ANY logged-in user allowed
):
    text = payload.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    lowered = text.lower()

    # ----------------------------------------------------
    # 1. Pharmacist inventory logic
    # ----------------------------------------------------
    if user.role == "pharmacist":
        matches = search_inventory(db, user.id, text)

        if matches:
            lines = []
            for item in matches:
                expiry = item.expiry_date.isoformat() if item.expiry_date else "N/A"
                lines.append(
                    f"{item.medicine_name} (batch {item.batch_no}) — "
                    f"{item.quantity} units, expires {expiry}"
                )

            return ChatReply(
                reply="Here is what I found in your inventory:\n" + "\n".join(lines),
                source="inventory"
            )

        # Generic stock questions
        if any(w in lowered for w in ["stock", "inventory", "available", "have"]):
            count = db.query(Inventory).filter(Inventory.user_id == user.id).count()
            return ChatReply(
                reply=f"You have {count} items in your inventory. Try asking about a specific medicine.",
                source="template"
            )

    # ----------------------------------------------------
    # 2. AI Response via DeepSeek
    # ----------------------------------------------------
    ai_reply = call_deepseek(text)
    if ai_reply:
        return ChatReply(reply=ai_reply, source="deepseek")

    # ----------------------------------------------------
    # 3. Fallback
    # ----------------------------------------------------
    fallback = (
        "I couldn't find an answer. You can ask things like:\n"
        "- 'Do I have Dolo 650?'\n"
        "- 'How many items in inventory?'\n"
        "- 'Explain blockchain verification.'\n"
        f"You said: \"{text}\""
    )

    return ChatReply(reply=fallback, source="fallback")
