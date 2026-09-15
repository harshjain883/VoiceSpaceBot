import os
import json
import hmac
import hashlib
from urllib.parse import parse_qsl
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from livekit import api
from dotenv import load_dotenv

from db import get_room, delete_room, rooms_collection

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

# Static files mount
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

    # Parse incoming parameter (e.g. 4362672803x7f2a)
    incoming_param = req.chat_id.replace("vc_", "").replace("room_", "")
    
    if "x" in incoming_param:
        raw_chat_part, _ = incoming_param.split("x", 1)
    else:
        raw_chat_part = incoming_param

    # Multi-format ID check to guarantee title resolution
    candidate_ids = [
        raw_chat_part,
        f"-{raw_chat_part}",
        f"-100{raw_chat_part}" if not raw_chat_part.startswith("-") else raw_chat_part
    ]

    room_data = None
    matched_chat_id = None
    for cid in candidate_ids:
        room_data = await get_room(cid)
        if room_data:
            matched_chat_id = cid
            break

    # Direct search by active session key if ID check misses
    if not room_data:
        matched_room = await rooms_collection.find_one({"active_session": incoming_param})
        if matched_room:
            room_data = matched_room
            matched_chat_id = room_data.get("chat_id")

    if not room_data:
        raise HTTPException(status_code=404, detail="Voice Space is not active.")

    # 2. Dynamic Single-Session Key Verification
    active_session = room_data.get("active_session")
    if active_session and incoming_param != active_session:
        raise HTTPException(status_code=403, detail="Session expired. Please join using the newest group link.")

    group_title = room_data.get("title", "Voice Space")
    admins = room_data.get("admins", [])

    is_owner = user_id in OWNER_IDS
    is_admin = user_id in admins

    room_name = f"room_{matched_chat_id or raw_chat_part}"

    metadata = json.dumps({
        "username": username,
        "photo_url": photo_url,
        "is_owner": is_owner,
        "is_admin": is_admin
    })

    # SDK-compatible grant resolution
    try:
        grants = api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True
        )
    except AttributeError:
        grants = api.VideoGrant(
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
        .with_grants(grants)
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
    if "x" in raw_chat:
        raw_chat = raw_chat.split("x")[0]

    normalized_chat_id = raw_chat if raw_chat.startswith("-") else (
        raw_chat if raw_chat.startswith("-100") else f"-100{raw_chat}"
    )

    room_data = await get_room(normalized_chat_id)
    if not room_data:
        room_data = await get_room(raw_chat)

    admins = room_data.get("admins", []) if room_data else []

    if user_id not in OWNER_IDS and user_id not in admins:
        raise HTTPException(status_code=403, detail="Permission Denied")

    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        room_name = f"room_{normalized_chat_id}"
        await lk_api.room.delete_room(api.DeleteRoomRequest(room=room_name))
        await delete_room(normalized_chat_id)
        await delete_room(raw_chat)
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
    if "x" in raw_chat:
        raw_chat = raw_chat.split("x")[0]

    normalized_chat_id = raw_chat if raw_chat.startswith("-") else (
        raw_chat if raw_chat.startswith("-100") else f"-100{raw_chat}"
    )

    room_data = await get_room(normalized_chat_id)
    if not room_data:
        room_data = await get_room(raw_chat)

    admins = room_data.get("admins", []) if room_data else []

    if caller_id not in OWNER_IDS and caller_id not in admins:
        raise HTTPException(status_code=403, detail="Permission Denied")

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
    
