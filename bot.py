import os
import asyncio
from pyrogram import Client, filters, types
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from pyrogram.enums import ChatMemberStatus
from dotenv import load_dotenv
from livekit import api

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
WEBAPP_URL = os.getenv("WEBAPP_URL").rstrip("/")

raw_owners = os.getenv("OWNER_ID", "")
OWNER_IDS = [int(x.strip()) for x in raw_owners.split(",") if x.strip().isdigit()]

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

from server import ACTIVE_ROOMS

bot = Client(
    "VoiceSpaceBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@bot.on_message(filters.command("vc") & (filters.group | filters.supergroup))
async def start_vc_command(client: Client, message: types.Message):
    chat = message.chat
    caller_id = message.from_user.id

    # Verify caller is admin or owner
    caller_member = await chat.get_member(caller_id)
    is_owner = caller_id in OWNER_IDS
    is_admin = caller_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

    if not is_owner and not is_admin:
        return await message.reply_text("❌ Only group administrators can start the voice space.")

    # Extract all group admins
    admin_ids = []
    async for member in chat.get_members(filter=pyrogram.enums.ChatMembersFilter.ADMINISTRATORS):
        admin_ids.append(member.user.id)

    ACTIVE_ROOMS[str(chat.id)] = {
        "title": chat.title,
        "admins": admin_ids
    }

    twa_url = f"{WEBAPP_URL}?chat_id={chat.id}"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎙 Join Voice Space", web_app=WebAppInfo(url=twa_url))]
    ])

    await message.reply_text(
        f"🎧 **Voice Space Started for {chat.title}**\n\n"
        f"👥 Multi-group parallel engine active.\n"
        f"Click below to join:",
        reply_markup=markup
    )

@bot.on_message(filters.command("activevc") & filters.user(OWNER_IDS) & filters.private)
async def owner_active_vc_panel(client: Client, message: types.Message):
    if not ACTIVE_ROOMS:
        return await message.reply_text("📭 Currently no active voice spaces in any group.")

    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        text = "🎛 **Owner Control Panel - Active Voice Spaces**\n\n"
        keyboard = []

        for chat_id, data in list(ACTIVE_ROOMS.items()):
            room_name = f"room_{chat_id}"
            member_count = 0
            try:
                participants = await lk_api.room.list_participants(api.ListParticipantsRequest(room=room_name))
                member_count = len(participants)
            except Exception:
                pass

            group_title = data.get("title", f"Chat {chat_id}")
            twa_link = f"https://t.me/{BOT_USERNAME}?startapp=vc_{chat_id}" if BOT_USERNAME else f"{WEBAPP_URL}?chat_id={chat_id}"

            text += f"📌 **{group_title}**\n"
            text += f"👥 Active Members: `ˠ{member_count}`\n"
            text += f"🔗 Link: `{twa_url := f'{WEBAPP_URL}?chat_id={chat_id}'}`\n\n"

            keyboard.append([InlineKeyboardButton(f"🚀 Join {group_title[:15]}", web_app=WebAppInfo(url=twa_url))])

        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)
    finally:
        await lk_api.aclose()

if __name__ == "__main__":
    bot.run()
    
