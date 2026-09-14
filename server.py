import os
import hmac
import hashlib
import json
from urllib.parse import parse_qsl
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from livekit import api
from db import get_room, delete_room

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

raw_owners = os.getenv("OWNER_ID", "")
OWNER_IDS = [int(x.strip()) for x in raw_owners.split(",") if x.strip().isdigit()]

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

def verify_telegram_init_data(init_data: str) -> dict:
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
        return json.loads(parsed_data.get("user", "{}"))
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Telegram authentication: {e}")

class JoinRequest(BaseModel):
    chat_id: str
    init_data: str

class ModerateRequest(BaseModel):
    chat_id: str
    init_data: str
    target_user_id: int
    action: str

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

    chat_id = str(req.chat_id)
    room_data = await get_room(chat_id)
    room_admins = room_data.get("admins", []) if room_data else []

    is_owner = user_id in OWNER_IDS
    is_admin = is_owner or (user_id in room_admins)

    token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    token.with_identity(str(user_id))
    token.with_name(name)
    token.with_metadata(json.dumps({
        "username": username,
        "photo_url": photo_url,
        "is_admin": is_admin,
        "is_owner": is_owner
    }))

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
        "is_owner": is_owner
    }

@app.post("/api/moderate-user")
async def moderate_user(req: ModerateRequest):
    caller = verify_telegram_init_data(req.init_data)
    caller_id = caller.get("id")
    chat_id = str(req.chat_id)
    target_id = req.target_user_id

    room_data = await get_room(chat_id)
    room_admins = room_data.get("admins", []) if room_data else []

    caller_is_owner = caller_id in OWNER_IDS
    caller_is_admin = caller_is_owner or (caller_id in room_admins)

    if not caller_is_admin:
        raise HTTPException(status_code=403, detail="Unauthorized")

    if target_id in OWNER_IDS:
        raise HTTPException(status_code=403, detail="Forbidden: Bot Owner cannot be moderated!")

    if not caller_is_owner and target_id in room_admins:
        raise HTTPException(status_code=403, detail="Regular admins cannot moderate other admins!")

    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        room_name = f"room_{chat_id}"
        if req.action == "kick":
            await lk_api.room.remove_participant(
                api.RoomParticipantIdentity(room=room_name, identity=str(target_id))
            )
            return {"status": "kicked"}
        elif req.action == "mute":
            await lk_api.room.mute_published_track(
                api.MuteRoomTrackRequest(
                    room=room_name,
                    identity=str(target_id),
                    track_sid="",
                    muted=True
                )
            )
            return {"status": "muted"}
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
    finally:
        await lk_api.aclose()

@app.post("/api/end-room")
async def end_room(req: JoinRequest):
    user = verify_telegram_init_data(req.init_data)
    user_id = user.get("id")
    chat_id = str(req.chat_id)

    room_data = await get_room(chat_id)
    is_owner = user_id in OWNER_IDS
    is_admin = is_owner or (user_id in (room_data.get("admins", []) if room_data else []))

    if not is_admin:
        raise HTTPException(status_code=403, detail="Unauthorized")

    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        await lk_api.room.delete_room(api.DeleteRoomRequest(room=f"room_{chat_id}"))
        await delete_room(chat_id)
    finally:
        await lk_api.aclose()

    return {"status": "room_closed"}
    
