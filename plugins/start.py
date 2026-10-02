#This code was published by @MightyAyush on github.com/mightyayush
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, CallbackQuery
from pyrogram.enums import ChatType, ButtonStyle
import logging
from Client.cache import USER_IDS_CACHE, GROUP_IDS_CACHE
from Client.premium import premium_button, premium_emoji

logger = logging.getLogger("BioLinkRemover.Start")

SUPPORT_URL = "https://t.me/ArchonCare"

def get_start_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [premium_button("Add me", "add", ButtonStyle.SUCCESS, url=f"https://t.me/{bot_username}?startgroup=true")],
        [
            premium_button("Updates", "updates", ButtonStyle.DANGER, callback_data="updates_page"),
            premium_button("Support", "support", ButtonStyle.PRIMARY, url=SUPPORT_URL)
        ],
        [
            premium_button("User Guide", "language", ButtonStyle.PRIMARY, callback_data="user_guide"),
            premium_button("About Bot", "source", ButtonStyle.DANGER, callback_data="about_bot")
        ],
        [premium_button("Help", "help", ButtonStyle.SUCCESS, callback_data="help_pm")]
    ])

def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [premium_button("Back", "back", ButtonStyle.DANGER, callback_data="start_pm")]
    ])

@Client.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    chat_type = message.chat.type
    bot_user = await client.get_me()
    if chat_type == ChatType.PRIVATE:
        user_id = message.from_user.id
        if user_id not in USER_IDS_CACHE:
            try:
                await client.db.add_user(user_id, message.from_user.username)
                USER_IDS_CACHE.add(user_id)
                logger.info(f"Registered user via /start: {user_id}")
            except Exception as e:
                logger.error(f"Error registering user in DB via start: {e}")
        welcome_text = (
            f"{premium_emoji('home', '👋')} <b>Hello {message.from_user.first_name}!</b>\n\n"
            f"I am <b>𝖡𝗂𝗈 𝖫𝗂𝗇𝗄 𝖱𝖾𝗌𝗍𝗋𝗂𝖼𝗍𝗈𝗋</b>, a security bot designed to protect your groups "
            f"from spam by scanning user bios for links, dirty words, and suspicious websites.\n\n"
            f"If a user without approval sends a message, I will scan their profile's bio. "
            f"If they violate your rules, I will apply the configured punishment (mute, kick, ban) and delete the message.\n\n"
            f"Use the buttons below to add me to your group or explore my options."
        )
        await message.reply_text(welcome_text, reply_markup=get_start_keyboard(bot_user.username))
    else:
        chat_id = message.chat.id
        if chat_id not in GROUP_IDS_CACHE:
            try:
                await client.db.add_group(chat_id, message.chat.title)
                GROUP_IDS_CACHE.add(chat_id)
                logger.info(f"Registered group via /start: {chat_id}")
            except Exception as e:
                logger.error(f"Error registering group in DB via start: {e}")
        keyboard = InlineKeyboardMarkup([
            [premium_button("Start in Private", "add", ButtonStyle.SUCCESS, url=f"https://t.me/{bot_user.username}?start=start")]
        ])
        await message.reply_text(
            f"{premium_emoji('home', '👋')} <b>Welcome!</b>\n\n"
            f"Please run the `/start` command in my private messages to see my instructions, "
            f"or click the button below to start the chat.",
            reply_markup=keyboard
        )

@Client.on_callback_query(filters.regex("^start_pm$"))
async def start_pm_callback(client: Client, callback_query: CallbackQuery):
    bot_user = await client.get_me()
    welcome_text = (
        f"{premium_emoji('home', '👋')} <b>Hello {callback_query.from_user.first_name}!</b>\n\n"
        f"I am <b>𝖡𝗂𝗈 𝖫𝗂𝗇𝗄 𝖱𝖾𝗌𝗍𝗋𝗂𝖼𝗍𝗈𝗋</b>, I help keep your groups safe by checking user bios for unwanted links "
        f"suspicious websites and blacklisted words.\n\n"
        f"<tg-emoji emoji-id='4904936030232117798'>⚙️</tg-emoji> Violations can be automatically removed with your configured punishment.\n\n"
        f"<tg-emoji emoji-id='5960842268096073715'>👆</tg-emoji> Use the help button to explore my features."
    )
    await callback_query.answer()
    await callback_query.edit_message_text(text=welcome_text, reply_markup=get_start_keyboard(bot_user.username))


@Client.on_callback_query(filters.regex("^updates_page$"))
async def updates_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer()
    text = (
        f"{premium_emoji('updates', '📢')} <b>Updates</b>\n\n"
        f"{premium_emoji('source', '💡')} Bot updates and announcements will appear here.\n\n"
        f"Please check back here whenever a new feature or important change is released."
    )
    await callback_query.edit_message_text(text=text, reply_markup=back_keyboard())

@Client.on_callback_query(filters.regex("^user_guide$"))
async def user_guide_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer()
    text = (
        f"{premium_emoji('language', '📚')} <b>User Guide</b>\n\n"
        f"{premium_emoji('add', '➕')} <b>1. Add me</b> to your group and give the required admin permissions.\n\n"
        f"{premium_emoji('admins', '👮')} <b>2. Approve trusted users</b> with `/approve`.\n\n"
        f"{premium_emoji('auth', '🛡️')} <b>3. Configure moderation</b> with `/config` to choose ban, mute, or kick.\n\n"
        f"{premium_emoji('help', '💡')} <b>4. Need more help?</b> Open the Help Center for every available command."
    )
    await callback_query.edit_message_text(text=text, reply_markup=back_keyboard())

@Client.on_callback_query(filters.regex("^about_bot$"))
async def about_bot_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer()
    text = (
        f"{premium_emoji('source', '🛡️')} <b>𝖡𝗂𝗈 𝖫𝗂𝗇𝗄 𝖱𝖾𝗌𝗍𝗋𝗂𝖼𝗍𝗈𝗋</b>\n\n"
        f"<b>𝖡𝗂𝗈 𝖫𝗂𝗇𝗄 𝖱𝖾𝗌𝗍𝗋𝗂𝖼𝗍𝗈𝗋</b> is a Telegram group security bot that helps detect suspicious links, "
        f"blacklisted words, and unwanted websites in user bios.\n\n"
        f"{premium_emoji('auth', '⚙️')} It can automatically remove violating messages and apply the group's configured punishment.\n\n"
        f"{premium_emoji('help', '📚')} Use <code>/help</code> to explore the complete command guide."
    )
    await callback_query.edit_message_text(text=text, reply_markup=back_keyboard())
