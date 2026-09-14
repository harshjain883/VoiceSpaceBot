import os
import time
import secrets
import asyncio
from pyrogram import Client, filters, types
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus, ChatMembersFilter
from pyrogram.errors import RPCError
from dotenv import load_dotenv
from livekit import api

from db import set_room, get_room, delete_room, get_all_rooms

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "Gcvoicechatbot").replace("@", "").strip()
APP_SHORT_NAME = os.getenv("APP_SHORT_NAME", "myapp").strip()

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

BOT_START_TIME = time.time()


# --- 1. PRIVATE /start COMMAND ---
@bot.on_message(filters.command("start") & filters.private)
async def start_private_handler(client: Client, message: types.Message):
    args = message.command

    # Deep-link fallback redirection handler
    if len(args) > 1:
        param = args[1]
        direct_url = f"https://t.me/{BOT_USERNAME}/{APP_SHORT_NAME}?startapp={param}"
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("✧ ᴇɴᴛᴇʀ sᴘᴀᴄᴇ ✧", url=direct_url)]
        ])
        return await message.reply_text(
            "╭───────────────╮\n"
            "   ✦ **ᴠᴏɪᴄᴇ sᴘᴀᴄᴇ ʀᴇᴀᴅʏ** ✦\n"
            "╰───────────────╯\n\n"
            "ᴄʟɪᴄᴋ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴊᴏɪɴ ᴛʜᴇ sᴇssɪᴏɴ:",
            reply_markup=markup
        )

    user_mention = message.from_user.mention
    text = (
        f"╭───────────────╮\n"
        f"   ✦ **ᴠᴏɪᴄᴇ sᴘᴀᴄᴇ ʙᴏᴛ** ✦\n"
        f"╰───────────────╯\n\n"
        f"ɢʀᴇᴇᴛɪɴɢs {user_mention} ✨\n\n"
        "ɪ ᴀᴍ ʏᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ **ᴠᴏɪᴄᴇ sᴘᴀᴄᴇ** ᴍᴀɴᴀɢᴇʀ ᴅᴇsɪɢɴᴇᴅ ғᴏʀ ᴛᴇʟᴇɢʀᴀᴍ ɢʀᴏᴜᴘs.\n\n"
        "╭── ✦ **ᴡʜᴀᴛ ᴅᴏ ɪ ᴏғғᴇʀ?** ──╮\n"
        "├ 🎙️ ᴄʀᴇᴀᴛᴇ ʟɪᴠᴇ ᴠᴏɪᴄᴇ sᴘᴀᴄᴇs ғᴏʀ ʏᴏᴜʀ ɢʀᴏᴜᴘ\n"
        "├ 🎧 ʙᴀᴄᴋɢʀᴏᴜɴᴅ & ʟᴏᴄᴋ-sᴄʀᴇᴇɴ ᴀᴜᴅɪᴏ ᴘʟᴀʏʙᴀᴄᴋ\n"
        "├ 💬 ɪɴ-ʀᴏᴏᴍ ʀᴇᴀʟ-ᴛɪᴍᴇ ᴛᴇxᴛ ᴄʜᴀᴛᴛɪɴɢ\n"
        "├ 👑 ᴀᴅᴍɪɴ ᴍᴏᴅᴇʀᴀᴛɪᴏɴ (ᴍᴜᴛᴇ & ᴋɪᴄᴋ ᴄᴏɴᴛʀᴏʟs)\n"
        "├ 🔐 ᴏɴᴇ-ᴛɪᴍᴇ ᴇɴᴄʀʏᴘᴛᴇᴅ ᴅʏɴᴀᴍɪᴄ ᴊᴏɪɴ ʟɪɴᴋs\n"
        "╰──────────────────────────╯\n\n"
        "ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ᴄᴏᴍᴍᴜɴɪᴛʏ ᴛᴏ ᴇʟᴇᴠᴀᴛᴇ ʏᴏᴜʀ ᴠᴏɪᴄᴇ ᴄᴀʟʟs."
    )

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✧ ᴀᴅᴅ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ ✧", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
        [
            InlineKeyboardButton("📖 ɢᴜɪᴅᴇ", callback_data="cb_help"),
            InlineKeyboardButton("⚡ ᴘɪɴɢ", callback_data="cb_ping")
        ]
    ])

    await message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)


# --- 2. GROUP /vc or /startvc LAUNCHER ---
@bot.on_message(filters.command(["vc", "startvc"]) & filters.group)
async def start_vc_command(client: Client, message: types.Message):
    chat = message.chat
    caller_id = message.from_user.id

    # Admin check for bot
    bot_member = await chat.get_member("me")
    if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
        return await message.reply_text(
            "╭─ ⚠️ **ᴘᴇʀᴍɪssɪᴏɴ ʀᴇǫᴜɪʀᴇᴅ** ─╮\n\n"
            "ᴘʟᴇᴀsᴇ ᴘʀᴏᴍᴏᴛᴇ ᴍᴇ ᴛᴏ **ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀ** ᴛᴏ ʟᴀᴜɴᴄʜ ᴠᴏɪᴄᴇ sᴘᴀᴄᴇs! ✨\n"
            "╰──────────────────────────╯"
        )

    # Admin check for caller
    caller_member = await chat.get_member(caller_id)
    is_owner = caller_id in OWNER_IDS
    is_admin = caller_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

    if not is_owner and not is_admin:
        return await message.reply_text("❌ *ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀs ᴄᴀɴ sᴛᴀʀᴛ ᴀ ᴠᴏɪᴄᴇ sᴘᴀᴄᴇ.*")

    # Fetch/create invite link
    invite_link = chat.invite_link
    if not invite_link:
        try:
            link_obj = await client.create_chat_invite_link(chat.id, name="Voice Space Link")
            invite_link = link_obj.invite_link
        except RPCError:
            invite_link = f"https://t.me/{chat.username}" if chat.username else "No link accessible"

    # Sync Admin IDs
    admin_ids = []
    async for member in chat.get_members(filter=ChatMembersFilter.ADMINISTRATORS):
        admin_ids.append(member.user.id)

    # Cryptographically unique single-session key
    unique_secret = secrets.token_hex(3)
    clean_chat_id = str(chat.id).replace("-100", "").replace("-", "")
    dynamic_session_param = f"{clean_chat_id}x{unique_secret}"

    # Persist Room
    await set_room(
        chat_id=str(chat.id),
        title=chat.title,
        admins=admin_ids,
        invite_link=invite_link,
        session_key=dynamic_session_param
    )

    # Launch URL
    unique_app_link = f"https://t.me/{BOT_USERNAME}/{APP_SHORT_NAME}?startapp={dynamic_session_param}"

    card_text = (
        f"╭───────────────╮\n"
        f"   ✦ **ᴠᴏɪᴄᴇ sᴘᴀᴄᴇ ʟɪᴠᴇ** ✦\n"
        f"╰───────────────╯\n\n"
        f"📍 **ɢʀᴏᴜᴘ:** `{chat.title}`\n"
        f"🎧 **ᴀᴜᴅɪᴏ:** ʜᴅ ᴄʀʏsᴛᴀʟ ᴄʟᴇᴀʀ\n"
        f"💬 **ᴄʜᴀᴛ:** ɪɴ-ʀᴏᴏᴍ ᴛᴇxᴛ ᴀᴄᴛɪᴠᴇ\n"
        f"🔐 **sᴇssɪᴏɴ:** `{unique_secret}` *(sᴇᴄᴜʀᴇ)*\n\n"
        f"✨ *ᴛᴀᴘ ʙᴇʟᴏᴡ ᴛᴏ ᴇɴᴛᴇʀ ᴛʜᴇ sᴘᴀᴄᴇ:* "
    )

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(" ᴊᴏɪɴ ᴠᴏɪᴄᴇ sᴘᴀᴄᴇ", url=unique_app_link)],
        [InlineKeyboardButton("✕ ᴇɴᴅ sᴘᴀᴄᴇ", callback_data="cb_stop_vc")]
    ])

    await message.reply_text(card_text, reply_markup=markup, disable_web_page_preview=True)


# --- 3. /stopvc or /endvc COMMAND ---
@bot.on_message(filters.command(["stopvc", "endvc"]) & filters.group)
async def stop_vc_command(client: Client, message: types.Message):
    chat = message.chat
    caller_id = message.from_user.id

    caller_member = await chat.get_member(caller_id)
    is_owner = caller_id in OWNER_IDS
    is_admin = caller_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

    if not is_owner and not is_admin:
        return await message.reply_text(" *ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀs ᴄᴀɴ ᴇɴᴅ ᴛʜᴇ ᴠᴏɪᴄᴇ sᴘᴀᴄᴇ.*")

    room = await get_room(str(chat.id))
    if not room:
        return await message.reply_text(" *ɴᴏ ᴀᴄᴛɪᴠᴇ ᴠᴏɪᴄᴇ sᴘᴀᴄᴇ ғᴏᴜɴᴅ ɪɴ ᴛʜɪs ɢʀᴏᴜᴘ.*")

    await delete_room(str(chat.id))

    lk_api = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        room_name = f"room_{chat.id}"
        await lk_api.room.delete_room(api.DeleteRoomRequest(room=room_name))
    except Exception:
        pass
    finally:
        await lk_api.aclose()

    await message.reply_text(
        f" **ᴠᴏɪᴄᴇ sᴘᴀᴄᴇ ᴄʟᴏsᴇᴅ: {chat.title}**\n\n"
        "ᴀʟʟ ᴘᴀʀᴛɪᴄɪᴘᴀɴᴛs ʜᴀᴠᴇ ʙᴇᴇɴ ᴅɪsᴄᴏɴɴᴇᴄᴛᴇᴅ. sᴇɴᴅ `/vc` ᴛᴏ sᴛᴀʀᴛ ᴀ ɴᴇᴡ sᴇssɪᴏɴ."
    )


# --- 4. /help COMMAND ---
@bot.on_message(filters.command(["help", "commands"]))
async def help_command(client: Client, message: types.Message):
    help_text = (
        "╭───────────────╮\n"
        "   **ᴜsᴇʀ ɢᴜɪᴅᴇ**    \n"
        "╰───────────────╯\n\n"
        "**ɢʀᴏᴜᴘ ᴄᴏᴍᴍᴀɴᴅs:**\n"
        "• `/vc` - ʟᴀᴜɴᴄʜ ᴀ ɴᴇᴡ ᴠᴏɪᴄᴇ sᴘᴀᴄᴇ\n"
        "• `/stopvc` - ᴄʟᴏsᴇ ᴛʜᴇ ᴀᴄᴛɪᴠᴇ sᴘᴀᴄᴇ\n"
        "• `/ping` - ᴄʜᴇᴄᴋ ʙᴏᴛ ʟᴀᴛᴇɴᴄʏ & sᴛᴀᴛᴜs\n\n"
        "**ᴋᴇʏ ғᴇᴀᴛᴜʀᴇs:**\n"
        "• ʟᴏᴄᴋ-sᴄʀᴇᴇɴ & ʙᴀᴄᴋɢʀᴏᴜɴᴅ ᴀᴜᴅɪᴏ sᴜᴘᴘᴏʀᴛ\n"
        "• ʀᴇᴀʟ-ᴛɪᴍᴇ ɪɴ-ʀᴏᴏᴍ ᴛᴇxᴛ ᴍᴇssᴀɢɪɴɢ\n"
        "• ʟɪᴠᴇ ᴍᴜᴛᴇ / ᴜɴᴍᴜᴛᴇ sᴛᴀᴛᴜs ɪɴᴅɪᴄᴀᴛᴏʀs\n"
        "• ᴀᴜᴛᴏ-ᴇxᴘɪʀɪɴɢ sᴇᴄᴜʀᴇ ᴊᴏɪɴ ʟɪɴᴋs"
    )
    await message.reply_text(help_text)


# --- 5. /ping COMMAND ---
@bot.on_message(filters.command("ping"))
async def ping_command(client: Client, message: types.Message):
    start = time.time()
    msg = await message.reply_text("⚡ *ᴄʜᴇᴄᴋɪɴɢ...*")
    latency = round((time.time() - start) * 1000, 2)
    uptime_sec = int(time.time() - BOT_START_TIME)
    uptime_min = round(uptime_sec / 60, 1)

    await msg.edit_text(
        f"╭─ ⚡ **sʏsᴛᴇᴍ sᴛᴀᴛᴜs** ─╮\n"
        f"├ 🚀 **ʟᴀᴛᴇɴᴄʏ:** `{latency} ms`\n"
        f"├ ⏱️ **ᴜᴘᴛɪᴍᴇ:** `{uptime_min} mins`\n"
        f"├ 🟢 **sᴛᴀᴛᴜs:** `ᴏᴘᴇʀᴀᴛɪᴏɴᴀʟ`\n"
        f"╰────────────────────╯"
    )


# --- 6. CALLBACK BUTTON LISTENERS ---
@bot.on_callback_query()
async def callback_listener(client: Client, query: types.CallbackQuery):
    data = query.data

    if data == "cb_ping":
        latency = round((time.time() - query.message.date.timestamp()) * 10, 2)
        await query.answer(f" ʟᴀᴛᴇɴᴄʏ: {latency}ms | ᴀʟʟ sʏsᴛᴇᴍs ᴏᴘᴇʀᴀᴛɪᴏɴᴀʟ!", show_alert=True)

    elif data == "cb_help":
        await query.answer()
        await query.message.edit_text(
            "╭─ 📖 **ᴄᴏᴍᴍᴀɴᴅs ᴍᴇɴᴜ** ─╮\n\n"
            "• `/vc` - sᴛᴀʀᴛ ᴀ ɢʀᴏᴜᴘ ᴠᴏɪᴄᴇ sᴘᴀᴄᴇ\n"
            "• `/stopvc` - ᴄʟᴏsᴇ ᴀᴄᴛɪᴠᴇ sᴘᴀᴄᴇ\n"
            "• `/ping` - ᴄʜᴇᴄᴋ ʙᴏᴛ ʀᴇsᴘᴏɴsᴇ ᴛɪᴍᴇ\n\n"
            "ᴘʀᴏᴍᴏᴛᴇ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴀᴅᴍɪɴ ᴛᴏ ɢᴇᴛ sᴛᴀʀᴛᴇᴅ! ✨",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data="cb_back_start")]
            ])
        )

    elif data == "cb_back_start":
        await query.answer()
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("✧ ᴀᴅᴅ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ ✧", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
            [
                InlineKeyboardButton("ɢᴜɪᴅᴇ", callback_data="cb_help"),
                InlineKeyboardButton("ᴘɪɴɢ", callback_data="cb_ping")
            ]
        ])
        await query.message.edit_text(
            f"ɢʀᴇᴇᴛɪɴɢs {query.from_user.mention}! ✨\n\n"
            "ɪ ᴀᴍ ʏᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ ᴠᴏɪᴄᴇ sᴘᴀᴄᴇ ᴍᴀɴᴀɢᴇʀ.",
            reply_markup=markup
        )

    elif data == "cb_stop_vc":
        chat = query.message.chat
        user_id = query.from_user.id
        caller_member = await chat.get_member(user_id)
        is_admin = caller_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

        if not is_admin and user_id not in OWNER_IDS:
            return await query.answer("ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀs ᴄᴀɴ ᴇɴᴅ ᴛʜɪs sᴘᴀᴄᴇ.", show_alert=True)

        await delete_room(str(chat.id))
        await query.answer("ᴠᴏɪᴄᴇ sᴘᴀᴄᴇ ᴇɴᴅᴇᴅ!", show_alert=False)
        await query.message.edit_text(
            f"**ᴠᴏɪᴄᴇ sᴘᴀᴄᴇ ᴄʟᴏsᴇᴅ: {chat.title}**\n\nsᴇssɪᴏɴ ᴇɴᴅᴇᴅ ʙʏ {query.from_user.mention}."
        )


if __name__ == "__main__":
    print("Voice Space Bot is Running...")
    bot.run()
    
