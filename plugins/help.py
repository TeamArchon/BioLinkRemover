from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, CallbackQuery
from pyrogram.enums import ChatType, ButtonStyle
import config
from Client.helpers import is_user_admin
from Client.premium import premium_button, premium_emoji

PAGES = [
    {
        "title": "General Commands",
        "icon": "help",
        "commands": [
            ("/start", "Start the bot and open the main menu."),
            ("/help", "Open this Help Center."),
        ],
        "note": "Use the main menu buttons for quick access to the bot's features."
    },
    {
        "title": "Approval & Whitelist",
        "icon": "admins",
        "commands": [
            ("/approve", "Approve a user so their bio is not scanned in this group. Use a reply, user ID, or username."),
            ("/unapprove", "Remove a user from the approved list."),
            ("/unapproveall", "Clear every approved user in the group."),
            ("/approved", "Show the users currently approved in the group."),
        ],
        "note": "These commands are available to group administrators."
    },
    {
        "title": "New User Protection",
        "icon": "auth",
        "commands": [
            ("/newuser", "Open the New User Protection panel. Configure enable/disable and the restriction duration."),
        ],
        "note": "New members can be limited to text-only messages for a configurable period. Telegram automatically lifts the restriction when the timer expires."
    },
    {
        "title": "Moderation & Configuration",
        "icon": "auth",
        "commands": [
            ("/config", "View or change the punishment mode: ban, mute, or kick."),
        ],
        "note": "BioGuardBot checks non-admin, non-approved users for links, blacklisted words, and suspicious sites in their bio."
    },
    {
        "title": "Owner Commands",
        "icon": "owner",
        "commands": [
            ("/stats", "Show registered user and group statistics."),
            ("/gcast", "Broadcast a message to all registered groups. Reply to a message or provide text."),
            ("/ucast", "Broadcast a message to all users who started the bot in private chat. Reply to a message or provide text."),
        ],
        "note": "Owner commands work only for the configured owner and sudo users."
    },
    {
        "title": "How BioGuardBot Works",
        "icon": "source",
        "commands": [],
        "note": "When a non-admin, non-approved member sends a message, BioGuardBot checks the user's bio. If a violation is found, the message is removed and the configured action is applied. Admins can approve trusted users with /approve, while /config controls the punishment mode."
    }
]

def help_keyboard(page: int) -> InlineKeyboardMarkup:
    rows = []
    nav = []
    if page > 0:
        nav.append(premium_button("Prev", "back", ButtonStyle.PRIMARY, callback_data=f"help_page:{page - 1}"))
    nav.append(premium_button(f"{page + 1}/{len(PAGES)}", "queue", ButtonStyle.DANGER, callback_data=f"help_page:{page}"))
    if page < len(PAGES) - 1:
        nav.append(premium_button("Next", "skip", ButtonStyle.PRIMARY, callback_data=f"help_page:{page + 1}"))
    rows.append(nav)
    rows.append([premium_button("Home", "home", ButtonStyle.SUCCESS, callback_data="start_pm")])
    return InlineKeyboardMarkup(rows)

def render_help_page(page: int) -> str:
    data = PAGES[page]
    text = (
        f"{premium_emoji('help', '🧊')} <b>Help Center</b> "
        f"{premium_emoji('queue', '🎟️')} <b>{page + 1}/{len(PAGES)}</b>\n\n"
        f"{premium_emoji(data['icon'], '📚')} <b>{data['title']}</b>\n\n"
    )
    if data["commands"]:
        for command, description in data["commands"]:
            text += (
                "<blockquote>"
                f"{premium_emoji('default', '🤖')} <code>{command}</code> — {description}"
                "</blockquote>\n"
            )
        text += f"\n{premium_emoji('source', '💡')} <i>{data['note']}</i>"
    else:
        text += f"{premium_emoji('source', '💡')} <i>{data['note']}</i>"
    return text

async def show_help(client: Client, target, page: int):
    page = max(0, min(page, len(PAGES) - 1))
    text = render_help_page(page)
    keyboard = help_keyboard(page)
    if isinstance(target, CallbackQuery):
        await target.edit_message_text(text=text, reply_markup=keyboard)
    else:
        await target.reply_text(text=text, reply_markup=keyboard)

@Client.on_message(filters.command("help"))
async def help_cmd(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    is_owner = user_id == config.OWNER_ID or user_id in config.SUDO_USERS
    if message.chat.type == ChatType.PRIVATE:
        await show_help(client, message, 0)
        return
    if await is_user_admin(client, message.chat.id, user_id) or is_owner:
        await show_help(client, message, 0)
    else:
        await message.reply_text(
            f"{premium_emoji('cancel', '❌')} <b>Access Denied:</b> Only group administrators can open the admin Help Center here."
        )

@Client.on_callback_query(filters.regex(r"^help_page:(\d+)$"))
async def help_page_callback(client: Client, callback_query: CallbackQuery):
    page = int(callback_query.data.split(":")[1])
    await callback_query.answer()
    await show_help(client, callback_query, page)

@Client.on_callback_query(filters.regex(r"^help_pm$"))
async def help_pm_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer()
    await show_help(client, callback_query, 0)
