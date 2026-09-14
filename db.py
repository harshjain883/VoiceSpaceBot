import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
DB_NAME = os.getenv("DB_NAME", "voicespace_db")

client = AsyncIOMotorClient(MONGO_URI)
database = client[DB_NAME]
rooms_collection = database["active_rooms"]

async def set_room(chat_id: str, title: str, admins: list, invite_link: str):
    await rooms_collection.update_one(
        {"chat_id": str(chat_id)},
        {
            "$set": {
                "chat_id": str(chat_id),
                "title": title,
                "admins": admins,
                "invite_link": invite_link
            }
        },
        upsert=True
    )

async def get_room(chat_id: str):
    return await rooms_collection.find_one({"chat_id": str(chat_id)})

async def get_all_rooms():
    cursor = rooms_collection.find({})
    return await cursor.to_list(length=1000)

async def delete_room(chat_id: str):
    await rooms_collection.delete_one({"chat_id": str(chat_id)})
  
