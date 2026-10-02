#This code was published by @MightyAyush on github.com/mightyayush
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import logging

class Database:
    def __init__(self, uri: str, db_name: str):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]
        self.users = self.db["users"]
        self.groups = self.db["groups"]
        logging.info("Connected to MongoDB successfully.")

    async def add_user(self, user_id: int, username: str = None):
        await self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {"username": username, "last_seen": datetime.utcnow()},
                "$setOnInsert": {"date_joined": datetime.utcnow()}
            },
            upsert=True
        )

    async def get_all_user_ids(self) -> list[int]:
        cursor = self.users.find({}, {"user_id": 1})
        docs = await cursor.to_list(length=None)
        return [doc["user_id"] for doc in docs if "user_id" in doc]

    async def add_group(self, chat_id: int, title: str = None):
        await self.groups.update_one(
            {"chat_id": chat_id},
            {
                "$set": {"title": title, "last_active": datetime.utcnow()},
                "$setOnInsert": {
                    "punishment_mode": "mute",
                    "approved_users": [],
                    "date_added": datetime.utcnow()
                }
            },
            upsert=True
        )

    async def get_group_config(self, chat_id: int) -> str:
        doc = await self.groups.find_one({"chat_id": chat_id}, {"punishment_mode": 1})
        if doc and "punishment_mode" in doc:
            return doc["punishment_mode"]
        return "mute"

    async def set_group_config(self, chat_id: int, mode: str):
        await self.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {"punishment_mode": mode}},
            upsert=True
        )

    async def get_approved_users(self, chat_id: int) -> list[int]:
        doc = await self.groups.find_one({"chat_id": chat_id}, {"approved_users": 1})
        if doc and "approved_users" in doc:
            return doc["approved_users"]
        return []

    async def approve_user(self, chat_id: int, user_id: int):
        await self.groups.update_one(
            {"chat_id": chat_id},
            {"$addToSet": {"approved_users": user_id}},
            upsert=True
        )

    async def unapprove_user(self, chat_id: int, user_id: int):
        await self.groups.update_one(
            {"chat_id": chat_id},
            {"$pull": {"approved_users": user_id}},
            upsert=True
        )

    async def unapprove_all(self, chat_id: int):
        await self.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {"approved_users": []}},
            upsert=True
        )

    async def get_all_group_ids(self) -> list[int]:
        cursor = self.groups.find({}, {"chat_id": 1})
        docs = await cursor.to_list(length=None)
        return [doc["chat_id"] for doc in docs if "chat_id" in doc]

    async def get_stats(self) -> tuple[int, int]:
        users_count = await self.users.count_documents({})
        groups_count = await self.groups.count_documents({})
        return users_count, groups_count

    async def get_newuser_config(self, chat_id: int) -> dict:
        doc = await self.groups.find_one(
            {"chat_id": chat_id},
            {"newuser_enabled": 1, "newuser_duration": 1}
        )
        return {
            "enabled": bool(doc.get("newuser_enabled", False)) if doc else False,
            "duration": int(doc.get("newuser_duration", 86400)) if doc else 86400,
        }

    async def set_newuser_config(self, chat_id: int, enabled=None, duration=None):
        update = {}
        if enabled is not None:
            update["newuser_enabled"] = bool(enabled)
        if duration is not None:
            update["newuser_duration"] = int(duration)
        if update:
            await self.groups.update_one(
                {"chat_id": chat_id},
                {"$set": update},
                upsert=True
            )

    async def add_newuser_restriction(self, chat_id: int, user_id: int, expires_at):
        await self.db["newuser_restrictions"].update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {
                "$set": {
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "expires_at": expires_at,
                }
            },
            upsert=True
        )

    async def get_active_newuser_restrictions(self, chat_id: int, now=None) -> list[dict]:
        now = now or datetime.utcnow()
        cursor = self.db["newuser_restrictions"].find(
            {"chat_id": chat_id, "expires_at": {"$gt": now}},
            {"user_id": 1, "expires_at": 1}
        )
        return await cursor.to_list(length=None)

    async def remove_newuser_restriction(self, chat_id: int, user_id: int):
        await self.db["newuser_restrictions"].delete_one(
            {"chat_id": chat_id, "user_id": user_id}
        )

    async def cleanup_newuser_restrictions(self):
        await self.db["newuser_restrictions"].delete_many(
            {"expires_at": {"$lte": datetime.utcnow()}}
        )

