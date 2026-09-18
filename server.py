import os
import json
import hmac
import hashlib
import urllib.request
import asyncio
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

# Microphone Permission Policy Middleware for Telegram In-App WebView
# In server.py

@app.middleware("http")
async def add_permission_headers(request, call_next):
    response = await call_next(request)
    response.headers["Permissions-Policy"] = "microphone=*, camera=*"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    action: str  # "mute", "unmute", "kick"
    allow_admin_unmute: bool = False

def verify_telegram_init_data(init_data: str, bot_token: str):
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

def _sync_fetch_chat_photo(chat_id: str) -> str:
    """Built-in urllib se Telegram group photo nikalta hai bina kisi external library ke"""
    if not BOT_TOKEN or not chat_id:
        return None
    try:
        get_chat_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChat?chat_id={chat_id}"
        req = urllib.request.Request(get_chat_url, headers={"User-Agent": "VoiceSpaceBot"})
        with urllib.request.urlopen(req, timeout=4) as res:
            data = json.loads(res.read().decode())
            if not data.get("ok"):
                return None

        photo_data = data.get("result", {}).get("photo", {})
        file_id = photo_data.get("big_file_id") or photo_data.get("small_file_id")
        if not file_id:
            return None

        get_file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        req_file = urllib.request.Request(get_file_url, headers={"User-Agent": "VoiceSpaceBot"})
        with urllib.request.urlopen(req_file, timeout=4) as res_file:
            file_json = json.loads(res_file.read().decode())
            if not file_json.get("ok"):
                return None

        file_path = file_json.get("result", {}).get("file_path")
        if not file_path:
            return None

        return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    except Exception as e:
        print(f"Error fetching group profile photo: {e}")
        return None

async def fetch_telegram_chat_photo(chat_id: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_fetch_chat_photo, chat_id)

@app.post("/api/get-token")
async def get_token(req: TokenRequest):
    is_valid, user_data = verify_telegram_init_data(req.init_data, BOT_TOKEN)
    if not is_valid or not user_data:
        raise HTTPException(status_code=401, detail="Invalid Telegram authentication data")

    user_id = user_data.get("id")
    first_name = user_data.get("first_name", "User")
    username = user_data.get("username", "")
    photo_url = user_data.get("photo_url", "")

    incoming_param = req.chat_id.replace("vc_", "").replace("room_", "")
    raw_chat_part = incoming_param.split("x")[0] if "x" in incoming_param else incoming_param

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

    if not room_data:
        matched_room = await rooms_collection.find_one({"active_session": incoming_param})
        if matched_room:
            room_data = matched_room
            matched_chat_id = room_data.get("chat_id")

    if not room_data:
        raise HTTPException(status_code=404, detail="Voice Space is not active.")

    active_session = room_data.get("active_session")
    if active_session and incoming_param != active_session:
        raise HTTPException(status_code=403, detail="Session expired.")

    group_title = room_data.get("title", "Voice Space")
    admins = room_data.get("admins", [])
    muted_list = room_data.get("muted_users", {})

    is_owner = user_id in OWNER_IDS
    is_admin = user_id in admins
    is_muted = str(user_id) in muted_list

    actual_chat_id = matched_chat_id or raw_chat_part
    group_photo_url = await fetch_telegram_chat_photo(actual_chat_id)

    room_name = f"room_{matched_chat_id or raw_chat_part}"

    metadata = json.dumps({
        "username": username,
        "photo_url": photo_url,
        "is_owner": is_owner,
        "is_admin": is_admin,
        "is_muted": is_muted,
        "muted_by_owner": muted_list.get(str(user_id), {}).get("by_owner", False),
        "allow_admin_unmute": muted_list.get(str(user_id), {}).get("allow_admin", False)
    })

    try:
        grants = api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=not is_muted,
            can_subscribe=True,
            can_publish_data=True
        )
    except AttributeError:
        grants = api.VideoGrant(
            room_join=True,
            room=room_name,
            can_publish=not is_muted,
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
        "group_photo_url": group_photo_url,
        "is_admin": is_admin,
        "is_owner": is_owner,
        "is_muted": is_muted
    }

@app.post("/api/moderate-user")
async def moderate_user(req: ModerateRequest):
    is_valid, user_data = verify_telegram_init_data(req.init_data, BOT_TOKEN)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Unauthorized")

    caller_id = user_data.get("id")
    incoming_param = req.chat_id.replace("vc_", "").replace("room_", "")
    raw_chat = incoming_param.split("x")[0] if "x" in incoming_param else incoming_param

    normalized_chat_id = raw_chat if raw_chat.startswith("-") else (
        raw_chat if raw_chat.startswith("-100") else f"-100{raw_chat}"
    )

    room_data = await get_room(normalized_chat_id)
    if not room_data:
        room_data = await get_room(raw_chat)
    if not room_data:
        room_data = await rooms_collection.find_one({"active_session": incoming_param})

    if not room_data:
        raise HTTPException(status_code=404, detail="Voice Space not found")

    admins = room_data.get("admins", [])
    muted_users = room_data.get("muted_users", {})
    caller_is_owner = caller_id in OWNER_IDS
    caller_is_admin = caller_id in admins

    if not caller_is_owner and not caller_is_admin:
        raise HTTPException(status_code=403, detail="Permission Denied")

    if req.target_user_id in OWNER_IDS:
        raise HTTPException(status_code=403, detail="Cannot moderate Bot Owner")

    target_is_admin = req.target_user_id in admins
    target_str = str(req.target_user_id)

    if not caller_is_owner and target_is_admin:
        raise HTTPException(status_code=403, detail="Group Admins cannot moderate other Admins")

    if req.action == "unmute" and not caller_is_owner:
        lock_info = muted_users.get(target_str, {})
        if lock_info.get("by_owner") and not lock_info.get("allow_admin"):
            raise HTTPException(status_code=403, detail="Only Bot Owner can unmute this user.")

    stored_cid = room_data.get("chat_id", normalized_chat_id)
    room_name = f"room_{stored_cid}"

    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        if req.action == "kick":
            await lk_api.room.remove_participant(
                api.RoomParticipantIdentity(room=room_name, identity=target_str)
            )
            muted_users.pop(target_str, None)

        elif req.action == "mute":
            try:
                await lk_api.room.mute_published_track(
                    api.MuteRoomTrackRequest(
                        room=room_name,
                        identity=target_str,
                        track_sid="",
                        muted=True
                    )
                )
            except Exception:
                pass

            muted_users[target_str] = {
                "by_owner": caller_is_owner,
                "allow_admin": req.allow_admin_unmute if caller_is_owner else False
            }

        elif req.action == "unmute":
            muted_users.pop(target_str, None)

        await rooms_collection.update_one(
            {"chat_id": room_data.get("chat_id")},
            {"$set": {"muted_users": muted_users}}
        )

    finally:
        await lk_api.aclose()

    return {"status": "ok", "muted_users": muted_users}

@app.post("/api/end-room")
async def end_room(req: EndRoomRequest):
    is_valid, user_data = verify_telegram_init_data(req.init_data, BOT_TOKEN)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_id = user_data.get("id")
    raw_chat = req.chat_id.replace("vc_", "").replace("room_", "")
    raw_chat = raw_chat.split("x")[0] if "x" in raw_chat else raw_chat

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
        stored_cid = room_data.get("chat_id") if room_data else normalized_chat_id
        await lk_api.room.delete_room(api.DeleteRoomRequest(room=f"room_{stored_cid}"))
        await delete_room(normalized_chat_id)
        await delete_room(raw_chat)
    except Exception:
        pass
    finally:
        await lk_api.aclose()

    return {"status": "ok"}
