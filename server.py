import os
import json
import hmac
import hashlib
from urllib.parse import parse_qsl
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from livekit import api
from dotenv import load_dotenv

from db import get_room, delete_room

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

raw_owners = os.getenv("OWNER_ID", "")
OWNER_IDS = [int(x.strip()) for x in raw_owners.split(",") if x.strip().isdigit()]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (index.html)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


class TokenRequest(BaseModel):
    chat_id: str
    init_data: str


class EndRoomRequest(BaseModel):
    chat_id: str
    init_data: str


class ModerateRequest(BaseModel):
    chat_id: str
    init_data: str
    target_user_id: int
    action: str  # "mute" or "kick"


def verify_telegram_init_data(init_data: str, bot_token: str):
    """Verifies Telegram WebApp initData HMAC-SHA256 signature"""
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        hash_check = parsed.pop("hash", None)
        if not hash_check:
            return False, {}

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        calc_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if calc_hash == hash_check:
            user_data = json.loads(parsed.get("user", "{}"))
            return True, user_data
        return False, {}
    except Exception:
        return False, {}


@app.post("/api/get-token")
async def get_token(req: TokenRequest):
    # 1. Telegram WebApp Data Validation
    is_valid, user_data = verify_telegram_init_data(req.init_data, BOT_TOKEN)
    if not is_valid or not user_data:
        raise HTTPException(status_code=401, detail="Invalid Telegram authentication data")

    user_id = user_data.get("id")
    first_name = user_data.get("first_name", "User")
    username = user_data.get("username", "")
    photo_url = user_data.get("photo_url", "")

    # Normalize Chat ID
    raw_chat = req.chat_id.replace("vc_", "").replace("room_", "")
    normalized_chat_id = raw_chat if raw_chat.startswith("-") else f"-{raw_chat}"

    # 2. Fetch Room from DB
    room_data = await get_room(normalized_chat_id)
    if not room_data:
        # Fallback query for id format variations
        room_data = await get_room(raw_chat)

    group_title = room_data.get("title", "Voice Space") if room_data else "Voice Space"
    admins = room_data.get("admins", []) if room_data else []

    is_owner = user_id in OWNER_IDS
    is_admin = user_id in admins

    # 3. Build LiveKit Room Token
    room_name = f"room_{normalized_chat_id}"

    # Metadata attached to the user track
    metadata = json.dumps({
        "username": username,
        "photo_url": photo_url,
        "is_owner": is_owner,
        "is_admin": is_admin
    })

    try:
        # FIXED: Compatible grant creation across LiveKit SDK versions
        grant = api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True
        )

        token = (
            api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            .with_identity(str(user_id))
            .with_name(first_name)
            .with_metadata(metadata)
            .with_grants(grant)
            .to_jwt()
        )
    except AttributeError:
        # Fallback if api.VideoGrants is at sub-level
        from livekit.api import VideoGrants
        grant = VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True
        )
        token = (
            api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            .with_identity(str(user_id))
            .with_name(first_name)
            .with_metadata(metadata)
            .with_grants(grant)
            .to_jwt()
        )

    return {
        "token": token,
        "livekit_url": LIVEKIT_URL,
        "group_title": group_title,
        "is_admin": is_admin,
        "is_owner": is_owner
    }


@app.post("/api/end-room")
async def end_room(req: EndRoomRequest):
    is_valid, user_data = verify_telegram_init_data(req.init_data, BOT_TOKEN)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_id = user_data.get("id")
    raw_chat = req.chat_id.replace("vc_", "").replace("room_", "")
    normalized_chat_id = raw_chat if raw_chat.startswith("-") else f"-{raw_chat}"

    room_data = await get_room(normalized_chat_id)
    admins = room_data.get("admins", []) if room_data else []

    if user_id not in OWNER_IDS and user_id not in admins:
        raise HTTPException(status_code=403, detail="Permission Denied")

    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        room_name = f"room_{normalized_chat_id}"
        await lk_api.room.delete_room(api.DeleteRoomRequest(room=room_name))
        await delete_room(normalized_chat_id)
    except Exception:
        pass
    finally:
        await lk_api.aclose()

    return {"status": "ok"}


@app.post("/api/moderate-user")
async def moderate_user(req: ModerateRequest):
    is_valid, user_data = verify_telegram_init_data(req.init_data, BOT_TOKEN)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Unauthorized")

    caller_id = user_data.get("id")
    raw_chat = req.chat_id.replace("vc_", "").replace("room_", "")
    normalized_chat_id = raw_chat if raw_chat.startswith("-") else f"-{raw_chat}"

    room_data = await get_room(normalized_chat_id)
    admins = room_data.get("admins", []) if room_data else []

    if caller_id not in OWNER_IDS and caller_id not in admins:
        raise HTTPException(status_code=403, detail="Permission Denied")

    # Prevent non-owner from kicking/muting owner
    if req.target_user_id in OWNER_IDS:
        raise HTTPException(status_code=403, detail="Cannot moderate Bot Owner")

    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    room_name = f"room_{normalized_chat_id}"
    try:
        if req.action == "kick":
            await lk_api.room.remove_participant(
                api.RoomParticipantIdentity(room=room_name, identity=str(req.target_user_id))
            )
        elif req.action == "mute":
            await lk_api.room.mute_published_track(
                api.MuteRoomTrackRequest(
                    room=room_name,
                    identity=str(req.target_user_id),
                    track_sid="",
                    muted=True
                )
            )
    finally:
        await lk_api.aclose()

    return {"status": "ok"}
    
