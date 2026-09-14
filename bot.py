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
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
WEBAPP_URL = os.getenv("WEBAPP_URL").rstrip("/")

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

# FIXED: filters.group handles both normal groups and supergroups in Pyrogram
@bot.on_message(filters.command("vc") & filters.group)
async def start_vc_command(client: Client, message: types.Message):
    chat = message.chat
    caller_id = message.from_user.id

    # 1. Verify Bot's Admin Rights and "can_invite_users" Privilege
    bot_member = await chat.get_member("me")
    if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
        return await message.reply_text(
            "❌ **Bot is not an Admin!**\n\n"
            "Please promote me to **Administrator** with **Invite Users via Link** permission enabled."
        )

    privileges = bot_member.privileges
    if not (privileges and privileges.can_invite_users):
        return await message.reply_text(
            "⚠️ **Permission Missing!**\n\n"
            "Bot ko kaam karne ke liye **Invite Users via Link** permission chahiye.\n"
            "Admin Settings mein jaakar yeh permission enable karein!"
        )

    # 2. Verify Caller is Admin or Owner
    caller_member = await chat.get_member(caller_id)
    is_owner = caller_id in OWNER_IDS
    is_admin = caller_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

    if not is_owner and not is_admin:
        return await message.reply_text("❌ Sirf group administrators hi Voice Space start kar sakte hain.")

    # 3. Retrieve or Create Group Invite Link
    invite_link = chat.invite_link
    if not invite_link:
        try:
            link_obj = await client.create_chat_invite_link(chat.id, name="Voice Space Link")
            invite_link = link_obj.invite_link
        except RPCError:
            invite_link = f"https://t.me/{chat.username}" if chat.username else "No link accessible"

    # 4. Extract Admins
    admin_ids = []
    async for member in chat.get_members(filter=ChatMembersFilter.ADMINISTRATORS):
        admin_ids.append(member.user.id)

    # 5. Persist to MongoDB
    await set_room(
        chat_id=str(chat.id),
        title=chat.title,
        admins=admin_ids,
        invite_link=invite_link
    )

    twa_url = f"{WEBAPP_URL}?chat_id={chat.id}"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎙 Join Voice Space", web_app=WebAppInfo(url=twa_url))]
    ])

    await message.reply_text(
        f"🎧 **Voice Space Started for {chat.title}**\n\n"
        f"🛡 **Invite Permission:** Verified ✅\n"
        f"👑 **Admins:** Synced with Database\n"
        f"🔊 **Quality:** HD Opus Audio (Lag-Free)\n\n"
        f"Click below to join the voice space:",
        reply_markup=markup
    )

@bot.on_message(filters.command("activevc") & filters.user(OWNER_IDS) & filters.private)
async def owner_active_vc_panel(client: Client, message: types.Message):
    active_rooms = await get_all_rooms()
    if not active_rooms:
        return await message.reply_text("📭 Kisi bhi group mein abhi koi Voice Space active nahi hai.")

    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        text = "🎛 **Owner Super-Panel - Active Voice Spaces**\n\n"
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
            tg_invite = data.get("invite_link", "Unavailable")
            twa_url = f"{WEBAPP_URL}?chat_id={chat_id}"

            text += f"📌 **Group:** `{group_title}`\n"
            text += f"🆔 **Chat ID:** `{chat_id}`\n"
            text += f"👥 **Online Members:** `{member_count}`\n"
            text += f"🔗 **Group Invite Link:** {tg_invite}\n"
            text += f"🚀 **Mini App Link:** `{twa_url}`\n"
            text += "────────────────────────\n"

            keyboard.append([
                InlineKeyboardButton(f"🎙 Join VC ({group_title[:12]})", web_app=WebAppInfo(url=twa_url)),
                InlineKeyboardButton("🔗 Group Link", url=tg_invite if tg_invite.startswith("http") else "https://t.me")
            ])

        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )
    finally:
        await lk_api.aclose()

# bot.py ke last lines ko replace karein:
if __name__ == "__main__":
    print("---------------------------------------")
    print(">>> Voice Space Pyrogram Bot Started! <<<")
    print("---------------------------------------")
    bot.run()
