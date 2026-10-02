# 🛡️ BioLinkRemover Bot

`BioLinkRemover` is a powerful, production-ready Telegram group security and auto-moderation bot. It automatically scans the biography/about sections of users sending messages in your group. If a user's bio contains spam links, blacklisted domains, or dirty words, the bot deletes their message and applies a configurable punishment (mute, kick, or ban).

---

## ✨ Features

- **Automated Bio Scanner:** Scans user profiles using Telegram's raw API (`GetFullUser`) upon sending messages.
- **Link & Keyword Blocker:** Checks bios against a robust URL pattern regex and custom lists of dirty words/spam links.
- **Interactive Moderation Cards:**
  - **Mute Mode:** Warning cards include a **🔄 Refresh (Check Bio Again)** button. Muted users can clean their bio and click this button to self-unmute without needing administrator help.
  - **Ban Mode:** Warning cards include an **🔓 Unban User** button so group administrators can lift bans instantly.
- **Group Whitelisting:** Admins can approve specific users to bypass all bio scans.
- **Dynamic Configuration:** Easily set punishment types (`mute`, `kick`, `ban`) via commands or an inline interactive settings panel.
- **Silent Database Registration:** Automatically caches and stores user and group data into MongoDB on first contact.
- **Broadcast System:** Owner-only commands to broadcast text or forward media to all registered groups and users.
- **High Performance Caching:** Utilizes in-memory sets and TTL caches for whitelists, configs, and admin lists to prevent rate limits and API FloodWaits.

---

## 🛠️ Project Structure

```
BioLinkProtections/
├── .env                  # Environment configuration secrets
├── requirements.txt      # Project python dependencies
├── config.py             # Global configurations & environment variable loader
├── main.py               # Application entrypoint
├── setup.sh              # Bash installer for Linux VPS deployment
├── Client/
│   ├── __init__.py
│   ├── bot.py            # Custom Client subclass with db connection and startup caching
│   ├── database.py       # Asynchronous MongoDB database driver (Motor)
│   ├── cache.py          # Shared sets and dicts for caching whitelists, config, and admins
│   └── helpers.py        # Shared permission checking and cache retrievers
└── plugins/
    ├── __init__.py
    ├── admin.py          # Group moderation & owner broadcast commands
    ├── start.py          # /start command greeting menus (PM & Groups)
    └── watcher.py        # Core bio scanner and automated card interactions
```

---

## 📋 Commands Index

| Command | Scope | Level | Description |
| :--- | :--- | :--- | :--- |
| `/start` | PM & Groups | All Users | Starts the bot; returns interactive welcoming menus. |
| `/help` | PM & Groups | Admins / Owner | Displays help details tailored to permissions. |
| `/approve` | Groups | Group Admins | Whitelists a user (via reply or ID/username) to bypass bio scans. |
| `/unapprove` | Groups | Group Admins | Removes a user from the group whitelist. |
| `/unapproveall`| Groups | Group Admins | Clears all whitelisted users in the current group. |
| `/approved` | Groups | Group Admins | Lists all currently whitelisted users in the group. |
| `/config` | Groups | Group Admins | Configures punishment mode (`ban`, `mute`, `kick`) via buttons. |
| `/stats` | Private Chat | Bot Owner | Shows bot usage stats (registered users and groups). |
| `/gcast` | Private Chat | Bot Owner | Broadcasts text or forwards a replied message to all groups. |
| `/ucast` | Private Chat | Bot Owner | Broadcasts text or forwards a replied message to all users. |

---

## 🚀 Setup & VPS Deployment Guide

### Prerequisites
- **Python 3.10+**
- **MongoDB Database:** Get a free Atlas connection string at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
- **Telegram Credentials:** Get your `API_ID` and `API_HASH` at [my.telegram.org](https://my.telegram.org/), and a `BOT_TOKEN` from [@BotFather](https://t.me/BotFather).

### VPS Setup (Linux Ubuntu/Debian)
1. Upload the project folder to your VPS.
2. Navigate to the project directory and run the automatic setup script:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
3. The setup script will:
   - Install required system packages (`python3-venv`, `git`, etc.).
   - Set up a Python virtual environment and install requirements.
   - Interactively ask you to fill in your `.env` configuration (it will read and pre-fill existing values if available).
   - Ask if you want to install and launch the bot as a **systemd service** (`biolink.service`) for 24/7 background running.

### Manual Running
If you choose to run the bot manually:
```bash
# Activate virtual environment
source venv/bin/activate

# Start the bot
python main.py
```

### Managing the Service
If you configured the systemd service:
- **Check Bot Status:** `sudo systemctl status biolink`
- **View Live Logs:** `sudo journalctl -u biolink -f`
- **Restart Bot:** `sudo systemctl restart biolink`
- **Stop Bot:** `sudo systemctl stop biolink`

---

## 💳 Credits & License

Made with ❤️ by:
- **Archon:** [@TheArchon](https://github.com/TheArchon)
- **Telegram:** [@ArchonNetwork](https://t.me/ArchonNetwork)
- **Ayush:** [@mightyayush](https://github.com/mightyayush)

*This code was published by @TeamArchon*
