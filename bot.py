import os
import asyncio
from pyrogram import Client, filters, types
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from pyrogram.enums import ChatMemberStatus, ChatMembersFilter
from pyrogram.errors import RPCError
from dotenv import load_dotenv
from livekit import api

from db import set_room, get_all_rooms, get_room

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "").replace("@", "").strip()
APP_SHORT_NAME = os.getenv("APP_SHORT_NAME", "myapp").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").rstrip("/")

raw_owners = os.getenv("OWNER_ID", "")
OWNER_IDS = [int(x.strip()) for x in raw_owners.split(",") if x.strip().isdigit()]

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

bot = Client(
    "VoiceSpaceBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# 1. /start HANDLER (For Private DMs & Startapp Redirects)
@bot.on_message(filters.command("start") & filters.private)
async def start_private_handler(client: Client, message: types.Message):
    args = message.command
    
    # Agar user startapp link se aaya hai (e.g. /start room_123456)
    if len(args) > 1:
        raw_target = args[1]
        chat_id = raw_target.replace("vc_", "").replace("room_", "")
        if not chat_id.startswith("-"):
            chat_id = f"-{chat_id}"
            
        twa_url = f"{WEBAPP_URL}?chat_id={chat_id}"
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎙 Open Voice Space", web_app=WebAppInfo(url=twa_url))]
        ])
        return await message.reply_text(
            "🚀 **Voice Space Ready!**\n\nNeeche button par click karke Voice Space join karein:",
            reply_markup=markup
        )

    # Normal /start in DM
    help_text = (
        f"👋 **Namaste {message.from_user.first_name}!**\n\n"
        "Main Telegram Voice Space Bot hoon.\n\n"
        "📌 **Kaise use karein?**\n"
        "1. Mujhe apne group mein **Admin** banayein (Invite Users permission ke sath).\n"
        "2. Group mein `/vc` command send karein.\n"
        "3. Mini App launch ho jayega HD Voice call ke sath!"
    )
    await message.reply_text(help_text)


# 2. /vc COMMAND (For Groups)
@bot.on_message(filters.command("vc") & filters.group)
async def start_vc_command(client: Client, message: types.Message):
    chat = message.chat
    caller_id = message.from_user.id

    # Admin check
    bot_member = await chat.get_member("me")
    if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
        return await message.reply_text(
            "❌ **Bot Admin nahi hai!**\n\n"
            "Kripya mujhe group ka Administrator banayein."
        )

    privileges = bot_member.privileges
    if not (privileges and privileges.can_invite_users):
        return await message.reply_text(
            "⚠️ **Permission Missing!**\n\n"
            "Bot ko **Invite Users via Link** permission chahiye."
        )

    caller_member = await chat.get_member(caller_id)
    is_owner = caller_id in OWNER_IDS
    is_admin = caller_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

    if not is_owner and not is_admin:
        return await message.reply_text("❌ Sirf group admins Voice Space start kar sakte hain.")

    # Invite Link
    invite_link = chat.invite_link
    if not invite_link:
        try:
            link_obj = await client.create_chat_invite_link(chat.id, name="Voice Space")
            invite_link = link_obj.invite_link
        except RPCError:
            invite_link = f"https://t.me/{chat.username}" if chat.username else "No link accessible"

    # Sync Admins
    admin_ids = []
    async for member in chat.get_members(filter=ChatMembersFilter.ADMINISTRATORS):
        admin_ids.append(member.user.id)

    # Save to DB
    await set_room(
        chat_id=str(chat.id),
        title=chat.title,
        admins=admin_ids,
        invite_link=invite_link
    )

    clean_chat_id = str(chat.id).replace("-100", "").replace("-", "")
    
    # Direct Mini App Link (Attachment/Webapp Drawer format)
    direct_app_url = f"https://t.me/{BOT_USERNAME}/{APP_SHORT_NAME}?startapp={clean_chat_id}"
    dm_fallback_url = f"https://t.me/{BOT_USERNAME}?start=vc_{clean_chat_id}"

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎙 Join Voice Space (Mini App)", url=direct_app_url)],
        [InlineKeyboardButton("💬 Join via Bot DM", url=dm_fallback_url)]
    ])

    await message.reply_text(
        f"🎧 **Voice Space Started: {chat.title}**\n\n"
        f"👑 **Admins:** Synced\n"
        f"🔊 **Audio Engine:** LiveKit WebRTC (Lag-Free)\n\n"
        f"Neeche button dabakar join karein:",
        reply_markup=markup
    )


# 3. /activevc COMMAND (Owner Only Panel)
@bot.on_message(filters.command("activevc") & filters.user(OWNER_IDS) & filters.private)
async def owner_active_vc_panel(client: Client, message: types.Message):
    active_rooms = await get_all_rooms()
    if not active_rooms:
        return await message.reply_text("📭 Abhi koi bhi Voice Space active nahi hai.")

    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        text = "🎛 **Active Voice Spaces Panel**\n\n"
        keyboard = []

        for data in active_rooms:
            chat_id = data.get("chat_id")
            room_name = f"room_{chat_id}"
            member_count = 0
            try:
                participants = await lk_api.room.list_participants(
                    api.ListParticipantsRequest(room=room_name)
                )
                member_count = len(participants)
            except Exception:
                pass

            group_title = data.get("title", f"Chat {chat_id}")
            clean_id = str(chat_id).replace("-100", "").replace("-", "")
            twa_url = f"{WEBAPP_URL}?chat_id={chat_id}"

            text += f"📌 **Group:** `{group_title}`\n"
            text += f"🆔 **Chat ID:** `{chat_id}`\n"
            text += f"👥 **Members:** `{member_count}`\n"
            text += "────────────────────────\n"

            keyboard.append([
                InlineKeyboardButton(f"🎙 Join VC ({group_title[:10]})", web_app=WebAppInfo(url=twa_url))
            ])

        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    finally:
        await lk_api.aclose()


if __name__ == "__main__":
    print("---------------------------------------")
    print(">>> Voice Space Pyrogram Bot Started! <<<")
    print("---------------------------------------")
    bot.run()
    
