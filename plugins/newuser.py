from datetime import datetime, timedelta, timezone
import asyncio
import logging
import re
import time

from pyrogram import Client, filters
from pyrogram.enums import ButtonStyle
from pyrogram.errors import ChatAdminRequired, FloodWait, UserAdminInvalid
from pyrogram.types import CallbackQuery, ChatPermissions, InlineKeyboardMarkup, Message

from Client.cache import NEWUSER_CONFIG_CACHE
from Client.helpers import is_user_admin
from Client.premium import premium_button, premium_emoji

logger = logging.getLogger("BioGuard.NewUser")

DEFAULT_DURATION = 24 * 60 * 60
PRESET_DURATIONS = [
    30 * 60,
    60 * 60,
    2 * 60 * 60,
    6 * 60 * 60,
    12 * 60 * 60,
    24 * 60 * 60,
    48 * 60 * 60,
    72 * 60 * 60,
]
MAX_DURATION = 365 * 24 * 60 * 60
CUSTOM_PENDING = {}
CUSTOM_TIMEOUT = 120


def format_duration(seconds: int) -> str:
    seconds = int(seconds)
    if seconds % 86400 == 0:
        days = seconds // 86400
        return f"{days} Day{'s' if days != 1 else ''}"
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"{hours} Hour{'s' if hours != 1 else ''}"
    minutes = seconds // 60
    if minutes:
        return f"{minutes} Minute{'s' if minutes != 1 else ''}"
    return f"{seconds} Second{'s' if seconds != 1 else ''}"


def parse_duration(value: str) -> int | None:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([mhd])\s*", value.lower())
    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2)
    multiplier = {"m": 60, "h": 3600, "d": 86400}[unit]
    seconds = int(amount * multiplier)

    if seconds < 30 * 60 or seconds > MAX_DURATION:
        return None
    return seconds


def duration_buttons(current: int, chat_id: int) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(PRESET_DURATIONS), 2):
        row = []
        for duration in PRESET_DURATIONS[i:i + 2]:
            icon = "confirm" if duration == current else "default"
            label = f"{'✓ ' if duration == current else ''}{format_duration(duration)}"
            row.append(
                premium_button(
                    label,
                    icon,
                    ButtonStyle.SUCCESS if duration == current else ButtonStyle.PRIMARY,
                    callback_data=f"newuser_time:{chat_id}:{duration}"
                )
            )
        rows.append(row)

    rows.append([
        premium_button(
            "Custom Time",
            "stats",
            ButtonStyle.DANGER,
            callback_data=f"newuser_custom:{chat_id}"
        )
    ])
    rows.append([
        premium_button(
            "Back",
            "back",
            ButtonStyle.PRIMARY,
            callback_data=f"newuser_panel:{chat_id}"
        )
    ])
    return InlineKeyboardMarkup(rows)


def panel_keyboard(chat_id: int, enabled: bool, duration: int) -> InlineKeyboardMarkup:
    rows = [
        [
            premium_button(
                "Enable",
                "confirm",
                ButtonStyle.SUCCESS,
                callback_data=f"newuser_toggle:{chat_id}:on"
            ),
            premium_button(
                "Disable",
                "cancel",
                ButtonStyle.DANGER,
                callback_data=f"newuser_toggle:{chat_id}:off"
            ),
        ],
        [
            premium_button(
                f"Timer: {format_duration(duration)}",
                "queue",
                ButtonStyle.PRIMARY,
                callback_data=f"newuser_times:{chat_id}"
            )
        ],
        [
            premium_button(
                "Decrease",
                "back",
                ButtonStyle.PRIMARY,
                callback_data=f"newuser_step:{chat_id}:down"
            ),
            premium_button(
                "Increase",
                "skip",
                ButtonStyle.PRIMARY,
                callback_data=f"newuser_step:{chat_id}:up"
            ),
        ],
        [
            premium_button(
                "Custom Time",
                "stats",
                ButtonStyle.DANGER,
                callback_data=f"newuser_custom:{chat_id}"
            )
        ],
        [
            premium_button(
                "Status",
                "auth",
                ButtonStyle.PRIMARY,
                callback_data=f"newuser_status:{chat_id}"
            )
        ],
    ]
    return InlineKeyboardMarkup(rows)


async def get_config(client: Client, chat_id: int) -> tuple[bool, int]:
    if chat_id not in NEWUSER_CONFIG_CACHE:
        data = await client.db.get_newuser_config(chat_id)
        NEWUSER_CONFIG_CACHE[chat_id] = data
    data = NEWUSER_CONFIG_CACHE[chat_id]
    return bool(data["enabled"]), int(data["duration"])


async def save_config(client: Client, chat_id: int, enabled=None, duration=None):
    current_enabled, current_duration = await get_config(client, chat_id)
    enabled = current_enabled if enabled is None else bool(enabled)
    duration = current_duration if duration is None else int(duration)

    await client.db.set_newuser_config(
        chat_id,
        enabled=enabled,
        duration=duration,
    )
    NEWUSER_CONFIG_CACHE[chat_id] = {
        "enabled": enabled,
        "duration": duration,
    }
    return enabled, duration


def text_only_permissions() -> ChatPermissions:
    # Telegram exposes granular media permissions. Keeping can_send_messages=True
    # allows normal text while all media/other-message permissions stay disabled.
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
    )


async def default_permissions(client: Client, chat_id: int) -> ChatPermissions:
    chat = await client.get_chat(chat_id)
    permissions = getattr(chat, "permissions", None)
    if permissions is not None:
        return permissions

    try:
        return ChatPermissions.all_permissions()
    except AttributeError:
        return ChatPermissions(
            can_send_messages=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
        )


async def is_admin_or_owner(client: Client, chat_id: int, user_id: int) -> bool:
    return await is_user_admin(client, chat_id, user_id)


async def render_panel(client: Client, target, chat_id: int):
    enabled, duration = await get_config(client, chat_id)
    active = await client.db.get_active_newuser_restrictions(chat_id)

    status = (
        f"{premium_emoji('confirm', '🟢')} <b>Enabled</b>"
        if enabled
        else f"{premium_emoji('cancel', '🔴')} <b>Disabled</b>"
    )

    text = (
        f"{premium_emoji('auth', '🛡️')} <b>New User Protection</b>\n\n"
        f"Restricts newly joined members to <b>text-only</b> messages for a selected duration.\n\n"
        f"{premium_emoji('confirm', '🟢')} <b>Status:</b> {status}\n"
        f"{premium_emoji('queue', '⏱️')} <b>Duration:</b> {format_duration(duration)}\n"
        f"{premium_emoji('help', '💬')} <b>Mode:</b> Text Only\n"
        f"{premium_emoji('admins', '👥')} <b>Active Users:</b> {len(active)}\n\n"
        f"<i>Photos, videos, stickers, GIFs, audio, voice notes, documents and polls "
        f"are blocked during the restriction.</i>"
    )

    keyboard = panel_keyboard(chat_id, enabled, duration)
    if isinstance(target, CallbackQuery):
        await target.edit_message_text(text=text, reply_markup=keyboard)
    else:
        await target.reply_text(text=text, reply_markup=keyboard)


async def lift_active_restrictions(client: Client, chat_id: int):
    active = await client.db.get_active_newuser_restrictions(chat_id)
    if not active:
        return 0

    permissions = await default_permissions(client, chat_id)
    restored = 0

    for item in active:
        user_id = item["user_id"]
        try:
            await client.restrict_chat_member(
                chat_id,
                user_id,
                permissions=permissions,
            )
            restored += 1
        except Exception as exc:
            logger.warning("Could not restore %s in %s: %s", user_id, chat_id, exc)
        finally:
            await client.db.remove_newuser_restriction(chat_id, user_id)

    return restored


@Client.on_message(filters.command("newuser") & filters.group, group=-10)
async def newuser_command(client: Client, message: Message):
    if not message.from_user or not await is_admin_or_owner(
        client, message.chat.id, message.from_user.id
    ):
        await message.reply_text(
            f"{premium_emoji('cancel', '❌')} <b>Access Denied:</b> "
            f"Only group administrators can manage New User Protection."
        )
        return

    await render_panel(client, message, message.chat.id)


@Client.on_callback_query(filters.regex(r"^newuser_(panel|times|status|custom|toggle|time|step):"), group=-10)
async def newuser_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data.split(":")
    action = data[0]
    chat_id = int(data[1])

    if callback_query.message is None:
        await callback_query.answer()
        return

    if callback_query.message.chat.id != chat_id:
        await callback_query.answer("This control belongs to another group.", show_alert=True)
        return

    if not await is_admin_or_owner(client, chat_id, callback_query.from_user.id):
        await callback_query.answer(
            "Only group administrators can change this setting.",
            show_alert=True,
        )
        return

    if action == "newuser_panel":
        await callback_query.answer()
        await render_panel(client, callback_query, chat_id)
        return

    if action == "newuser_times":
        _, _, _ = data
        _, duration = await get_config(client, chat_id)
        await callback_query.answer()
        await callback_query.edit_message_text(
            f"{premium_emoji('queue', '⏱️')} <b>Select Restriction Duration</b>\n\n"
            f"Current duration: <b>{format_duration(duration)}</b>",
            reply_markup=duration_buttons(duration, chat_id),
        )
        return

    if action == "newuser_status":
        enabled, duration = await get_config(client, chat_id)
        active = await client.db.get_active_newuser_restrictions(chat_id)
        await callback_query.answer()
        await callback_query.edit_message_text(
            f"{premium_emoji('auth', '🛡️')} <b>New User Protection Status</b>\n\n"
            f"{premium_emoji('confirm', '🟢')} <b>Status:</b> {'Enabled' if enabled else 'Disabled'}\n"
            f"{premium_emoji('queue', '⏱️')} <b>Duration:</b> {format_duration(duration)}\n"
            f"{premium_emoji('help', '💬')} <b>Mode:</b> Text Only\n"
            f"{premium_emoji('admins', '👥')} <b>Active Users:</b> {len(active)}",
            reply_markup=InlineKeyboardMarkup([
                [premium_button("Back", "back", ButtonStyle.PRIMARY, callback_data=f"newuser_panel:{chat_id}")]
            ]),
        )
        return

    if action == "newuser_toggle":
        state = data[2] == "on"
        if state:
            await save_config(client, chat_id, enabled=True)
            await callback_query.answer("New User Protection enabled.", show_alert=True)
        else:
            restored = await lift_active_restrictions(client, chat_id)
            await save_config(client, chat_id, enabled=False)
            await callback_query.answer(
                f"Disabled. Restored {restored} active user(s).",
                show_alert=True,
            )
        await render_panel(client, callback_query, chat_id)
        return

    if action == "newuser_time":
        duration = int(data[2])
        if duration < 30 * 60 or duration > MAX_DURATION:
            await callback_query.answer("Invalid duration.", show_alert=True)
            return
        await save_config(client, chat_id, duration=duration)
        await callback_query.answer(f"Duration set to {format_duration(duration)}.", show_alert=True)
        await render_panel(client, callback_query, chat_id)
        return

    if action == "newuser_step":
        _, _, direction = data
        _, current = await get_config(client, chat_id)
        if direction == "up":
            candidates = [x for x in PRESET_DURATIONS if x > current]
            new_duration = candidates[0] if candidates else PRESET_DURATIONS[-1]
        else:
            candidates = [x for x in PRESET_DURATIONS if x < current]
            new_duration = candidates[-1] if candidates else PRESET_DURATIONS[0]
        await save_config(client, chat_id, duration=new_duration)
        await callback_query.answer(f"Duration: {format_duration(new_duration)}")
        await render_panel(client, callback_query, chat_id)
        return

    if action == "newuser_custom":
        CUSTOM_PENDING[(callback_query.from_user.id, chat_id)] = {
            "chat_id": chat_id,
            "expires": time.time() + CUSTOM_TIMEOUT,
        }
        await callback_query.answer()
        await callback_query.edit_message_text(
            f"{premium_emoji('stats', '⚙️')} <b>Custom Restriction Time</b>\n\n"
            f"Send a duration such as <code>18h</code>, <code>90m</code>, or <code>2d</code>.\n"
            f"Allowed range: <b>30 minutes to 365 days</b>.\n\n"
            f"<i>This request expires in 2 minutes.</i>",
            reply_markup=InlineKeyboardMarkup([
                [premium_button("Cancel", "cancel", ButtonStyle.DANGER, callback_data=f"newuser_panel:{chat_id}")]
            ]),
        )
        return


@Client.on_message(filters.group & ~filters.service, group=-9)
async def custom_duration_input(client: Client, message: Message):
    if not message.from_user:
        return

    pending = CUSTOM_PENDING.get((message.from_user.id, message.chat.id))
    if not pending:
        return

    if pending["expires"] < time.time():
        CUSTOM_PENDING.pop((message.from_user.id, message.chat.id), None)
        return

    chat_id = pending["chat_id"]
    if message.chat.id != chat_id:
        return

    if not await is_admin_or_owner(client, chat_id, message.from_user.id):
        CUSTOM_PENDING.pop((message.from_user.id, message.chat.id), None)
        return

    duration = parse_duration(message.text or "")
    if duration is None:
        await message.reply_text(
            f"{premium_emoji('cancel', '❌')} <b>Invalid duration.</b>\n"
            f"Use values like <code>18h</code>, <code>90m</code>, or <code>2d</code>. Minimum is <b>30 minutes</b>."
        )
        return

    CUSTOM_PENDING.pop((message.from_user.id, message.chat.id), None)
    await save_config(client, chat_id, duration=duration)
    await message.reply_text(
        f"{premium_emoji('confirm', '✅')} <b>Custom duration saved:</b> {format_duration(duration)}."
    )
    await asyncio.sleep(0.5)


@Client.on_message(filters.new_chat_members & filters.group, group=-8)
async def new_member_restriction(client: Client, message: Message):
    enabled, duration = await get_config(client, message.chat.id)
    if not enabled:
        return

    for user in message.new_chat_members or []:
        if user.is_bot:
            continue

        try:
            if await is_user_admin(client, message.chat.id, user.id):
                continue

            expires_at = datetime.now(timezone.utc) + timedelta(seconds=duration)

            await client.restrict_chat_member(
                message.chat.id,
                user.id,
                permissions=text_only_permissions(),
                until_date=expires_at,
            )

            await client.db.add_newuser_restriction(
                message.chat.id,
                user.id,
                expires_at.replace(tzinfo=None),
            )

            logger.info(
                "New User Protection: restricted %s in %s for %s",
                user.id,
                message.chat.id,
                format_duration(duration),
            )
        except (ChatAdminRequired, UserAdminInvalid) as exc:
            logger.warning(
                "Cannot restrict new user %s in %s: %s",
                user.id,
                message.chat.id,
                exc,
            )
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
        except Exception as exc:
            logger.exception(
                "Failed to restrict new user %s in %s: %s",
                user.id,
                message.chat.id,
                exc,
            )
