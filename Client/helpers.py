#This code was published by @MightyAyush on github.com/mightyayush
from pyrogram import Client
from pyrogram.enums import ChatMembersFilter
import config
import logging
import time
from Client.cache import GROUP_CONFIG_CACHE, APPROVED_USERS_CACHE, GROUP_ADMINS_CACHE

logger = logging.getLogger("BioLinkRemover.Helpers")

async def get_group_config(client: Client, chat_id: int) -> str:
    if chat_id not in GROUP_CONFIG_CACHE:
        try:
            mode = await client.db.get_group_config(chat_id)
            GROUP_CONFIG_CACHE[chat_id] = mode
        except Exception as e:
            logger.error(f"Error fetching group config for {chat_id}: {e}")
            return "mute"
    return GROUP_CONFIG_CACHE[chat_id]

async def get_approved_users(client: Client, chat_id: int) -> set[int]:
    if chat_id not in APPROVED_USERS_CACHE:
        try:
            users = await client.db.get_approved_users(chat_id)
            APPROVED_USERS_CACHE[chat_id] = set(users)
        except Exception as e:
            logger.error(f"Error fetching approved users for {chat_id}: {e}")
            return set()
    return APPROVED_USERS_CACHE[chat_id]

async def is_user_admin(client: Client, chat_id: int, user_id: int) -> bool:
    if user_id == config.OWNER_ID or user_id in config.SUDO_USERS:
        return True

    now = time.time()
    if chat_id in GROUP_ADMINS_CACHE:
        admin_ids, timestamp = GROUP_ADMINS_CACHE[chat_id]
        if now - timestamp < 300:
            return user_id in admin_ids

    try:
        admins = []
        async for member in client.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
            if member.user:
                admins.append(member.user.id)
        GROUP_ADMINS_CACHE[chat_id] = (set(admins), now)
        return user_id in admins
    except Exception as e:
        logger.warning(f"Error fetching chat admins for {chat_id}: {e}")
        return False
