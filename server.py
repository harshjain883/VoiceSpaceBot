import os
import hmac
import hashlib
import json
from urllib.parse import parse_qsl
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from livekit import api

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

app = FastAPI(title="Telegram Voice Space Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Shared storage for active rooms & admins (Populated by bot)
# Format: { chat_id: [admin_user_id1, admin_user_id2] }
ACTIVE_ROOMS = {}

def verify_telegram_init_data(init_data: str) -> dict:
    """Verifies Telegram WebApp initData HMAC-SHA256 signature."""
    try:
        parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
        hash_to_check = parsed_data.pop("hash", None)
        if not hash_to_check:
            raise ValueError("Hash missing")

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calculated_hash, hash_to_check):
            raise ValueError("Hash mismatch")

        user_info = json.loads(parsed_data.get("user", "{}"))
        return user_info
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Telegram authentication: {e}")

class JoinRequest(BaseModel):
    chat_id: str
    init_data: str

@app.get("/")
async def index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"status": "running"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/api/get-token")
async def get_token(req: JoinRequest):
    user = verify_telegram_init_data(req.init_data)
    user_id = user.get("id")
    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or f"User_{user_id}"
    username = user.get("username", "")
    photo_url = user.get("photo_url", "")

    chat_id = req.chat_id
    room_admins = ACTIVE_ROOMS.get(str(chat_id), [])
    is_admin = user_id in room_admins

    # Generate LiveKit Token
    token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    token.with_identity(str(user_id))
    token.with_name(name)
    token.with_metadata(json.dumps({
        "username": username,
        "photo_url": photo_url,
        "is_admin": is_admin
    }))

    # Admin gets full rights, normal users get standard speak rights
    grant = api.VideoGrant(
        room_join=True,
        room=f"room_{chat_id}",
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True
    )
    token.with_grants(grant)

    return {
        "token": token.to_jwt(),
        "livekit_url": LIVEKIT_URL,
        "is_admin": is_admin,
        "user_info": {
            "id": user_id,
            "name": name,
            "username": username,
            "photo_url": photo_url
        }
    }

@app.post("/api/end-room")
async def end_room(req: JoinRequest):
    user = verify_telegram_init_data(req.init_data)
    user_id = user.get("id")
    chat_id = req.chat_id

    room_admins = ACTIVE_ROOMS.get(str(chat_id), [])
    if user_id not in room_admins:
        raise HTTPException(status_code=403, detail="Only admins can end this room")

    # Terminate LiveKit Room
    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        await lk_api.room.delete_room(api.DeleteRoomRequest(room=f"room_{chat_id}"))
        ACTIVE_ROOMS.pop(str(chat_id), None)
    finally:
        await lk_api.aclose()

    return {"status": "room_closed"}
  
