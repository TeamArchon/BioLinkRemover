import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.enums import ButtonStyle
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import config
from Client.premium import premium_button, premium_emoji

log = logging.getLogger("BioGuard.Updater")
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".bioguard_update.json"
BACKUPS = ROOT / "backups" / "updater"
REPO = "TheArchon/BioGuard"
BRANCH = "main"
LOCK = asyncio.Lock()
AUTO_CHECK = os.getenv("BIOGUARD_AUTO_UPDATE_CHECK", "true").lower() in {"1", "true", "yes", "on"}
CHECK_INTERVAL = max(300, int(os.getenv("BIOGUARD_UPDATE_INTERVAL", "3600")))
NOTIFY_COOLDOWN = max(300, int(os.getenv("BIOGUARD_UPDATE_NOTIFY_COOLDOWN", "21600")))

PROTECTED = {
    ".env", ".git", "venv", ".venv", "__pycache__",
    "backups", ".bioguard_update.json"
}

def github_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "BioGuard-Updater",
            "Accept": "application/vnd.github+json"
        }
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "BioGuard-Updater"})
    with urllib.request.urlopen(req, timeout=180) as r:
        with open(path, "wb") as f:
            shutil.copyfileobj(r, f)

def latest_commit():
    data = github_json(f"https://api.github.com/repos/{REPO}/commits/{BRANCH}")
    return data["sha"], data["commit"]["message"].splitlines()[0]

def latest_release():
    try:
        data = github_json(f"https://api.github.com/repos/{REPO}/releases/latest")
        return {
            "tag": data.get("tag_name") or "",
            "name": data.get("name") or "",
            "url": data.get("html_url") or ""
        }
    except Exception:
        return {}

def read_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}

def local_commit():
    state = read_state()
    if state.get("repository") == REPO and state.get("branch") == BRANCH and state.get("commit"):
        return state["commit"]
    git = shutil.which("git")
    if git and (ROOT / ".git").exists():
        try:
            r = subprocess.run(
                [git, "rev-parse", "HEAD"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            return r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return None

def save_state(commit, **extra):
    data = read_state()
    data.update({
        "repository": REPO,
        "branch": BRANCH,
        "commit": commit,
        "updated_at": int(time.time())
    })
    data.update(extra)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE)

def history():
    state = read_state()
    return state.get("history", [])

def add_history(entry):
    state = read_state()
    items = state.get("history", [])
    items.insert(0, entry)
    save_state(state.get("commit") or local_commit() or "", history=items[:20])

def protected(path):
    return any(x in PROTECTED for x in path.parts)

def safe_rel(path):
    p = Path(path)
    return not p.is_absolute() and ".." not in p.parts and not protected(p)

def extract_zip(zip_path, destination):
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if not safe_rel(info.filename):
                raise RuntimeError(f"Unsafe archive path: {info.filename}")
        z.extractall(destination)
    folders = [p for p in destination.iterdir() if p.is_dir()]
    if len(folders) != 1:
        raise RuntimeError("Invalid GitHub archive.")
    return folders[0]

def repo_files(source):
    return [
        p.relative_to(source)
        for p in source.rglob("*")
        if p.is_file() and safe_rel(p.relative_to(source))
    ]

def backup_files(files, backup):
    old = []
    new = []
    for rel in files:
        if protected(rel):
            continue
        src = ROOT / rel
        dst = backup / rel
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            old.append(rel)
        elif not src.exists():
            new.append(rel)
    return old, new

def apply_files(source, files):
    for rel in files:
        if protected(rel):
            continue
        src = source / rel
        dst = ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def rollback(backup, old, new):
    for rel in old:
        src = backup / rel
        dst = ROOT / rel
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    for rel in new:
        dst = ROOT / rel
        if dst.is_file():
            try:
                dst.unlink()
            except OSError:
                log.exception("Could not remove new file during rollback: %s", dst)

def validate(files):
    for rel in files:
        if rel.suffix != ".py" or protected(rel):
            continue
        path = ROOT / rel
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

def requirements_changed(backup):
    current = ROOT / "requirements.txt"
    old = backup / "requirements.txt"
    if not current.exists():
        return False
    if not old.exists():
        return True
    return current.read_bytes() != old.read_bytes()

def install_requirements(requirements=None):
    req = requirements or (ROOT / "requirements.txt")
    if not req.exists():
        return
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=900,
        check=True
    )

def changed_summary(files):
    names = [str(x).replace("\\", "/") for x in files if not protected(x)]
    names.sort()
    if len(names) <= 15:
        return names
    return names[:15] + [f"... +{len(names) - 15} more"]

async def update_bot():
    async with LOCK:
        with tempfile.TemporaryDirectory(prefix="bioguard-") as tmp:
            tmp = Path(tmp)
            archive = tmp / "update.zip"
            source_dir = tmp / "source"
            latest, message = await asyncio.to_thread(latest_commit)
            current = local_commit()
            if current == latest:
                return False, latest, "already_latest", [], None

            url = f"https://github.com/{REPO}/archive/refs/heads/{BRANCH}.zip"
            await asyncio.to_thread(download, url, archive)
            source_dir.mkdir()
            source = await asyncio.to_thread(extract_zip, archive, source_dir)
            files = repo_files(source)
            if not files:
                raise RuntimeError("GitHub update is empty.")

            stamp = time.strftime("%Y%m%d-%H%M%S")
            backup = BACKUPS / stamp
            backup.mkdir(parents=True, exist_ok=True)
            old, new = await asyncio.to_thread(backup_files, files, backup)

            try:
                await asyncio.to_thread(apply_files, source, files)
                await asyncio.to_thread(validate, files)
                if requirements_changed(backup):
                    await asyncio.to_thread(install_requirements)
                save_state(latest, last_backup=str(backup.relative_to(ROOT)))
                add_history({
                    "time": int(time.time()),
                    "from": current,
                    "to": latest,
                    "message": message[:500],
                    "backup": str(backup.relative_to(ROOT)),
                    "files": changed_summary(files),
                    "status": "success"
                })
                return True, latest, message, changed_summary(files), backup

            except Exception:
                log.exception("Update failed. Rolling back.")
                await asyncio.to_thread(rollback, backup, old, new)
                old_req = backup / "requirements.txt"
                if old_req.exists():
                    try:
                        await asyncio.to_thread(install_requirements, old_req)
                    except Exception:
                        log.exception("Dependency rollback failed.")
                add_history({
                    "time": int(time.time()),
                    "from": current,
                    "to": latest,
                    "message": message[:500],
                    "backup": str(backup.relative_to(ROOT)),
                    "files": changed_summary(files),
                    "status": "failed_rolled_back"
                })
                raise

def restore_backup(backup):
    if not backup.exists() or not backup.is_dir():
        raise RuntimeError("Backup not found.")
    files = [p.relative_to(backup) for p in backup.rglob("*") if p.is_file()]
    if not files:
        raise RuntimeError("Backup is empty.")
    for rel in files:
        if protected(rel):
            continue
        src = backup / rel
        dst = ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    req = backup / "requirements.txt"
    if req.exists():
        install_requirements(req)
    return len(files)

def latest_backup():
    if not BACKUPS.exists():
        return None
    dirs = sorted((p for p in BACKUPS.iterdir() if p.is_dir()), reverse=True)
    return dirs[0] if dirs else None

def restart_bot():
    os.execv(sys.executable, [sys.executable, *sys.argv])

def authorized(user_id):
    owner = getattr(config, "OWNER_ID", None)
    sudo = getattr(config, "SUDO_USERS", [])
    return user_id == owner or user_id in sudo

def update_keyboard():
    return InlineKeyboardMarkup([[
        premium_button("Update", "updates", ButtonStyle.SUCCESS, callback_data="bgupd:update"),
        premium_button("Cancel", "cancel", ButtonStyle.DANGER, callback_data="bgupd:cancel")
    ]])

def info_keyboard():
    return InlineKeyboardMarkup([[
        premium_button("Check Again", "updates", ButtonStyle.PRIMARY, callback_data="bgupd:check"),
        premium_button("History", "queue", ButtonStyle.PRIMARY, callback_data="bgupd:history")
    ], [
        premium_button("Rollback", "replay", ButtonStyle.DANGER, callback_data="bgupd:rollback")
    ]])

async def check_update_message(message):
    latest, commit_message = await asyncio.to_thread(latest_commit)
    release = await asyncio.to_thread(latest_release)
    current = local_commit()
    if current == latest:
        await message.edit_text(
            f"{premium_emoji('confirm', '✅')} <b>BioGuard is already up to date.</b>\n\n"
            f"<b>Version:</b> <code>{latest[:7]}</code>",
            reply_markup=info_keyboard()
        )
        return False
    await message.edit_text(
        f"{premium_emoji('updates', '🔄')} <b>New update available.</b>\n\n"
        f"<b>Current:</b> <code>{(current or 'Unknown')[:7]}</code>\n"
        f"<b>Latest:</b> <code>{latest[:7]}</code>\n\n"
        f"{premium_emoji('source', '📝')} <b>{commit_message[:500]}</b>\n"
        f"<b>Release:</b> <code>{(release.get('tag') or 'None')[:80]}</code>\n\n"
        "<b>Install this update?</b>",
        reply_markup=update_keyboard()
    )
    return True

@Client.on_message(filters.command("update") & filters.private)
async def update_command(client: Client, message: Message):
    if not message.from_user or not authorized(message.from_user.id):
        return
    if LOCK.locked():
        await message.reply_text(f"{premium_emoji('updates', '🔄')} <b>An update is already running.</b>")
        return
    msg = await message.reply_text(f"{premium_emoji('updates', '🔄')} <b>Checking for updates...</b>")
    try:
        await check_update_message(msg)
    except Exception as e:
        log.exception("Update check failed.")
        await msg.edit_text(
            f"{premium_emoji('cancel', '❌')} <b>Could not check for updates.</b>\n\n"
            f"<code>{str(e)[:700]}</code>",
            reply_markup=info_keyboard()
        )

@Client.on_callback_query(filters.regex(r"^bgupd:(update|cancel|check|history|rollback)$"))
async def update_callback(client: Client, query: CallbackQuery):
    if not query.from_user or not authorized(query.from_user.id):
        await query.answer("You are not authorized.", show_alert=True)
        return
    action = query.data.split(":", 1)[1]

    if action == "cancel":
        await query.answer("Update cancelled.")
        await query.edit_message_text(f"{premium_emoji('cancel', '❌')} <b>Update cancelled.</b>")
        return

    if action == "check":
        await query.answer()
        try:
            await query.edit_message_text(f"{premium_emoji('updates', '🔄')} <b>Checking for updates...</b>")
            await check_update_message(query.message)
        except Exception as e:
            log.exception("Manual update check failed.")
            await query.edit_message_text(
                f"{premium_emoji('cancel', '❌')} <b>Check failed.</b>\n\n<code>{str(e)[:700]}</code>",
                reply_markup=info_keyboard()
            )
        return

    if action == "history":
        await query.answer()
        items = history()[:10]
        if not items:
            text = f"{premium_emoji('queue', '📜')} <b>No update history found.</b>"
        else:
            lines = [f"{premium_emoji('queue', '📜')} <b>Update History</b>\n"]
            for item in items:
                when = time.strftime("%Y-%m-%d %H:%M", time.localtime(item.get("time", 0)))
                status = item.get("status", "unknown")
                lines.append(
                    f"<b>{when}</b> • <code>{str(item.get('to', ''))[:7]}</code> • "
                    f"<b>{status}</b>"
                )
            text = "\n".join(lines)
        await query.edit_message_text(text, reply_markup=info_keyboard())
        return

    if action == "rollback":
        await query.answer()
        if LOCK.locked():
            await query.answer("An update is already running.", show_alert=True)
            return
        backup = latest_backup()
        if not backup:
            await query.edit_message_text(
                f"{premium_emoji('cancel', '❌')} <b>No backup is available for rollback.</b>",
                reply_markup=info_keyboard()
            )
            return
        try:
            async with LOCK:
                count = await asyncio.to_thread(restore_backup, backup)
            previous = ""
            for item in history():
                if item.get("status") == "success" and item.get("to"):
                    previous = item.get("from") or ""
                    break
            save_state(previous or local_commit() or "", last_rollback=str(backup.relative_to(ROOT)))
            add_history({
                "time": int(time.time()),
                "from": local_commit(),
                "to": "rollback",
                "message": "Manual rollback",
                "backup": str(backup.relative_to(ROOT)),
                "files": [f"Restored {count} files"],
                "status": "rollback_success"
            })
            await query.edit_message_text(
                f"{premium_emoji('confirm', '✅')} <b>Rollback completed.</b>\n\n"
                f"<b>Backup:</b> <code>{backup.name}</code>\n"
                "<b>Restarting BioGuard...</b>"
            )
            await asyncio.sleep(2)
            await asyncio.to_thread(restart_bot)
        except Exception as e:
            log.exception("Rollback failed.")
            await query.edit_message_text(
                f"{premium_emoji('cancel', '❌')} <b>Rollback failed.</b>\n\n"
                f"<code>{str(e)[:900]}</code>",
                reply_markup=info_keyboard()
            )
        return

    if LOCK.locked():
        await query.answer("An update is already running.", show_alert=True)
        return

    await query.answer("Updating BioGuard...")
    try:
        await query.edit_message_text(
            f"{premium_emoji('updates', '🔄')} <b>Updating BioGuard...</b>\n\n"
            "Creating backup and validating files."
        )
        updated, commit, message, files, backup = await update_bot()
        if not updated:
            await query.edit_message_text(
                f"{premium_emoji('confirm', '✅')} <b>BioGuard is already up to date.</b>",
                reply_markup=info_keyboard()
            )
            return
        file_text = "\n".join(f"• <code>{x}</code>" for x in files[:15])
        if len(files) > 15:
            file_text += f"\n• <i>+{len(files) - 15} more</i>"
        await query.edit_message_text(
            f"{premium_emoji('confirm', '✅')} <b>Update installed successfully.</b>\n\n"
            f"<b>Version:</b> <code>{commit[:7]}</code>\n"
            f"{premium_emoji('source', '📝')} <b>{message[:400]}</b>\n\n"
            f"<b>Changed files:</b>\n{file_text or '• None'}\n\n"
            "<b>Backup created.</b>\n"
            "<b>Restarting BioGuard...</b>"
        )
        await asyncio.sleep(2)
        await asyncio.to_thread(restart_bot)
    except Exception as e:
        log.exception("Update failed.")
        try:
            await query.edit_message_text(
                f"{premium_emoji('cancel', '❌')} <b>Update failed.</b>\n\n"
                "<b>Previous version restored.</b>\n\n"
                f"<code>{str(e)[:900]}</code>",
                reply_markup=info_keyboard()
            )
        except Exception:
            pass

async def auto_update_checker(client):
    if not AUTO_CHECK:
        return
    await asyncio.sleep(60)
    while True:
        try:
            if not LOCK.locked():
                latest, message = await asyncio.to_thread(latest_commit)
                current = local_commit()
                if current and current != latest:
                    owner = getattr(config, "OWNER_ID", None)
                    state = read_state()
                    last_notice = state.get("last_notice_commit")
                    last_notice_time = int(state.get("last_notice_at", 0) or 0)
                    if owner and (
                        last_notice != latest or time.time() - last_notice_time >= NOTIFY_COOLDOWN
                    ):
                        try:
                            await client.send_message(
                                owner,
                                f"{premium_emoji('updates', '🔄')} <b>New BioGuard update available.</b>\n\n"
                                f"<b>Current:</b> <code>{current[:7]}</code>\n"
                                f"<b>Latest:</b> <code>{latest[:7]}</code>\n\n"
                                f"{premium_emoji('source', '📝')} <b>{message[:500]}</b>",
                                reply_markup=update_keyboard()
                            )
                            save_state(current, last_notice_commit=latest, last_notice_at=int(time.time()))
                        except Exception:
                            log.exception("Could not notify owner about update.")
        except Exception:
            log.exception("Automatic update check failed.")
        await asyncio.sleep(CHECK_INTERVAL)

@Client.on_message(filters.command("updatehistory") & filters.private)
async def update_history_command(client: Client, message: Message):
    if not message.from_user or not authorized(message.from_user.id):
        return
    items = history()[:10]
    if not items:
        await message.reply_text(f"{premium_emoji('queue', '📜')} <b>No update history found.</b>")
        return
    lines = [f"{premium_emoji('queue', '📜')} <b>Update History</b>\n"]
    for item in items:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(item.get("time", 0)))
        lines.append(
            f"<b>{when}</b> • <code>{str(item.get('to', ''))[:7]}</code> • "
            f"<b>{item.get('status', 'unknown')}</b>"
        )
    await message.reply_text("\n".join(lines))

@Client.on_start()
async def updater_start(client):
    try:
        asyncio.create_task(auto_update_checker(client))
    except Exception:
        log.exception("Could not start automatic update checker.")
