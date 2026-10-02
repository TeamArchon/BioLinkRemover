#This code was published by @MightyAyush on github.com/mightyayush
import os
from dotenv import load_dotenv

load_dotenv()

def get_env_int(key, default=None):
    val = os.getenv(key)
    return int(val) if val and val.strip().replace("-", "").isdigit() else default

def get_env_list(key, default=None):
    if default is None:
        default = []
    val = os.getenv(key)
    if not val:
        return default
    
    val = val.strip()
    if val.startswith('[') and val.endswith(']'):
        val = val[1:-1]
        
    res = []
    for x in val.split(','):
        x_clean = x.strip()
        if x_clean.replace("-", "").isdigit():
            res.append(int(x_clean))
    return res

API_ID = get_env_int("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = get_env_int("OWNER_ID")
SUDO_USERS = [OWNER_ID] #Add more sudo users to give access of gcast, ucast

MONGO_DB = os.getenv("MONGO_DB")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "BioLinkRemover")

LOGGER_GROUP = get_env_int("LOGGER_GROUP")
DATABASE_CHANNEL = LOGGER_GROUP

DIRTY_WORDS = [
    "pussy", "porn", "xxx", "sex", "crypto double", "earn free btc", 
    "free money", "scam", "investment", "invest here", "easy money", 
    "casino", "gamble", "onlyfans", "sugar daddy", "sugar mommy"
]

DIRTY_SITES = [
    "bit.ly", "tinyurl.com", "t.co", "shorturl.at", "cutt.ly", "linktr.ee"
]
