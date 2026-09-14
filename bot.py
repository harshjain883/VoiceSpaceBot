import os
import asyncio
from pyrogram import Client, filters, types
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from pyrogram.enums import ChatMemberStatus
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL").rstrip("/")

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

    # 1. Verify caller is an Admin
    caller_member = await chat.get_member(caller_id)
    if caller_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        return await message.reply_text("❌ Only group administrators can start the voice space.")

    # 2. Get all administrators in this group
    admin_ids = []
    async for member in chat.get_members(filter=pyrogram.enums.ChatMembersFilter.ADMINISTRATORS):
        admin_ids.append(member.user.id)

    ACTIVE_ROOMS[str(chat.id)] = admin_ids

    # 3. Direct URL pointing to our Mini App with chat context
    twa_url = f"{WEBAPP_URL}?chat_id={chat.id}"

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🎙 Join Voice Space",
                web_app=WebAppInfo(url=twa_url)
            )
        ]
    ])

    await message.reply_text(
        f"🎧 **Voice Space Started for {chat.title}**\n\n"
        f"👑 **Admins:** Auto-synced from group\n"
        f"🔊 **Quality:** HD Opus Audio (Lag-Free)\n\n"
        f"Click below to join the voice space:",
        reply_markup=markup
    )

if __name__ == "__main__":
    bot.run()
  
