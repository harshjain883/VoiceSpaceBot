import os
import asyncio
from pyrogram import Client, filters, types
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from pyrogram.enums import ChatMemberStatus, ChatMembersFilter
from pyrogram.errors import RPCError
from dotenv import load_dotenv
from livekit import api

from db import set_room, get_all_rooms

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "Gcvoicechatbot").replace("@", "").strip()
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

@bot.on_message(filters.command("start") & filters.private)
async def start_private_handler(client: Client, message: types.Message):
    args = message.command
    if len(args) > 1:
        raw_target = args[1].replace("vc_", "").replace("room_", "")
        chat_id = raw_target if raw_target.startswith("-") else f"-{raw_target}"
        twa_url = f"{WEBAPP_URL}?chat_id={chat_id}"
        return await message.reply_text(
            "🚀 **Voice Space Ready!**\n\nNeeche button par tap karke join karein:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎙 Join Voice Space", web_app=WebAppInfo(url=twa_url))]
            ])
        )

    await message.reply_text(
        f"👋 **Namaste {message.from_user.first_name}!**\n\n"
        "Mujhe kisi bhi group mein add karke Admin banayein aur `/vc` command dein!"
    )

@bot.on_message(filters.command("vc") & filters.group)
async def start_vc_command(client: Client, message: types.Message):
    chat = message.chat
    caller_id = message.from_user.id

    # 1. Admin Verification
    bot_member = await chat.get_member("me")
    if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
        return await message.reply_text("❌ Mujhe group ka Admin banayein taaki Voice Space chal sake.")

    caller_member = await chat.get_member(caller_id)
    is_owner = caller_id in OWNER_IDS
    is_admin = caller_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

    if not is_owner and not is_admin:
        return await message.reply_text("❌ Sirf group admins hi Voice Space start kar sakte hain.")

    # 2. Invite Link
    invite_link = chat.invite_link
    if not invite_link:
        try:
            link_obj = await client.create_chat_invite_link(chat.id, name="Voice Space")
            invite_link = link_obj.invite_link
        except RPCError:
            invite_link = f"https://t.me/{chat.username}" if chat.username else "No link"

    # 3. Admins List
    admin_ids = []
    async for member in chat.get_members(filter=ChatMembersFilter.ADMINISTRATORS):
        admin_ids.append(member.user.id)

    # 4. Save Room in DB
    await set_room(
        chat_id=str(chat.id),
        title=chat.title,
        admins=admin_ids,
        invite_link=invite_link
    )

    # Telegram Native App Link: Direct popup trigger
    clean_chat_id = str(chat.id).replace("-100", "").replace("-", "")
    direct_launch_url = f"https://t.me/{BOT_USERNAME}/{APP_SHORT_NAME}?startapp={clean_chat_id}"

    # ONLY 1 SINGLE BUTTON
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎙 Join Voice Space", url=direct_launch_url)]
    ])

    await message.reply_text(
        f"🎧 **Voice Space Started: {chat.title}**\n\n"
        f"👑 **Admins:** Synced\n"
        f"🔊 **Audio Engine:** LiveKit WebRTC (Lag-Free)\n\n"
        f"Click below to join:",
        reply_markup=markup
    )

@bot.on_message(filters.command("activevc") & filters.user(OWNER_IDS) & filters.private)
async def owner_active_vc_panel(client: Client, message: types.Message):
    active_rooms = await get_all_rooms()
    if not active_rooms:
        return await message.reply_text("📭 Abhi koi bhi Voice Space active nahi hai.")

    text = "🎛 **Active Voice Spaces Panel**\n\n"
    keyboard = []
    for data in active_rooms:
        chat_id = data.get("chat_id")
        group_title = data.get("title", f"Chat {chat_id}")
        clean_id = str(chat_id).replace("-100", "").replace("-", "")
        app_url = f"https://t.me/{BOT_USERNAME}/{APP_SHORT_NAME}?startapp={clean_id}"

        text += f"📌 **Group:** `{group_title}`\n🆔 `{chat_id}`\n───────────────────\n"
        keyboard.append([InlineKeyboardButton(f"🎙 Join VC ({group_title[:12]})", url=app_url)])

    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

if __name__ == "__main__":
    print("Voice Space Pyrogram Bot is Running...")
    bot.run()
    
