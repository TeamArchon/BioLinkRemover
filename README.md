# 🛡️ BioLinkRemover Bot

`BioLinkRemover` is a Telegram group security and auto-moderation bot. It scans user biographies/about sections and can delete messages and apply configurable punishments when blocked links or keywords are detected.

## ✨ Features

- Automated Telegram bio scanner
- Link and keyword blocker
- Mute, kick and ban modes
- Interactive moderation cards
- Group user whitelisting
- MongoDB-backed user/group registration
- Owner broadcast commands
- In-memory caching for frequently used data

## 🛠️ Project Structure

```text
BioGuard/
├── .python-version
├── Procfile
├── requirements.txt
├── config.py
├── main.py
├── setup.sh
├── Client/
│   ├── __init__.py
│   ├── bot.py
│   ├── database.py
│   ├── cache.py
│   ├── helpers.py
│   └── premium.py
└── plugins/
    ├── __init__.py
    ├── admin.py
    ├── help.py
    ├── newuser.py
    ├── start.py
    ├── updater.py
    └── watcher.py
```

## 📋 Commands Index

| Command | Scope | Level | Description |
| :--- | :--- | :--- | :--- |
| `/start` | PM & Groups | All Users | Starts the bot |
| `/help` | PM & Groups | Admins / Owner | Shows help |
| `/approve` | Groups | Group Admins | Whitelists a user |
| `/unapprove` | Groups | Group Admins | Removes a user from whitelist |
| `/unapproveall` | Groups | Group Admins | Clears the group whitelist |
| `/approved` | Groups | Group Admins | Lists whitelisted users |
| `/config` | Groups | Group Admins | Configures punishment mode |
| `/stats` | Private Chat | Bot Owner | Shows bot statistics |
| `/gcast` | Private Chat | Bot Owner | Broadcasts to groups |
| `/ucast` | Private Chat | Bot Owner | Broadcasts to users |

## 🔐 Environment Variables

The bot reads its configuration from environment variables:

```text
OWNER_ID=123456789
API_ID=123456
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
MONGO_DB=mongodb_connection_string
MONGODB_DB_NAME=BioLinkRemover
LOGGER_GROUP=-100xxxxxxxxxx
```

Do not commit secrets such as `BOT_TOKEN`, `API_HASH`, or MongoDB credentials to GitHub.

---

## 🚀 Heroku Deployment

This project is configured to run on Heroku as a **worker dyno**. Telegram bots do not need Heroku's `web` HTTP process, so the root `Procfile` starts the bot with:

```text
worker: python3 main.py
```

### 1. Create a Heroku app

Create a new app from the Heroku dashboard or Heroku CLI.

### 2. Add Config Vars

In your Heroku app, open **Settings → Config Vars** and add:

```text
OWNER_ID
API_ID
API_HASH
BOT_TOKEN
MONGO_DB
MONGODB_DB_NAME
LOGGER_GROUP
```

Use the same values you normally put in `.env` on a VPS.

### 3. Deploy the repository

Push the project to the Heroku app using Git:

```bash
git init
git add .
git commit -m "Deploy BioLinkRemover to Heroku"
heroku git:remote -a YOUR_APP_NAME
git push heroku main
```

If your GitHub repository is already connected to Heroku, you can deploy it from the Heroku Deploy/Deployment settings instead.

### 4. Scale the worker

After deployment, make sure one worker dyno is running:

```bash
heroku ps:scale worker=1
```

Check the process:

```bash
heroku ps
```

View live logs:

```bash
heroku logs --tail
```

### ⚠️ Important

- MongoDB must be reachable from Heroku.
- Keep all secrets in Heroku Config Vars.
- Do **not** upload a `.env` file containing real credentials.
- The bot uses a Heroku `worker` process, not a `web` process.
- `setup.sh` is intended for VPS/Linux setup and is not required for Heroku deployment.

---

## 🚀 VPS Deployment

### Prerequisites

- Python 3.10+
- MongoDB
- Telegram API ID/API HASH
- Telegram Bot Token

Run:

```bash
chmod +x setup.sh
./setup.sh
```

For manual startup:

```bash
source venv/bin/activate
python3 main.py
```

## 💳 Credits & License

Made with ❤️ by:

- **Archon:** [@TheArchon](https://github.com/TheArchon)
- **Telegram:** [@ArchonNetwork](https://t.me/ArchonNetwork)
- **Ayush:** [@mightyayush](https://github.com/mightyayush)

*This code was published by @TeamArchon*
