#This code was published by @MightyAyush on github.com/mightyayush
from pyrogram import Client
import config
import logging
from Client.database import Database
from Client.cache import USER_IDS_CACHE, GROUP_IDS_CACHE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("BioLinkRemover")

class BioLinkBot(Client):
    def __init__(self):
        super().__init__(
            name="BioLinkRemover",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            plugins=dict(root="plugins")
        )
        self.db = None

    async def start(self, *args, **kwargs):
        await super().start(*args, **kwargs)
        self.db = Database(config.MONGO_DB, config.MONGODB_DB_NAME)
        try:
            user_ids = await self.db.get_all_user_ids()
            group_ids = await self.db.get_all_group_ids()

            USER_IDS_CACHE.update(user_ids)
            GROUP_IDS_CACHE.update(group_ids)

            logger.info(f"Loaded {len(user_ids)} users and {len(group_ids)} groups from DB into cache.")
        except Exception as e:
            logger.error(f"Error pre-filling caches: {e}")

        if config.LOGGER_GROUP:
            try:
                await self.send_message(
                    chat_id=config.LOGGER_GROUP,
                    text="<tg-emoji emoji-id='6271537028307881531'>⚡</tg-emoji> <b>BioLinkRemover Bot has started successfully.</b>"
                )
            except Exception as e:
                logger.warning(f"Could not send startup log to LOGGER_GROUP ({config.LOGGER_GROUP}): {e}")

        logger.info("BioLinkRemover bot started successfully.")

    async def stop(self, *args, **kwargs):
        logger.info("Stopping BioLinkRemover bot...")
        if config.LOGGER_GROUP:
            try:
                await self.send_message(
                    chat_id=config.LOGGER_GROUP,
                    text="<tg-emoji emoji-id='5275969776668134187'>💤</tg-emoji> <b>BioLinkRemover Bot has been stopped.</b>"
                )
            except Exception:
                pass
        await super().stop(*args, **kwargs)
        logger.info("BioLinkRemover bot stopped.")
