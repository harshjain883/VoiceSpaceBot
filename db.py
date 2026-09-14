import os
import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "")
client = AsyncIOMotorClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["VoiceSpaceDB"]
rooms_collection = db["active_rooms"]

async def set_room(chat_id: str, title: str, admins: list, invite_link: str, session_key: str):
    """Sets or updates the room with a brand-new dynamic session_key."""
    await rooms_collection.update_one(
        {"chat_id": str(chat_id)},
        {"$set": {
            "title": title,
            "admins": admins,
            "invite_link": invite_link,
            "active_session": session_key
        }},
        upsert=True
    )

async def get_room(chat_id: str):
    return await rooms_collection.find_one({"chat_id": str(chat_id)})

async def delete_room(chat_id: str):
    await rooms_collection.delete_one({"chat_id": str(chat_id)})

async def get_all_rooms():
    cursor = rooms_collection.find({})
    return await cursor.to_list(length=100)
    
