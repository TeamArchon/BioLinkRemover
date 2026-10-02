#This code was published by @MightyAyush on github.com/mightyayush
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatType, ButtonStyle
from pyrogram.errors import FloodWait
import asyncio
import logging
import config
from Client.cache import GROUP_CONFIG_CACHE, APPROVED_USERS_CACHE
from Client.helpers import get_group_config, get_approved_users, is_user_admin
from Client.premium import premium_button, premium_emoji

logger = logging.getLogger("BioLinkRemover.Admin")


# ---------------------------------------------------------------------------
# Self Promo
# ---------------------------------------------------------------------------
# Everything for Self Promo is intentionally kept in this file. No .env
# settings are required. Replace SELF_PROMO_IMAGE_URL with the final public
# image URL when you want the promo to be sent as a photo; leaving it empty
# makes the system send the same promo as a text message.
SELF_PROMO_IMAGE_URL = "https://graph.org/file/7310c1a3a1ff8f3cf1714-d28fb916d188602312.jpg"
SELF_PROMO_TEXT = (
    "<b>🛡️ 𝖡𝗂𝗈 𝖦𝗎𝖺𝗋𝖽𝗂𝖺𝗇 𝖡𝗈𝗍</b>\n\n"
    "Keep your Telegram groups clean from suspicious bios, links and spam "
    "with <b>𝖡𝗂𝗈 𝖦𝗎𝖺𝗋𝖽𝗂𝖺𝗇 𝖡𝗈𝗍</b>.\n\n"
    "Add the bot to your groups and keep your community protected."
)
SELF_PROMO_BUTTON_TEXT = "• Aᴅᴅ Tσ Yσᴜʀ Gʀσᴜᴘ •"
SELF_PROMO_INTERVAL = 24 * 60 * 60
SELF_PROMO_DELETE_AFTER = 48 * 60 * 60
SELF_PROMO_LOCK = asyncio.Lock()
SELF_PROMO_SCHEDULER_TASK = None


def _selfpromo_is_owner(message: Message) -> bool:
    return bool(
        message.from_user
        and (
            message.from_user.id == config.OWNER_ID
            or message.from_user.id in config.SUDO_USERS
        )
    )


async def _selfpromo_button(client: Client):
    try:
        me = await client.get_me()
        return InlineKeyboardMarkup([
            [premium_button(
                SELF_PROMO_BUTTON_TEXT,
                "add",
                ButtonStyle.DANGER,
                url=f"https://t.me/{me.username}?startgroup=true",
            )]
        ])
    except Exception:
        return None


async def _selfpromo_send_one(client: Client, chat_id: int, delete_at):
    keyboard = await _selfpromo_button(client)
    if SELF_PROMO_IMAGE_URL.strip():
        sent = await client.send_photo(
            chat_id,
            SELF_PROMO_IMAGE_URL,
            caption=SELF_PROMO_TEXT,
            reply_markup=keyboard,
        )
    else:
        sent = await client.send_message(
            chat_id,
            SELF_PROMO_TEXT,
            reply_markup=keyboard,
        )

    await client.db.db["selfpromo_messages"].update_one(
        {"chat_id": chat_id, "message_id": sent.id},
        {"$set": {
            "chat_id": chat_id,
            "message_id": sent.id,
            "delete_at": delete_at,
        }},
        upsert=True,
    )


async def _selfpromo_cleanup(client: Client):
    now = __import__("datetime").datetime.utcnow()
    collection = client.db.db["selfpromo_messages"]
    cursor = collection.find(
        {"delete_at": {"$lte": now}},
        {"chat_id": 1, "message_id": 1},
    )
    for item in await cursor.to_list(length=None):
        chat_id = item.get("chat_id")
        message_id = item.get("message_id")
        try:
            await client.delete_messages(chat_id, message_id)
        except Exception:
            pass
        finally:
            await collection.delete_one({"chat_id": chat_id, "message_id": message_id})


async def _selfpromo_run(client: Client, trigger: str = "manual"):
    if SELF_PROMO_LOCK.locked():
        return {"busy": True, "total": 0, "success": 0, "failure": 0}

    async with SELF_PROMO_LOCK:
        from datetime import datetime, timedelta

        run_at = datetime.utcnow()
        delete_at = run_at + timedelta(seconds=SELF_PROMO_DELETE_AFTER)
        user_ids = await client.db.get_all_user_ids()
        group_ids = await client.db.get_all_group_ids()
        targets = list(dict.fromkeys(user_ids + group_ids))
        success = 0
        failure = 0

        for chat_id in targets:
            try:
                await _selfpromo_send_one(client, chat_id, delete_at)
                success += 1
                await asyncio.sleep(0.12)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
                try:
                    await _selfpromo_send_one(client, chat_id, delete_at)
                    success += 1
                except Exception as e:
                    failure += 1
                    logger.warning(f"Self promo retry failed for {chat_id}: {e}")
            except Exception as e:
                failure += 1
                logger.debug(f"Self promo failed for {chat_id}: {e}")

        await client.db.db["selfpromo_settings"].update_one(
            {"_id": "global"},
            {"$set": {"last_run": run_at}},
            upsert=True,
        )

        if config.LOGGER_GROUP:
            try:
                await client.send_message(
                    config.LOGGER_GROUP,
                    "<tg-emoji emoji-id='6271537028307881531'>📢</tg-emoji> "
                    "<b>[SELF PROMO]</b>\n\n"
                    f"<b>Trigger:</b> {trigger}\n"
                    f"<b>Total:</b> {len(targets)}\n"
                    f"<b>Success:</b> {success}\n"
                    f"<b>Failed:</b> {failure}",
                )
            except Exception:
                pass

        return {
            "busy": False,
            "total": len(targets),
            "success": success,
            "failure": failure,
        }


async def _selfpromo_scheduler(client: Client):
    while True:
        try:
            await _selfpromo_cleanup(client)
            settings = await client.db.db["selfpromo_settings"].find_one({"_id": "global"}) or {}
            if settings.get("enabled", False):
                last_run = settings.get("last_run")
                from datetime import datetime
                now = datetime.utcnow()
                if last_run is None or (now - last_run).total_seconds() >= SELF_PROMO_INTERVAL:
                    await _selfpromo_run(client, "automatic")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Self promo scheduler error: {e}")
        await asyncio.sleep(60)


async def _ensure_selfpromo_scheduler(client: Client):
    global SELF_PROMO_SCHEDULER_TASK
    if SELF_PROMO_SCHEDULER_TASK and not SELF_PROMO_SCHEDULER_TASK.done():
        return
    SELF_PROMO_SCHEDULER_TASK = asyncio.create_task(_selfpromo_scheduler(client))
    logger.info("Self promo scheduler started.")


@Client.on_message(filters.all, group=-100)
async def _selfpromo_scheduler_bootstrap(client: Client, message: Message):
    # Starts the persisted 24h scheduler as soon as the bot receives an update.
    await _ensure_selfpromo_scheduler(client)


@Client.on_message(filters.command("selfpromo") & filters.private)
async def selfpromo_cmd(client: Client, message: Message):
    if not _selfpromo_is_owner(message):
        return

    await _ensure_selfpromo_scheduler(client)
    parts = message.text.split(maxsplit=1)
    action = parts[1].strip().lower() if len(parts) > 1 else "status"

    if action == "on":
        await client.db.db["selfpromo_settings"].update_one(
            {"_id": "global"},
            {"$set": {"enabled": True}},
            upsert=True,
        )
        await message.reply_text(
            "<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> "
            "<b>Self Promo Enabled</b>\n\n"
            "Automatic promotion will run every <b>24 hours</b>."
        )
        return

    if action == "off":
        await client.db.db["selfpromo_settings"].update_one(
            {"_id": "global"},
            {"$set": {"enabled": False}},
            upsert=True,
        )
        await message.reply_text(
            "<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> "
            "<b>Self Promo Disabled</b>\n\n"
            "Automatic promotion has been stopped."
        )
        return

    if action == "run":
        status = await message.reply_text(
            "<tg-emoji emoji-id='6271537028307881531'>📢</tg-emoji> "
            "<b>Starting Self Promo...</b>"
        )
        result = await _selfpromo_run(client, "manual")
        if result["busy"]:
            await status.edit_text(
                "<tg-emoji emoji-id='6041720006973067267'>⚠️</tg-emoji> "
                "<b>Another Self Promo broadcast is already running.</b>"
            )
            return
        await status.edit_text(
            "<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> "
            "<b>Self Promo Completed!</b>\n\n"
            f"<b>Total:</b> {result['total']}\n"
            f"<b>Success:</b> {result['success']}\n"
            f"<b>Failed:</b> {result['failure']}\n\n"
            "Promo messages will be removed automatically after <b>48 hours</b>."
        )
        return

    settings = await client.db.db["selfpromo_settings"].find_one({"_id": "global"}) or {}
    enabled = "ON" if settings.get("enabled", False) else "OFF"
    last_run = settings.get("last_run")
    last_text = last_run.strftime("%Y-%m-%d %H:%M UTC") if last_run else "Never"
    await message.reply_text(
        "<tg-emoji emoji-id='6100546468924364734'>📢</tg-emoji> "
        "<b>Self Promo Status</b>\n\n"
        f"<b>Automatic:</b> {enabled}\n"
        "<b>Interval:</b> 24 Hours\n"
        "<b>Delete After:</b> 48 Hours\n"
        f"<b>Last Run:</b> {last_text}\n\n"
        "<code>/selfpromo on</code> — Enable\n"
        "<code>/selfpromo off</code> — Disable\n"
        "<code>/selfpromo run</code> — Run now"
    )

async def get_target_user(client: Client, message: Message) -> tuple[int, str]:
    if message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
        return user.id, user.mention

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        raise Exception("Please reply to a user's message or specify a user ID / username.")

    target = parts[1].strip()

    if target.isdigit() or (target.startswith("-") and target[1:].isdigit()):
        user_id = int(target)
        try:
            user = await client.get_users(user_id)
            return user.id, user.mention
        except Exception:
            return user_id, f"User ID <code>{user_id}</code>"

    username = target.lstrip("@")
    try:
        user = await client.get_users(username)
        return user.id, user.mention
    except Exception as e:
        raise Exception(f"Failed to resolve username @{username}: {e}")

@Client.on_message(filters.command("approve") & filters.group)
async def approve_user_cmd(client: Client, message: Message):
    if not await is_user_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> <b>Access Denied:</b> This command is restricted to group administrators.")
        return

    try:
        user_id, mention = await get_target_user(client, message)
    except Exception as e:
        await message.reply_text(f"<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> <b>Error:</b> {e}")
        return

    await client.db.approve_user(message.chat.id, user_id)
    approved_set = await get_approved_users(client, message.chat.id)
    approved_set.add(user_id)
    await message.reply_text(f"<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> {mention} has been <b>approved</b>. Their bio will not be scanned in this group.")

@Client.on_message(filters.command("unapprove") & filters.group)
async def unapprove_user_cmd(client: Client, message: Message):
    if not await is_user_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> <b>Access Denied:</b> This command is restricted to group administrators.")
        return

    try:
        user_id, mention = await get_target_user(client, message)
    except Exception as e:
        await message.reply_text(f"<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> <b>Error:</b> {e}")
        return

    await client.db.unapprove_user(message.chat.id, user_id)
    approved_set = await get_approved_users(client, message.chat.id)
    approved_set.discard(user_id)
    await message.reply_text(f"<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> {mention} has been <b>unapproved</b>. Their bio will now be scanned.")

@Client.on_message(filters.command("unapproveall") & filters.group)
async def unapprove_all_cmd(client: Client, message: Message):
    if not await is_user_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> <b>Access Denied:</b> This command is restricted to group administrators.")
        return

    await client.db.unapprove_all(message.chat.id)
    APPROVED_USERS_CACHE[message.chat.id] = set()
    await message.reply_text("<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> All approved users have been cleared from this group. Everyone (except admins) will be scanned.")

@Client.on_message(filters.command("approved") & filters.group)
async def list_approved_cmd(client: Client, message: Message):
    approved_set = await get_approved_users(client, message.chat.id)
    if not approved_set:
        await message.reply_text("<tg-emoji emoji-id='5350396951407895212'>ℹ️</tg-emoji> No users are currently whitelisted in this group.")
        return

    status_msg = await message.reply_text("<tg-emoji emoji-id='5409186957676785646'>🔎</tg-emoji> Fetching whitelisted users list...")
    text = "<b><tg-emoji emoji-id='5408843502027033965'>📋</tg-emoji> Whitelisted Users in this group:</b>\n\n"
    for idx, uid in enumerate(approved_set, 1):
        try:
            user = await client.get_users(uid)
            text += f"{idx}. {user.mention} (ID: <code>{uid}</code>)\n"
        except Exception:
            text += f"{idx}. User ID <code>{uid}</code>\n"
    await status_msg.edit_text(text)

@Client.on_message(filters.command("config") & filters.group)
async def config_group_cmd(client: Client, message: Message):
    if not await is_user_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> <b>Access Denied:</b> This command is restricted to group administrators.")
        return

    current_mode = await get_group_config(client, message.chat.id)
    parts = message.text.split()
    if len(parts) > 1:
        new_mode = parts[1].strip().lower()
        if new_mode in ["ban", "mute", "kick"]:
            await client.db.set_group_config(message.chat.id, new_mode)
            GROUP_CONFIG_CACHE[message.chat.id] = new_mode
            await message.reply_text(f"<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> Punishment mode successfully set to: <b>{new_mode.upper()}</b>")
            return
        else:
            await message.reply_text("<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> Invalid mode. Please choose between: `ban`, `mute`, or `kick`.")
            return

    keyboard = InlineKeyboardMarkup([
        [
            premium_button("Ban", "cancel", ButtonStyle.DANGER, callback_data=f"set_cfg:ban:{message.chat.id}"),
            premium_button("Mute", "default", ButtonStyle.PRIMARY, callback_data=f"set_cfg:mute:{message.chat.id}"),
            premium_button("Kick", "cancel", ButtonStyle.DANGER, callback_data=f"set_cfg:kick:{message.chat.id}")
        ]
    ])

    await message.reply_text(
        f"<tg-emoji emoji-id='6100546468924364734'>⚙️</tg-emoji> <b>BioLinkRemover Configuration</b>\n\n"
        f"Group: <b>{message.chat.title}</b>\n"
        f"Current Punishment: <b>{current_mode.upper()}</b>\n\n"
        f"Select a punishment button below to toggle settings for link spam violations:",
        reply_markup=keyboard
    )

@Client.on_callback_query(filters.regex(r"^set_cfg:(ban|mute|kick):(-?\d+)$"))
async def config_callback_handler(client: Client, callback_query: CallbackQuery):
    mode = callback_query.data.split(":")[1]
    chat_id = int(callback_query.data.split(":")[2])
    clicker_id = callback_query.from_user.id

    if not await is_user_admin(client, chat_id, clicker_id):
        await callback_query.answer("You are not authorized to edit this group's configuration.", show_alert=True)
        return

    await client.db.set_group_config(chat_id, mode)
    GROUP_CONFIG_CACHE[chat_id] = mode
    await callback_query.answer(f"Config updated to {mode.upper()}", show_alert=True)

    try:
        chat = await client.get_chat(chat_id)
        chat_title = chat.title
    except Exception:
        chat_title = "Group Settings"

    keyboard = InlineKeyboardMarkup([
        [
            premium_button("Ban", "cancel", ButtonStyle.DANGER, callback_data=f"set_cfg:ban:{chat_id}"),
            premium_button("Mute", "default", ButtonStyle.PRIMARY, callback_data=f"set_cfg:mute:{chat_id}"),
            premium_button("Kick", "cancel", ButtonStyle.DANGER, callback_data=f"set_cfg:kick:{chat_id}")
        ]
    ])

    await callback_query.edit_message_text(
        f"<tg-emoji emoji-id='6100546468924364734'>⚙️</tg-emoji> <b>BioLinkRemover Configuration</b>\n\n"
        f"Group: <b>{chat_title}</b>\n"
        f"Current Punishment: <b>{mode.upper()}</b>\n\n"
        f"<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> Mode updated successfully!",
        reply_markup=keyboard
    )

@Client.on_message(filters.command("stats") & filters.private)
async def stats_owner_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id != config.OWNER_ID and user_id not in config.SUDO_USERS:
        return

    users_count, groups_count = await client.db.get_stats()
    await message.reply_text(
        f"<tg-emoji emoji-id='6100546468924364734'>📊</tg-emoji> <b>Bot Usage Statistics</b>\n\n"
        f"<tg-emoji emoji-id='6021618194228187816'>👤</tg-emoji> <b>Total Registered Users:</b> {users_count}\n"
        f"<tg-emoji emoji-id='5767288287001580715'>👥</tg-emoji> <b>Total Registered Groups:</b> {groups_count}"
    )

@Client.on_message(filters.command("gcast") & filters.private)
async def gcast_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id != config.OWNER_ID and user_id not in config.SUDO_USERS:
        return

    broadcast_msg = message.reply_to_message
    text_only = False
    text_to_send = ""

    if not broadcast_msg:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> Please reply to a message or provide text to broadcast.")
            return
        text_only = True
        text_to_send = parts[1].strip()

    status_msg = await message.reply_text("<tg-emoji emoji-id='6271537028307881531'>📢</tg-emoji> Starting group broadcast...")
    group_ids = await client.db.get_all_group_ids()

    success, failure = 0, 0
    for gid in group_ids:
        try:
            if text_only:
                await client.send_message(gid, text_to_send)
            else:
                await broadcast_msg.copy(gid)
            success += 1
            await asyncio.sleep(0.1)
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
            try:
                if text_only:
                    await client.send_message(gid, text_to_send)
                else:
                    await broadcast_msg.copy(gid)
                success += 1
            except Exception:
                failure += 1
        except Exception:
            failure += 1

    await status_msg.edit_text(
        f"<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> <b>Group Broadcast Completed!</b>\n\n"
        f"<tg-emoji emoji-id='6100546468924364734'>📈</tg-emoji> <b>Success:</b> {success}\n"
        f"<tg-emoji emoji-id='6100546468924364734'>📉</tg-emoji> <b>Failed:</b> {failure}"
    )

@Client.on_message(filters.command("ucast") & filters.private)
async def ucast_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id != config.OWNER_ID and user_id not in config.SUDO_USERS:
        return

    broadcast_msg = message.reply_to_message
    text_only = False
    text_to_send = ""

    if not broadcast_msg:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> Please reply to a message or provide text to broadcast.")
            return
        text_only = True
        text_to_send = parts[1].strip()

    status_msg = await message.reply_text("<tg-emoji emoji-id='6271537028307881531'>📢</tg-emoji> Starting user broadcast...")
    user_ids = await client.db.get_all_user_ids()

    success, failure = 0, 0
    for uid in user_ids:
        try:
            if text_only:
                await client.send_message(uid, text_to_send)
            else:
                await broadcast_msg.copy(uid)
            success += 1
            await asyncio.sleep(0.1)
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
            try:
                if text_only:
                    await client.send_message(uid, text_to_send)
                else:
                    await broadcast_msg.copy(uid)
                success += 1
            except Exception:
                failure += 1
        except Exception:
            failure += 1

    await status_msg.edit_text(
        f"<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> <b>User Broadcast Completed!</b>\n\n"
        f"<tg-emoji emoji-id='6100546468924364734'>📈</tg-emoji> <b>Success:</b> {success}\n"
        f"<tg-emoji emoji-id='6100546468924364734'>📉</tg-emoji> <b>Failed:</b> {failure}"
    )
