"""
Telegram Bot Starter
- User dashboard
- Admin dashboard
- SQLite persistence
- User blocking/unblocking
- Broadcasts
- Maintenance mode
- Ready for deployment with environment variables

This starter intentionally does not automate fake engagement, farm points,
forge device-attestation data, or bypass a third-party service's protections.
Connect only an official/authorized API in the integration section below.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ----------------------------- Configuration -----------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "").strip()
DB_PATH = os.getenv("DB_PATH", "bot_data.sqlite3")
BOT_NAME = os.getenv("BOT_NAME", "Service Manager")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "").strip().lstrip("@")

def parse_admin_ids(value: str) -> set[int]:
    result: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if item:
            try:
                result.add(int(item))
            except ValueError:
                logging.warning("Ignoring invalid ADMIN_IDS item: %r", item)
    return result

ADMIN_IDS = parse_admin_ids(ADMIN_IDS_RAW)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("telegram-service-bot")

# ------------------------------- Database ---------------------------------

class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    joined_at TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    is_blocked INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    event TEXT NOT NULL,
                    details TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );
            """)
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES('maintenance', '0')"
            )

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def touch_user(self, user_id: int, username: str | None, first_name: str) -> None:
        now = self.now()
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO users(user_id, username, first_name, joined_at, last_seen)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    first_name=excluded.first_name,
                    last_seen=excluded.last_seen
            """, (user_id, username or "", first_name or "", now, now))

    def get_user(self, user_id: int):
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE user_id=?", (user_id,)
            ).fetchone()

    def is_blocked(self, user_id: int) -> bool:
        row = self.get_user(user_id)
        return bool(row and row["is_blocked"])

    def set_blocked(self, user_id: int, blocked: bool) -> bool:
        with self.connect() as conn:
            cur = conn.execute(
                "UPDATE users SET is_blocked=? WHERE user_id=?",
                (1 if blocked else 0, user_id),
            )
            return cur.rowcount > 0

    def user_count(self) -> int:
        with self.connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def blocked_count(self) -> int:
        with self.connect() as conn:
            return int(conn.execute(
                "SELECT COUNT(*) FROM users WHERE is_blocked=1"
            ).fetchone()[0])

    def all_user_ids(self) -> list[int]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT user_id FROM users WHERE is_blocked=0"
            ).fetchall()
            return [int(row["user_id"]) for row in rows]

    def set_setting(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO settings(key, value) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """, (key, value))

    def get_setting(self, key: str, default: str = "") -> str:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def log_event(self, user_id: int | None, event: str, details: str = "") -> None:
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO activity(user_id, event, details, created_at)
                VALUES(?, ?, ?, ?)
            """, (user_id, event, details[:1000], self.now()))

    def recent_activity(self, limit: int = 10):
        with self.connect() as conn:
            return conn.execute("""
                SELECT user_id, event, details, created_at
                FROM activity ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()

db = Database(DB_PATH)

# ------------------------------- Keyboards --------------------------------

def user_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 حسابي", callback_data="profile"),
         InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("🧩 الخدمات", callback_data="services")],
        [InlineKeyboardButton("ℹ️ المساعدة", callback_data="help")],
    ])

def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
         InlineKeyboardButton("👥 عدد المستخدمين", callback_data="admin_users")],
        [InlineKeyboardButton("🔧 وضع الصيانة", callback_data="admin_maintenance")],
        [InlineKeyboardButton("📜 آخر النشاطات", callback_data="admin_activity")],
        [InlineKeyboardButton("📣 تعليمات الإذاعة", callback_data="admin_broadcast_help")],
        [InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")],
    ])

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def maintenance_enabled() -> bool:
    return db.get_setting("maintenance", "0") == "1"

# --------------------------------- Text ------------------------------------

WELCOME = (
    f"أهلاً بك في *{BOT_NAME}* 👋\n\n"
    "اختر القسم المطلوب من الأزرار بالأسفل."
)

HELP_TEXT = (
    "ℹ️ *المساعدة*\n\n"
    "• استخدم الأزرار للتنقل بين الأقسام.\n"
    "• إذا واجهت مشكلة، تواصل مع الدعم.\n"
    "• لا ترسل كلمة المرور أو رموز التحقق لأي شخص.\n\n"
    "هذا الإصدار يحتوي على إدارة المستخدمين ولوحة الأدمن، "
    "ويمكن ربطه لاحقاً بواجهة رسمية ومصرّح بها."
)

SERVICES_TEXT = (
    "🧩 *الخدمات المتاحة حالياً*\n\n"
    "• إدارة الحساب الشخصي داخل البوت.\n"
    "• عرض حالة النظام.\n"
    "• متابعة الإعلانات والتنبيهات.\n\n"
    "تكامل الخدمات الخارجية غير مفعّل في هذا الإصدار. "
    "لا تدخل كلمات مرور حساباتك أو رموز جلساتك هنا."
)

# ------------------------------- Utilities ---------------------------------

async def safe_answer(update: Update, text: str = "", alert: bool = False) -> None:
    query = update.callback_query
    if query:
        try:
            await query.answer(text=text, show_alert=alert)
        except Exception:
            pass

async def guard_user(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    db.touch_user(user.id, user.username, user.first_name)
    if db.is_blocked(user.id) and not is_admin(user.id):
        if update.callback_query:
            await safe_answer(update, "تم تقييد وصولك إلى البوت.", True)
        elif update.effective_message:
            await update.effective_message.reply_text("تم تقييد وصولك إلى البوت.")
        return False
    if maintenance_enabled() and not is_admin(user.id):
        if update.callback_query:
            await safe_answer(update, "البوت في وضع الصيانة حالياً.", True)
        elif update.effective_message:
            await update.effective_message.reply_text(
                "🛠 البوت في وضع الصيانة حالياً. حاول لاحقاً."
            )
        return False
    return True

async def edit_or_reply(update: Update, text: str, keyboard=None) -> None:
    query = update.callback_query
    if query and query.message:
        await query.message.edit_text(
            text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )
    elif update.effective_message:
        await update.effective_message.reply_text(
            text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )

# -------------------------------- Commands ---------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update):
        return
    user = update.effective_user
    db.log_event(user.id, "start")
    await update.effective_message.reply_text(
        WELCOME, reply_markup=user_keyboard(), parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update):
        return
    await update.effective_message.reply_text(
        HELP_TEXT, parse_mode=ParseMode.MARKDOWN
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update):
        return
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text("⛔ هذا الأمر للأدمن فقط.")
        return
    await update.effective_message.reply_text(
        "🛡 *لوحة تحكم الأدمن*",
        reply_markup=admin_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )

async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("الاستخدام: /block USER_ID")
        return
    target = int(context.args[0])
    if target in ADMIN_IDS:
        await update.effective_message.reply_text("لا يمكن حظر أدمن.")
        return
    if db.set_blocked(target, True):
        db.log_event(update.effective_user.id, "block_user", str(target))
        await update.effective_message.reply_text(f"تم حظر المستخدم {target}.")
    else:
        await update.effective_message.reply_text("المستخدم غير موجود في قاعدة البيانات.")

async def unblock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("الاستخدام: /unblock USER_ID")
        return
    target = int(context.args[0])
    if db.set_blocked(target, False):
        db.log_event(update.effective_user.id, "unblock_user", str(target))
        await update.effective_message.reply_text(f"تم فك حظر المستخدم {target}.")
    else:
        await update.effective_message.reply_text("المستخدم غير موجود في قاعدة البيانات.")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return
    message = " ".join(context.args).strip()
    if not message:
        await update.effective_message.reply_text(
            "الاستخدام:\n/broadcast نص الرسالة\n\n"
            "سيتم إرسال النص إلى المستخدمين غير المحظورين."
        )
        return
    ids = db.all_user_ids()
    sent = failed = 0
    status = await update.effective_message.reply_text(
        f"بدأ الإرسال إلى {len(ids)} مستخدم..."
    )
    for user_id in ids:
        try:
            await context.bot.send_message(
                chat_id=user_id, text=message, disable_web_page_preview=True
            )
            sent += 1
        except Exception as exc:
            failed += 1
            log.debug("Broadcast failed for %s: %s", user_id, exc)
        await asyncio.sleep(0.04)
    db.log_event(update.effective_user.id, "broadcast", f"sent={sent}, failed={failed}")
    await status.edit_text(f"انتهى الإرسال.\n✅ وصل: {sent}\n❌ فشل: {failed}")

# ----------------------------- Callback Router ----------------------------

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update):
        return
    query = update.callback_query
    await safe_answer(update)
    action = query.data or ""
    user = update.effective_user

    if action == "home":
        await edit_or_reply(update, WELCOME, user_keyboard())
    elif action == "profile":
        row = db.get_user(user.id)
        username = f"@{row['username']}" if row and row["username"] else "غير محدد"
        joined = row["joined_at"][:10] if row else "—"
        await edit_or_reply(
            update,
            f"👤 *معلومات حسابك*\n\n🆔 ` {user.id} `\n"
            f"الاسم: {user.first_name}\nالمعرف: {username}\n"
            f"تاريخ التسجيل: {joined}",
            InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="home")]])
        )
    elif action == "stats":
        await edit_or_reply(
            update,
            f"📊 *إحصائيات النظام*\n\nحالة البوت: يعمل 🟢\n"
            f"وضع الصيانة: {'مفعل' if maintenance_enabled() else 'متوقف'}",
            InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="home")]])
        )
    elif action == "services":
        await edit_or_reply(
            update, SERVICES_TEXT,
            InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="home")]])
        )
    elif action == "help":
        await edit_or_reply(
            update, HELP_TEXT,
            InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="home")]])
        )
    elif action.startswith("admin_"):
        if not is_admin(user.id):
            await safe_answer(update, "هذا القسم للأدمن فقط.", True)
            return
        if action == "admin_stats":
            await edit_or_reply(
                update,
                f"📊 *إحصائيات الأدمن*\n\n"
                f"👥 إجمالي المستخدمين: {db.user_count()}\n"
                f"🚫 المحظورون: {db.blocked_count()}\n"
                f"🟢 غير المحظورين: {len(db.all_user_ids())}\n"
                f"🛠 الصيانة: {'مفعلة' if maintenance_enabled() else 'متوقفة'}",
                admin_keyboard()
            )
        elif action == "admin_users":
            await edit_or_reply(
                update,
                f"👥 إجمالي المستخدمين: *{db.user_count()}*\n"
                f"🚫 المحظورون: *{db.blocked_count()}*\n\n"
                "للحظر: `/block USER_ID`\nلفك الحظر: `/unblock USER_ID`",
                admin_keyboard()
            )
        elif action == "admin_maintenance":
            new_value = "0" if maintenance_enabled() else "1"
            db.set_setting("maintenance", new_value)
            db.log_event(user.id, "maintenance", new_value)
            await edit_or_reply(
                update,
                f"تم {'تفعيل' if new_value == '1' else 'إيقاف'} وضع الصيانة.",
                admin_keyboard()
            )
        elif action == "admin_activity":
            rows = db.recent_activity(10)
            if not rows:
                body = "لا توجد نشاطات مسجلة."
            else:
                body = "\n".join(
                    f"• `{r['user_id']}` — {r['event']} — {r['created_at'][:19]}"
                    for r in rows
                )
            await edit_or_reply(update, "📜 *آخر النشاطات*\n\n" + body, admin_keyboard())
        elif action == "admin_broadcast_help":
            await edit_or_reply(
                update,
                "📣 لإرسال إعلان:\n`/broadcast نص الإعلان`\n\n"
                "يرسل البوت الرسالة للمستخدمين غير المحظورين.",
                admin_keyboard()
            )
    else:
        await safe_answer(update, "خيار غير معروف.", True)

# --------------------------- Error and Lifecycle ---------------------------

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled exception while processing update", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "حدث خطأ غير متوقع. تم تسجيله، حاول مرة أخرى."
            )
        except Exception:
            pass

async def post_init(application: Application) -> None:
    log.info("Bot started. Database: %s", DB_PATH)
    for admin_id in ADMIN_IDS:
        try:
            await application.bot.send_message(
                chat_id=admin_id, text=f"🟢 {BOT_NAME} بدأ العمل."
            )
        except Exception:
            log.warning("Could not notify admin %s", admin_id)

def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN is missing. Copy .env.example to .env and set BOT_TOKEN."
        )
    if not ADMIN_IDS:
        raise SystemExit(
            "ADMIN_IDS is missing. Set at least one Telegram numeric user ID."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("block", block_command))
    application.add_handler(CommandHandler("unblock", unblock_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CallbackQueryHandler(callbacks))
    application.add_error_handler(error_handler)

    log.info("Polling started")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=False,
    )

if __name__ == "__main__":
    main()
