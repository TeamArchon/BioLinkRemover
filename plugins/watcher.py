#This code was published by @MightyAyush on github.com/mightyayush
from pyrogram import Client, filters
from pyrogram.types import Message, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, UserAdminInvalid, ChatAdminRequired
from pyrogram.enums import ButtonStyle
from pyrogram.raw.functions.users import GetFullUser
import re
import logging
import asyncio
import config
from Client.cache import USER_IDS_CACHE, GROUP_IDS_CACHE
from Client.helpers import get_group_config, get_approved_users, is_user_admin
from Client.premium import premium_button, premium_emoji

logger = logging.getLogger("BioLinkRemover.Watcher")

URL_REGEX = re.compile(
    r'(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}/[^\s]*|[a-zA-Z0-9.-]+\.(?:com|org|net|xyz|info|biz|me|co|cc|top|click|online|shop|site|website|club|icu|vip|work|fun|live|tech|app|link|dev|py|sh|us|in|uk|ru|br|tr|de|fr|it|es|ca|au|su|tk|ga|cf|gq|ml|t\.me)(?:/[^\s]*)?)',
    re.IGNORECASE
)

async def check_bio_spam(client: Client, user_id: int) -> tuple[bool, str | None]:
    try:
        peer = await client.resolve_peer(user_id)
        full_user = await client.invoke(GetFullUser(id=peer))
        bio = full_user.full_user.about

        if not bio:
            return False, None

        bio_lower = bio.lower()

        for word in config.DIRTY_WORDS:
            if word.lower() in bio_lower:
                return True, f"contains blacklisted word '{word}'"

        for site in config.DIRTY_SITES:
            if site.lower() in bio_lower:
                return True, f"contains blacklisted site link '{site}'"

        if URL_REGEX.search(bio):
            return True, "contains a link or URL"

        return False, None
    except Exception as e:
        logger.debug(f"Failed to fetch bio for user {user_id}: {e}")
        return False, None

@Client.on_message(filters.group & ~filters.service)
async def scan_group_message(client: Client, message: Message):
    chat_id = message.chat.id

    if chat_id not in GROUP_IDS_CACHE:
        try:
            await client.db.add_group(chat_id, message.chat.title)
            GROUP_IDS_CACHE.add(chat_id)
            logger.info(f"Silently registered new group: {message.chat.title} ({chat_id})")
        except Exception as e:
            logger.error(f"Error registering group in DB: {e}")

    if not message.from_user:
        return

    user_id = message.from_user.id

    if user_id not in USER_IDS_CACHE:
        try:
            await client.db.add_user(user_id, message.from_user.username)
            USER_IDS_CACHE.add(user_id)
            logger.info(f"Silently registered new user: {message.from_user.first_name} ({user_id})")
        except Exception as e:
            logger.error(f"Error registering user in DB: {e}")

    if await is_user_admin(client, chat_id, user_id):
        return

    approved_users = await get_approved_users(client, chat_id)
    if user_id in approved_users:
        return

    is_spam, reason = await check_bio_spam(client, user_id)
    if not is_spam:
        return

    punishment = await get_group_config(client, chat_id)

    try:
        try:
            await message.delete()
        except Exception as de:
            logger.warning(f"Could not delete message in chat {chat_id}: {de}")

        action_text = ""

        if punishment == "ban":
            await client.ban_chat_member(chat_id, user_id)
            action_text = "banned"
        elif punishment == "kick":
            await client.ban_chat_member(chat_id, user_id)
            await client.unban_chat_member(chat_id, user_id)
            action_text = "kicked"
        else:
            await client.restrict_chat_member(chat_id, user_id, ChatPermissions())
            action_text = "muted"

        reply_markup = None
        if punishment == "mute":
            reply_markup = InlineKeyboardMarkup([
                [premium_button("Refresh (Check Bio Again)", "replay", ButtonStyle.PRIMARY, callback_data=f"refresh_mute:{user_id}")]
            ])
        elif punishment == "ban":
            reply_markup = InlineKeyboardMarkup([
                [premium_button("Unban User", "confirm", ButtonStyle.SUCCESS, callback_data=f"unban_user:{user_id}:{chat_id}")]
            ])

        moderation_msg = (
            f"<tg-emoji emoji-id='5275969776668134187'>🛡️</tg-emoji> <b>BioLinkRemover Moderation</b>\n\n"
            f"<tg-emoji emoji-id='6021618194228187816'>👤</tg-emoji> <b>User:</b> {message.from_user.mention} (<code>{user_id}</code>)\n"
            f"<tg-emoji emoji-id='6100546468924364734'>🛠️</tg-emoji> <b>Action:</b> {action_text.upper()}\n"
            f"<tg-emoji emoji-id='5355051922862653659'>📝</tg-emoji> <b>Reason:</b> User bio {reason}."
        )
        await client.send_message(chat_id, moderation_msg, reply_markup=reply_markup)

        if config.LOGGER_GROUP:
            log_msg = (
                f"<tg-emoji emoji-id='6271537028307881531'>⚡</tg-emoji> <b>[MODERATION ACTION]</b>\n\n"
                f"<tg-emoji emoji-id='5767288287001580715'>👥</tg-emoji> <b>Group:</b> {message.chat.title} (<code>{chat_id}</code>)\n"
                f"<tg-emoji emoji-id='6021618194228187816'>👤</tg-emoji> <b>User:</b> {message.from_user.mention} (<code>{user_id}</code>)\n"
                f"<tg-emoji emoji-id='6100546468924364734'>🛠️</tg-emoji> <b>Action Applied:</b> {action_text.upper()}\n"
                f"<tg-emoji emoji-id='5355051922862653659'>📝</tg-emoji> <b>Detection Reason:</b> Bio {reason}"
            )
            await client.send_message(config.LOGGER_GROUP, log_msg)

    except FloodWait as fw:
        logger.warning(f"FloodWait encountered for {fw.value}s. Sleeping...")
        await asyncio.sleep(fw.value)
    except UserAdminInvalid:
        logger.warning(f"Failed to punish {user_id} in {chat_id}: User is an admin or has higher privileges.")
    except ChatAdminRequired:
        err_msg = f"Bot is missing admin permissions in group {message.chat.title} ({chat_id}) to take action."
        logger.error(err_msg)
        if config.LOGGER_GROUP:
            await client.send_message(config.LOGGER_GROUP, f"<tg-emoji emoji-id='6041720006973067267'>⚠️</tg-emoji> <b>[WARNING]</b> {err_msg}")
    except Exception as e:
        err_msg = f"Unexpected error moderating user {user_id} in group {chat_id}: {e}"
        logger.error(err_msg)
        if config.LOGGER_GROUP:
            await client.send_message(config.LOGGER_GROUP, f"<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> <b>[ERROR]</b> {err_msg}")

@Client.on_callback_query(filters.regex(r"^refresh_mute:(\d+)$"))
async def refresh_mute_callback(client: Client, callback_query: CallbackQuery):
    target_user_id = int(callback_query.data.split(":")[1])
    clicker_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id

    is_admin = await is_user_admin(client, chat_id, clicker_id)
    if clicker_id != target_user_id and not is_admin:
        await callback_query.answer("Only the muted user themselves can trigger a rescan.", show_alert=True)
        return

    is_spam, reason = await check_bio_spam(client, target_user_id)
    if is_spam:
        await callback_query.answer(f"Rescan failed! Your bio still {reason}.", show_alert=True)
        return

    try:
        await client.unban_chat_member(chat_id, target_user_id)

        try:
            target_user = await client.get_users(target_user_id)
            mention = target_user.mention
        except Exception:
            mention = f"User <code>{target_user_id}</code>"

        await callback_query.answer("Success! Your bio is clean, and you have been unmuted.", show_alert=True)

        await callback_query.edit_message_text(
            f"<tg-emoji emoji-id='5275969776668134187'>🛡️</tg-emoji> <b>BioLinkRemover Moderation</b>\n\n"
            f"<tg-emoji emoji-id='6021618194228187816'>👤</tg-emoji> <b>User:</b> {mention} (<code>{target_user_id}</code>)\n"
            f"<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> <b>Status:</b> Bio rescan passed. User has been <b>UNMUTED</b>."
        )

        if config.LOGGER_GROUP:
            log_msg = (
                f"<tg-emoji emoji-id='6023773095284707791'>🔄</tg-emoji> <b>[UNMUTED AFTER RESCAN]</b>\n\n"
                f"<tg-emoji emoji-id='5767288287001580715'>👥</tg-emoji> <b>Group:</b> {callback_query.message.chat.title} (<code>{chat_id}</code>)\n"
                f"<tg-emoji emoji-id='6021618194228187816'>👤</tg-emoji> <b>User:</b> {mention} (<code>{target_user_id}</code>)\n"
                f"<tg-emoji emoji-id='5350396951407895212'>💡</tg-emoji> <b>Action:</b> UNMUTED (Bio cleaned up by user)"
            )
            await client.send_message(config.LOGGER_GROUP, log_msg)

    except Exception as e:
        logger.error(f"Failed to unmute user {target_user_id} after rescan: {e}")
        await callback_query.answer(f"Failed to unmute: {e}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^unban_user:(\d+):(-?\d+)$"))
async def unban_user_callback(client: Client, callback_query: CallbackQuery):
    target_user_id = int(callback_query.data.split(":")[1])
    chat_id = int(callback_query.data.split(":")[2])
    clicker_id = callback_query.from_user.id

    if not await is_user_admin(client, chat_id, clicker_id):
        await callback_query.answer("Only group administrators can lift bans.", show_alert=True)
        return

    try:
        await client.unban_chat_member(chat_id, target_user_id)

        try:
            target_user = await client.get_users(target_user_id)
            target_mention = target_user.mention
        except Exception:
            target_mention = f"User <code>{target_user_id}</code>"

        clicker_mention = callback_query.from_user.mention

        await callback_query.answer("User unbanned successfully.", show_alert=True)

        await callback_query.edit_message_text(
            f"<tg-emoji emoji-id='5275969776668134187'>🛡️</tg-emoji> <b>BioLinkRemover Moderation</b>\n\n"
            f"<tg-emoji emoji-id='6021618194228187816'>👤</tg-emoji> <b>User:</b> {target_mention} (<code>{target_user_id}</code>)\n"
            f"<tg-emoji emoji-id='5463122435425448565'>🔓</tg-emoji> <b>Status:</b> User has been <b>UNBANNED</b> by admin {clicker_mention}."
        )

        if config.LOGGER_GROUP:
            log_msg = (
                f"<tg-emoji emoji-id='5463122435425448565'>🔓</tg-emoji> <b>[UNBANNED BY ADMIN]</b>\n\n"
                f"<tg-emoji emoji-id='5767288287001580715'>👥</tg-emoji> <b>Group:</b> {callback_query.message.chat.title} (<code>{chat_id}</code>)\n"
                f"<tg-emoji emoji-id='6021618194228187816'>👤</tg-emoji> <b>User:</b> {target_mention} (<code>{target_user_id}</code>)\n"
                f"<tg-emoji emoji-id='5767288287001580715'>👮</tg-emoji> <b>Admin:</b> {clicker_mention} (<code>{clicker_id}</code>)\n"
                f"<tg-emoji emoji-id='5350396951407895212'>💡</tg-emoji> <b>Action:</b> UNBANNED"
            )
            await client.send_message(config.LOGGER_GROUP, log_msg)

    except Exception as e:
        logger.error(f"Failed to unban user {target_user_id} via callback: {e}")
        await callback_query.answer(f"Failed to unban: {e}", show_alert=True)
