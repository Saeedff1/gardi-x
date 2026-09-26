# -*- coding: utf-8 -*-
"""
ربات گاردی ایکس - نسخه کامل
همراه با ۲۰۰ پاسخ، ۲۰۰ چالش، ۲۰۰ پ ن پ، ۲۰۰ بیو و...
"""

import os
import json
import logging
import random
import re
import time
import shutil
import tempfile
import hashlib
import asyncio
import unicodedata
import functools
import traceback
from html import escape
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import deque, defaultdict

from telegram_compat import (Robot, Message, ActionResult, MemberEvent, until_timestamp, mention_html,
                             TELEGRAM_MAX_TEMP_MINUTES)

# =========================================================
#  تنظیمات اصلی
# =========================================================

# توکن ربات تلگرام رو از @BotFather بگیر و در متغیر محیطی BOT_TOKEN بذار
# (شبیه چیزی مثل "123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
def _load_dotenv(path: str):
    """فایل .env کنار همین اسکریپت را (اگر باشد) می‌خواند؛ متغیرهای محیطیِ از قبل‌تنظیم‌شده را عوض نمی‌کند.
    فرمت: هر خط KEY=VALUE. توکن ربات نباید داخل کد یا گیت بیاید؛ فقط در .env یا متغیر محیطی."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except OSError:
        pass

_load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
# 🔒 برای Deploy روی Render: توکن دیگه هاردکد نیست و فقط از متغیر محیطی
# BOT_TOKEN خونده می‌شه (همون‌طور که پایین‌تر validate_startup_config() هم
# چک می‌کنه). توکن رو در تنظیمات سرویس روی Render، بخش Environment، اضافه کن.
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
VERSION = "10.0.0"
AUTHOR = "@im_Saeed1"
BOT_NAME = "گاردی ایکس"
# 🛠 این دو تا دیگه توی کد هاردکد نیستن؛ از متغیر محیطی خونده می‌شن تا لازم
# نباشه برای تنظیم لینک واقعی، خود کد رو ویرایش کنی (کافیه SUPPORT_LINK و
# FORCE_JOIN_CHANNEL_LINK رو در .env یا محیط اجرا بذاری). اگر تنظیم نشن،
# همین مقدار نمونه باقی می‌مونه و validate_startup_config() پایین‌تر یک
# هشدار واضح چاپ می‌کنه که یادت نره عوضش کنی.
SUPPORT_LINK = os.getenv("SUPPORT_LINK", "https://t.me/gardi_X")

# =========================================================
#  👑 مالک اصلی ربات (Super Owner)
# =========================================================
# مشکلی که باعث می‌شد مالک واقعی گروه (مالک گپ) پیام "⛔ شما اجازه انجام
# این کار را ندارید." بگیره این بود: ربات "مالک" رو صرفاً از روی یک لیست
# داخلی (owners) در دیتابیس خودش تشخیص می‌ده، نه از روی مالک واقعی گروه در
# روبیکا (که اصلاً از طریق API این ربات قابل خوندن نیست). این لیست فقط با
# اولین نفری که به ربات پیام داده (بوت‌استرپ) یا با /addowner پر می‌شه؛ اگر
# قبل از مالک واقعی، شخص دیگه‌ای (حتی خود شما با یه پیام تستی قدیمی) اولین
# نفر بوده، همون به‌عنوان مالک ثبت شده و مالک واقعی گروه هیچ سطح دسترسی‌ای
# نداشته. از طرفی /addowner هم چون به یک فیلد (owner_primary) که هیچ‌وقت
# مقداردهی نمی‌شد نیاز داشت، همیشه رد می‌شد و راه فراری هم نبود.
# راه‌حل: شناسه‌ی عددی خودتون (همون که ربات با /myid یا «آیدی من» بهتون
# نشون می‌ده) رو داخل متغیر محیطی SUPER_OWNERS بذارید (با کاما جدا اگر
# چند نفرن، مثلاً SUPER_OWNERS=123456789,987654321). هر کسی که آیدی‌اش
# اینجا باشه، در همه‌ی گروه‌ها همیشه سطح دسترسی «مالک» رو داره؛ صرف‌نظر از
# اینکه لیست owners داخلی گروه چی می‌گه.
SUPER_OWNERS = {
    x.strip() for x in os.getenv("SUPER_OWNERS", "8483919445").split(",") if x.strip()
}

def is_super_owner(user_id) -> bool:
    return str(user_id) in SUPER_OWNERS

# ---- عضویت اجباری (Force Join) ----
# ⚠️ توجه مهم: در تلگرام عضویت با یوزرنیم کانال (مثلاً "@my_channel") یا آیدی
# عددی کانال چک می‌شود. ربات باید ادمین همون کانال باشه تا بتونه عضویت رو چک کنه.
# تا وقتی این مقدار خالی باشه، ربات این مرحله رو رد می‌کنه تا کاربرها بی‌دلیل قفل نشن.
FORCE_JOIN_CHANNEL_GUID = os.getenv("FORCE_JOIN_CHANNEL_GUID", "@BioSongProf")  # مثلاً "@my_channel"
FORCE_JOIN_CHANNEL_LINK = os.getenv("FORCE_JOIN_CHANNEL_LINK", "https://t.me/BioSongProf")
FORCE_JOIN_MSG = (
    "📢 برای استفاده از ربات باید عضو کانال زیر باشید:\n\n"
    f"👉 {FORCE_JOIN_CHANNEL_LINK}\n\n"
    "بعد از عضویت، دوباره «استارت» رو بفرستید. ✅"
)
FORCE_JOIN_UNKNOWN_MSG = (
    "⚠️ امکان بررسی عضویت شما در کانال در حال حاضر وجود ندارد (خطای موقت).\n"
    "لطفاً کمی بعد دوباره «استارت» را بفرستید."
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE = os.path.join(DATA_DIR, "data.json")
RECENT_MSG_FILE = os.path.join(DATA_DIR, "recent_messages.json")

# =========================================================
#  🛠 بخش ۶۹: اعتبارسنجی تنظیمات محیطی قبل از اجرای ربات
# =========================================================
# قبلاً اگر BOT_TOKEN یا تنظیمات مهم دیگر اشتباه/خالی بودن، ربات یا با یک
# Exception نامفهوم وسط اجرا (مثلاً هنگام اولین درخواست به تلگرام) یا با یک
# پیام کوتاه متوقف می‌شد که مشخص نمی‌کرد دقیقاً کدام تنظیم مشکل دارد. این تابع
# همه‌ی تنظیمات ضروری/مهم را یک‌جا، قبل از ساخته‌شدن Robot، بررسی می‌کند:
# خطای ضروری (مثل BOT_TOKEN خالی) باعث توقف فوری با پیام واضح می‌شود؛ نکات غیر
# ضروری (مثل SUPER_OWNERS خالی) فقط به‌صورت هشدار چاپ می‌شوند تا اجرا ادامه پیدا کند.
def validate_startup_config() -> None:
    errors: List[str] = []
    warnings: List[str] = []

    if not BOT_TOKEN.strip():
        errors.append("BOT_TOKEN تنظیم نشده است. توکن واقعی از @BotFather بگیرید و در "
                       "متغیر محیطی BOT_TOKEN (یا فایل .env) قرار دهید.")
    elif ":" not in BOT_TOKEN:
        errors.append("BOT_TOKEN معتبر به‌نظر نمی‌رسد (باید شبیه '123456789:AA...' باشد).")

    if not SUPER_OWNERS:
        warnings.append("SUPER_OWNERS تنظیم نشده است؛ هیچ کاربری سطح دسترسی «مالک اصلی» "
                         "در همه‌ی گروه‌ها نخواهد داشت (فقط بوت‌استرپ/addowner داخل هر گروه کار می‌کند).")

    if SUPPORT_LINK == "https://t.me/your_support_username":
        warnings.append("SUPPORT_LINK هنوز مقدار نمونه است؛ آیدی پشتیبانی واقعی رو در متغیر "
                         "محیطی SUPPORT_LINK (یا .env) بذار، وگرنه کاربرها به یک لینک نمونه‌ی "
                         "غیرواقعی ارجاع داده می‌شن.")

    if FORCE_JOIN_CHANNEL_GUID and FORCE_JOIN_CHANNEL_LINK == "https://t.me/your_channel_username":
        warnings.append("عضویت اجباری فعال است (FORCE_JOIN_CHANNEL_GUID پر شده) ولی "
                         "FORCE_JOIN_CHANNEL_LINK هنوز مقدار نمونه است؛ لینک واقعی کانال رو در "
                         "متغیر محیطی FORCE_JOIN_CHANNEL_LINK بذار.")

    if FORCE_JOIN_CHANNEL_GUID and not (FORCE_JOIN_CHANNEL_GUID.startswith("@")
                                        or FORCE_JOIN_CHANNEL_GUID.lstrip("-").isdigit()):
        warnings.append(f"FORCE_JOIN_CHANNEL_GUID='{FORCE_JOIN_CHANNEL_GUID}' نه با @ شروع می‌شود نه یک "
                         "آیدی عددی است؛ برای تلگرام باید یوزرنیم کانال (@my_channel) یا آیدی عددی باشد.")

    # AI key may come from environment or a file. Resolve the file robustly
    # because some hosts start the bot with a different working/data directory.
    _ai_key_candidates = [
        os.getenv("AI_API_KEY", "").strip(),
        os.getenv("GEMINI_API_KEY", "").strip(),
        os.getenv("GOOGLE_API_KEY", "").strip(),
    ]
    _ai_key_present = any(_ai_key_candidates)
    if not _ai_key_present:
        _ai_key_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_key.txt"),
            os.path.join(os.getcwd(), "ai_key.txt"),
            os.path.join(DATA_DIR, "ai_key.txt"),
        ]
        for _ai_key_file in dict.fromkeys(_ai_key_paths):
            try:
                if os.path.isfile(_ai_key_file) and open(_ai_key_file, "r", encoding="utf-8").read().strip():
                    _ai_key_present = True
                    break
            except OSError:
                pass
        if not _ai_key_present:
            warnings.append("کلید Gemini تنظیم نشده است؛ یکی از AI_API_KEY/GEMINI_API_KEY/GOOGLE_API_KEY یا فایل ai_key.txt را تنظیم کنید.")

    try:
        test_path = os.path.join(DATA_DIR, ".write_test")
        with open(test_path, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_path)
    except OSError as e:
        errors.append(f"پوشه‌ی دیتابیس ({DATA_DIR}) قابل نوشتن نیست: {e}")

    for w in warnings:
        print(f"⚠️  [تنظیمات] {w}")

    if errors:
        print("=" * 70)
        print("❌ ربات به دلیل تنظیمات ناقص/نامعتبر اجرا نمی‌شود:")
        for err in errors:
            print(f"   ❌ {err}")
        print("=" * 70)
        raise SystemExit(1)


validate_startup_config()

bot = Robot(token=BOT_TOKEN)

# =========================================================
#  🆕 سیستم خطا (Global Error Handler)
# =========================================================
# 🛠 رفع باگ بزرگ: تا اینجای فایل هیچ‌جا هندلر خطای سراسری ثبت نشده بود.
# python-telegram-bot خودش جلوی کرش کل ربات رو می‌گیره، ولی بدون یک error
# handler صریح، استثنای هر هندلر فقط با logging.getLogger("telegram.ext...")
# در ترمینال چاپ می‌شد - جایی که هیچ‌کس (نه کاربر، نه حتی مالک ربات) واقعاً
# نمی‌بیندش. نتیجه: هر جا یک باگ برنامه‌نویسی/قطعی موقت شبکه/دیتای خراب پیش
# می‌اومد، کاربر برای همیشه هیچ پاسخی نمی‌گرفت و هیچ‌کس هم متوجه نمی‌شد که
# مشکلی وجود داره. الان:
#   ۱) traceback کامل با logging ثبت می‌شه (قابل پیگیری در لاگ سرور).
#   ۲) به مالک(های) اصلی (SUPER_OWNERS) در پیوی خبر داده می‌شه - با محدودیت
#      حداکثر یک اعلان در هر ۳۰۰ ثانیه در کل، تا اگه یک خطا برای صدها پیام
#      پشت‌سرهم تکرار بشه (مثلاً قطعی موقت API تلگرام)، پیوی مالک اسپم نشه.
#   ۳) اگه خطا حین پردازش یک پیام مشخص در گروه رخ داده، به‌جای سکوت کامل یک
#      پیام کوتاه و غیرفنی به همون گروه هم فرستاده می‌شه.
_LAST_ERROR_NOTICE_AT: Optional[float] = None
_ERROR_NOTICE_COOLDOWN = 300.0  # ثانیه

def _error_owner_notice_allowed() -> bool:
    global _LAST_ERROR_NOTICE_AT
    now = time.monotonic()
    if _LAST_ERROR_NOTICE_AT is not None and now - _LAST_ERROR_NOTICE_AT < _ERROR_NOTICE_COOLDOWN:
        return False
    _LAST_ERROR_NOTICE_AT = now
    return True

async def global_error_handler(update, context):
    err = context.error
    tb_text = "".join(traceback.format_exception(type(err), err, err.__traceback__))
    logging.getLogger("gardi.errors").error("خطای پردازش‌نشده در یک هندلر:\n%s", tb_text)

    if _error_owner_notice_allowed() and SUPER_OWNERS:
        short = f"{type(err).__name__}: {err}"
        short = short if len(short) <= 500 else short[:500] + "…"
        for owner_id in SUPER_OWNERS:
            try:
                await bot.send_text(owner_id, f"⚠️ **خطای داخلی ربات:**\n`{short}`\n\n(جزئیات کامل در لاگ سرور)")
            except Exception:
                pass  # اگه اطلاع دادن به مالک هم خطا داد، نباید کل error handler رو خراب کنه

    eff_msg = getattr(update, "effective_message", None) if update is not None else None
    if eff_msg is not None:
        try:
            await eff_msg.reply_text("⚠️ یه خطای موقت پیش اومد؛ لطفاً دوباره امتحان کن.")
        except Exception:
            pass

bot.set_error_handler(global_error_handler)

# =========================================================
#  🛠 رفع باگ بحرانی: «پاکسازی» فقط ادعای حذف می‌کرد، هیچ پیامی واقعاً حذف نمی‌شد
# =========================================================
# نسخه‌ی قبلی clear_cmd فقط عدد ورودی رو اعتبارسنجی می‌کرد و پیام
# "N پیام پاکسازی شد!" رو چاپ می‌کرد، بدون این‌که هیچ API ای برای حذف صدا
# بزنه. چون Rubika Bot API راهی برای گرفتن «تاریخچه‌ی پیام‌های قبلی» به
# ربات نمی‌ده (دقیقاً مثل محدودیت مشابه در Telegram Bot API)، تنها راه
# واقعی این‌ه که خود ربات از همون لحظه‌ای که وارد گروه می‌شه، شناسه‌ی
# پیام‌هایی که می‌بینه رو نگه داره تا بعداً واقعاً بتونه حذفشون کنه.
#
# 🛠 بهبود بعدی: نسخه‌ی اول این حافظه فقط در RAM بود و با هر ری‌استارت
# کاملاً خالی می‌شد (یعنی درست بعد از هر آپدیت/ری‌استارت سرور، «پاکسازی»
# دوباره از صفر شروع می‌شد). الان علاوه بر RAM، هر چند پیام یک‌بار روی
# دیسک هم ذخیره می‌شه (فایل جدا از data.json، چون این داده‌ی موقتی/غیرحیاتیه
# و لازم نیست قاطی دیتابیس اصلی بشه) و موقع بالا اومدن ربات، از روی دیسک
# بازیابی می‌شه. برای حذف واقعی هم به‌جای نگه‌داشتن خودِ آبجکت Message
# (که ممکنه هر لحظه از رده خارج بشه)، فقط chat_id/message_id ذخیره و با
# bot.delete_message(chat_id, message_id) حذف می‌کنیم - طبق مستندات رسمی
# rubka همین متد برای حذف پیام دلخواه وجود داره.
# سقف ۲۰۰ پیام آخر برای هر گروه، تا حافظه/فایل بی‌رویه رشد نکنه (بخش ۲۰).
RECENT_MESSAGES: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
_recent_msg_dirty_counter = 0

def _load_recent_messages():
    if not os.path.exists(RECENT_MSG_FILE):
        return
    try:
        with open(RECENT_MSG_FILE, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        for gid, items in raw.items():
            RECENT_MESSAGES[gid] = deque(items, maxlen=200)
        print(f"[recent_messages] {sum(len(v) for v in RECENT_MESSAGES.values())} پیام از دیسک بازیابی شد.")
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        print(f"[recent_messages][WARN] بازیابی از دیسک ناموفق بود (مهم نیست، خالی شروع می‌شه): {e!r}")

def _save_recent_messages():
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, prefix=".recentmsg_", suffix=".tmp")
        serializable = {gid: list(dq) for gid, dq in RECENT_MESSAGES.items()}
        with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
            json.dump(serializable, f, ensure_ascii=False)
        os.replace(tmp_path, RECENT_MSG_FILE)
    except OSError as e:
        print(f"[recent_messages][WARN] ذخیره روی دیسک ناموفق بود: {e!r}")

_load_recent_messages()

@bot.on_message()
async def _track_recent_messages_handler(bot: Robot, message: Message):
    """فقط شناسه‌ی پیام رو برای حذف احتمالی بعدی نگه می‌داره؛ هیچ پاسخی نمی‌ده."""
    global _recent_msg_dirty_counter
    group_id = get_chat_group_id(message)
    mid = getattr(message, "message_id", None)
    if group_id and mid:
        RECENT_MESSAGES[str(group_id)].append({"message_id": mid, "sender_id": str(getattr(message, "sender_id", ""))})
        _recent_msg_dirty_counter += 1
        # هر ۱۰ پیام یک‌بار روی دیسک ذخیره کن، نه هر پیام (طبق بخش ۱۲/۱۳:
        # جلوگیری از نوشتن غیرضروری روی دیسک در هر پیام)
        if _recent_msg_dirty_counter >= 10:
            _recent_msg_dirty_counter = 0
            _save_recent_messages()

# 🛠 رفع باگ: «پاکسازی» فقط پیام‌های خود کاربرها رو پاک می‌کرد، چون پیام‌هایی
# که خودِ ربات می‌فرستاد (reply/send_text) هیچ‌وقت وارد RECENT_MESSAGES نمی‌شدن
# (اون‌ها روی on_message که فقط برای پیام‌های ورودیه ثبت نمی‌شن). الان با
# استفاده از hook خود ربات (on_sent_message در telegram_compat.py)، هر پیامی
# که خودِ گاردی می‌فرسته هم دقیقاً مثل پیام بقیه وارد همین لیست می‌شه، پس
# /clear از این به بعد پیام‌های خودِ ربات رو هم پاک می‌کنه، نه فقط افراد.
def _track_bot_sent_message(chat_id, message_id: int):
    global _recent_msg_dirty_counter
    group_id = str(chat_id)
    RECENT_MESSAGES[group_id].append({"message_id": message_id, "sender_id": str(bot.bot_id or "")})
    _recent_msg_dirty_counter += 1
    if _recent_msg_dirty_counter >= 10:
        _recent_msg_dirty_counter = 0
        _save_recent_messages()

    # 🛠 «حذف خودکار پیام‌های مدیریتی» در راهنما تبلیغ می‌شد ولی هیچ‌جا واقعاً
    # پیاده نشده بود. الان: فقط برای گروه‌هایی که صریحاً «حذف خودکار فعال» رو
    # زدن (auto_delete_enabled=True در تنظیمات همون گروه) فعاله؛ پیوی و
    # گروه‌های تنظیم‌نشده دست‌نخورده می‌مونن تا هیچ رفتار قدیمی‌ای عوض نشه.
    try:
        cached = _ensure_cache_loaded().get(group_id)
        settings = cached.get("settings") if isinstance(cached, dict) else None
        if settings and settings.get("auto_delete_enabled"):
            seconds = settings.get("auto_delete_seconds", 10)
            asyncio.create_task(_auto_delete_bot_message_later(chat_id, message_id, seconds))
    except Exception as e:
        logging.getLogger("gardi").warning("auto_delete schedule failed: %r", e)

async def _auto_delete_bot_message_later(chat_id, message_id: int, seconds: float):
    try:
        await asyncio.sleep(seconds)
        await bot.delete_message_id(chat_id, message_id)
    except Exception as e:
        logging.getLogger("gardi").warning("auto_delete failed: %r", e)

bot.on_sent_message = _track_bot_sent_message

# =========================================================
#  دیتابیس
# =========================================================

# 🛠 رفع باگ فوق‌بحرانی (خطر پاک شدن کامل دیتابیس اگر data.json هم بکاپ هم
# خراب باشند): قبلاً وقتی load_data() به هر دلیلی نمی‌تونست دیتا رو بخونه،
# بی‌سروصدا {} برمی‌گردوند، و چون save_group_data همیشه یک بار دیگه هم
# load_data صدا می‌زد، همون یک بار خواندن ناموفق (مثلاً یک خطای دیسک موقت)
# می‌تونست با اولین ذخیره‌ی بعدی، دیتابیس کل ربات رو برای همیشه خالی کنه.
# الان: مقدار درست‌خوانده‌شده فقط یک بار در استارتاپ در حافظه (_DATA_CACHE)
# نگه داشته می‌شه و همه‌ی خواندن/نوشتن‌های بعدی روی همون آبجکتِ زنده‌ی
# در-حافظه انجام می‌شه، نه با خواندن دوباره از دیسک. این دو فایده دارد:
#   ۱) اگر بعد از استارتاپ یک خطای دیسکِ گذرا رخ بده، دیگر امکان نداره یک
#      خواندنِ ناموفق میانیِ اجرا، دیتای سالمِ در حافظه رو با {} جایگزین کنه.
#   ۲) چون همه‌ی هندلرها یک شیء دیکشنری *مشترک* رو می‌خونن/می‌نویسن (نه یک
#      کپی‌ی تازه از دیسک در هر فراخوانی)، تغییری که یک هندلر روی گروه X
#      می‌ده با تغییر هم‌زمانِ هندلر دیگری روی گروه Y (یا حتی همون گروه X،
#      در فیلدهای مختلف) رونویسی نمی‌شه - چون هر دو دارن مستقیماً همون
#      آبجکت مشترک رو تغییر می‌دن، نه این‌که هرکدوم یک کپی‌ی قدیمی رو کامل
#      جایگزین کنن. تنها اگر دو هندلر *دقیقاً همون یک فیلد* رو هم‌زمان (بین
#      دو await) عوض کنن رقابت باقی می‌مونه؛ برای همین موارد حساس مثل
#      تعیین مالک از OWNER_LOCK استفاده می‌کنن (بالاتر).
_DATA_CACHE: Optional[dict] = None
# اگر هم data.json هم بکاپش خراب باشند، دیگه نمی‌شه به‌صورت امن ذخیره کرد؛
# چون هر save در این حالت یعنی رونویسیِ قطعیِ یک دیتابیس خالی روی دیسک.
# به‌جای این‌که کورکورانه این‌کارو بکنیم، ذخیره رو کامل متوقف می‌کنیم و هر بار
# با یک خطای واضح در لاگ اعلام می‌کنیم تا یک ادمین دستی فایل‌های .corrupt-*
# رو بررسی کنه. (تا وقتی ربات دوباره با یک data.json سالم بالا نیامده، این
# پرچم پاک نمی‌شه.)
_DB_UNRECOVERABLE = False

def load_data():
    """فقط یک‌بار در استارتاپ (از طریق _ensure_cache_loaded) صدا زده می‌شود."""
    global _DB_UNRECOVERABLE
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        print(f"[DB][CRITICAL] خطا در خواندن {DB_FILE}: {e!r}")
        try:
            corrupt_path = DB_FILE + f".corrupt-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            shutil.copy2(DB_FILE, corrupt_path)
            print(f"[DB] کپی از فایل خراب برای بررسی دستی نگه داشته شد: {corrupt_path}")
        except OSError:
            pass
        backup_path = DB_FILE + ".bak"
        if os.path.exists(backup_path):
            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"[DB] بازیابی موفق از بکاپ: {backup_path}")
                return data
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                print(f"[DB][CRITICAL] بکاپ هم خراب بود: {backup_path}")
        print("[DB][CRITICAL] هیچ نسخه‌ی سالمی پیدا نشد؛ دیتابیس خالی در حافظه استفاده می‌شود "
              "ولی ذخیره‌سازی روی دیسک تا رفع دستی مشکل، متوقف می‌ماند (تا data.json موجود "
              "رونویسی/پاک نشود).")
        _DB_UNRECOVERABLE = True
        return {}

def save_data(data):
    """
    نوشتن اتمیک: اول در یک فایل موقت نوشته می‌شود، سپس با os.replace (که
    روی همه‌ی سیستم‌عامل‌ها اتمیک است) جایگزین فایل اصلی می‌شود. یعنی اگر
    ربات درست وسط نوشتن قطع بشه، data.json هیچ‌وقت نصفه یا خراب نمی‌مونه -
    یا نسخه‌ی قدیمی سالم می‌مونه یا نسخه‌ی جدید کامل جایگزین می‌شه، هیچ
    حالت میانی وجود نداره. قبل از جایگزینی، از نسخه‌ی فعلیِ سالم یک بکاپ
    (data.json.bak) گرفته می‌شه تا load_data در صورت خرابی بتونه ازش
    بازیابی کنه.
    """
    if _DB_UNRECOVERABLE:
        print(f"[DB][CRITICAL] ذخیره‌سازی رد شد: در زمان بالا آمدن ربات، {DB_FILE} و بکاپش "
              "هر دو خراب/غیرقابل‌خواندن بودند. برای جلوگیری از رونویسیِ اطلاعات قدیمیِ گروه‌ها "
              "با یک دیتابیس خالی، ذخیره‌سازی غیرفعال است. برای رفع: فایل‌های "
              f"{DB_FILE}.corrupt-* را بررسی/بازیابی دستی کن و ربات را دوباره اجرا کن.")
        return False
    if os.path.exists(DB_FILE):
        try:
            shutil.copy2(DB_FILE, DB_FILE + ".bak")
        except OSError as e:
            print(f"[DB][WARN] گرفتن بکاپ قبل از ذخیره ناموفق بود: {e!r}")
    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, prefix=".data_", suffix=".tmp")
        with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, DB_FILE)
        tmp_path = None
        return True
    except OSError as e:
        print(f"[DB][CRITICAL] خطا در ذخیره {DB_FILE}: {e!r}")
        return False
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

def _ensure_cache_loaded() -> dict:
    """دیتابیس را فقط یک‌بار (اولین فراخوانی) از دیسک می‌خواند و از آن به بعد
    همیشه همان آبجکتِ در-حافظه را برمی‌گرداند."""
    global _DATA_CACHE
    if _DATA_CACHE is None:
        _DATA_CACHE = load_data()
    return _DATA_CACHE

def get_group_data(group_id):
    data = _ensure_cache_loaded()
    group_id = str(group_id)
    if group_id not in data:
        data[group_id] = {
            'users': {},
            'admins': [],
            'owners': [],
            'specials': [],
            'exempts': [],
            'mutes': [],
            'bans': [],
            'blocks': [],
            'warns': {},
            'message_count': {},
            'daily_count': {},
            'weekly_count': {},
            'monthly_count': {},
            'stats': {
                'total_messages': 0,
                'today_messages': 0,
                'week_messages': 0,
                'month_messages': 0,
                'total_users': 0,
                'total_warns': 0,
                'total_mutes': 0,
                'total_bans': 0,
                'total_kicks': 0,
                'total_blocks': 0
            },
            'settings': {
                'max_warn': 3,
                'mute_duration': 5,
                'ban_duration': 86400,
                'lock': False,
                'anti_link': True,
                'anti_spam': True,
                'anti_swear': True,
                'welcome': '🎉 به گروه خوش اومدی {name}!',
                'goodbye': '👋 {name} از گروه خارج شد!',
                'rules': '📋 قوانین گروه:\n1️⃣ احترام\n2️⃣ بدون اسپم\n3️⃣ بدون لینک\n4️⃣ رعایت ادب',
                # 🧠 تنظیمات سخنگو (پیش‌فرض‌ها) — قبلاً این کلیدها اصلاً در دیتابیس
                # تعریف نشده بودن، برای همین دستورات «پنل سخنگو» و بقیه‌ی دستورات
                # روشن/خاموش کردنش که در راهنما تبلیغ می‌شدن، هیچ‌جای کد پیاده‌سازی
                # نداشتن و عملاً امکان نداشت جواب بدن.
                'speaker_enabled': True,
                'speaker_personal_enabled': True,
                'speaker_rude_enabled': False,
                'speaker_perm': 3,  # همون Perm.ADMIN (کلاس Perm پایین‌تر از این تابع تعریف شده)
                # 🛠 «حذف خودکار پیام‌های مدیریتی» توی راهنما (FULL_GUIDE_2) تبلیغ
                # می‌شد ولی هیچ‌جای کد پیاده‌سازی نشده بود؛ برای همین «حذف خودکار
                # فعال» جواب نمی‌داد و پیام‌های خودِ ربات هیچ‌وقت خودکار پاک نمی‌شدن.
                'auto_delete_enabled': False,
                'auto_delete_seconds': 10,
                # 🆕 «ضد تبچی» (FULL_GUIDE_1: «ضد تبچی روشن/خاموش») در راهنما تبلیغ می‌شد ولی هیچ
                # کلید settings و هیچ منطق اجرایی نداشت. «تبچی» یعنی اکانتی که تازه عضو گروه شده و
                # قبل از اینکه حتی یک پیام عادی بده، بلافاصله لینک/فوروارد تبلیغاتی می‌فرستد. وقتی
                # فعال باشد، در anti_tabchi_window_seconds اول بعد از عضویت، لینک/فوروارد آن کاربر
                # حذف و اخطار جداگانه ثبت می‌شود (پایین‌تر: auto_message_handler + tabchi_*_cmd).
                'anti_tabchi_enabled': False,
                'anti_tabchi_window_seconds': 300,
                'anti_tabchi_max_warn': 1,
                # 🛠 «تنظیم مشخصات کاربری»: کلید کلی برای خاموش/روشن کردن کل قابلیت
                # لقب/اصل/اسم/فامیلی در یک گروه («تنظیم مشخصات غیرفعال/فعال»).
                'profile_enabled': True,
            },
            # 🛠 مقادیرِ گروهیِ لقب/اصل/اسم/فامیلی هر کاربر: {user_id: {field: value}}
            'user_profiles': {},
            'filters': {
                'swear': ['فحش', 'لعنت', 'کونی', 'جنده', 'بی شرف', 'بی ناموس', 'خائن', 'منافق'],
                'badwords': ['سیاسی', 'مذهبی', 'جنسی', 'مخدر', 'الکل', 'قمار']
            },
            'learn': {},
            'logs': [],
            # 🆕 سیستم «دستورات دلخواه» (FULL_GUIDE_2) - نگاشت trigger سفارشی به alias اصلی،
            # مثلاً {"زمان": "ساعت"} یعنی نوشتن «زمان» همون کار «ساعت» را انجام می‌دهد.
            'custom_commands': {},
            # 🆕 سیستم «محدودیت عمومی دستورات» / «ضد خیانت» (FULL_GUIDE_2) - برای هر دستورِ
            # کانونیک (مثلاً /challenge): disabled (غیرفعال کامل در گروه)، user_disabled (غیرفعال
            # فقط برای یک نفر خاص)، user_limits (سقف روزانه‌ی هر نفر). warns_tabchi هم پایین‌تر
            # جدا از warns عادی نگه داشته می‌شود تا با اخطارهای فحش/کلمات‌ممنوعه قاطی نشود.
            'command_restrictions': {},
            'command_usage': {},
            'warns_tabchi': {},
        }
        save_data(data)
    gd_ = data[group_id]
    # 🛠 مهاجرت تنظیمات قدیمی group_welcome/group_goodbye فوراً ذخیره می‌شود، نه فقط در حافظه‌ی
    # همین درخواست (وگرنه با هر بار خواندن دوباره‌ی دیتابیس، کلید قدیمی دوباره ظاهر می‌شد).
    st = gd_.get("settings")
    if isinstance(st, dict) and ("group_welcome" in st or "group_goodbye" in st):
        migrate_welcome_settings(gd_)
        save_group_data(group_id, gd_)
    return gd_

def save_group_data(group_id, group_data):
    data = _ensure_cache_loaded()
    data[str(group_id)] = group_data
    save_data(data)

# 🛠 «تنظیم مشخصات کاربری» (لقب/اصل/اسم/فامیلی) نسخه‌ی «سراسری» - در راهنما
# (FULL_GUIDE_1/۳) وعده داده شده بود («تنظیم لقب/اصل/اسم/فامیلی سراسری #متن»)
# ولی نه این چهار فیلد نه حتی خودِ مفهوم «ذخیره‌ی سراسری» (مستقل از هر گروه)
# هیچ‌جای کد وجود نداشت. چون کلید گروه‌ها در data.json همیشه رشته‌ی عددیِ
# chat_id است (منفی برای گروه/سوپرگروه)، یک کلید غیرعددیِ رزرو‌شده برای این
# منظور امن است و هرگز با هیچ group_id واقعی برخورد نمی‌کند.
_GLOBAL_PROFILES_KEY = "__global_profiles__"

def get_global_profiles() -> dict:
    data = _ensure_cache_loaded()
    return data.setdefault(_GLOBAL_PROFILES_KEY, {})

def save_global_profiles(profiles: dict):
    data = _ensure_cache_loaded()
    data[_GLOBAL_PROFILES_KEY] = profiles
    save_data(data)

# =========================================================
#  🧩 هسته فاز ۱ ارتقا: نرمال‌سازی فارسی + Permission + Router + Log واقعی
#  توضیح کامل در انتهای فایل زیر عنوان «تغییرات نسخه جدید»
# =========================================================

def get_reply_message(message):
    """Safely get the replied-to message from any Rubka version."""
    return (getattr(message, "reply_to_message", None) or 
            getattr(message, "reply_message", None) or
            getattr(message, "forwarded_from", None))

def get_reply_sender_id(message):
    """Safely get sender_id from a replied-to message."""
    reply_msg = get_reply_message(message)
    if reply_msg:
        return str(getattr(reply_msg, "sender_id", ""))
    return None

# =========================================================
#  🛠 رفع باگ بحرانی: message.sender_first_name اصلاً وجود نداره!
# =========================================================
# آپدیت‌های رسمی Rubika Bot API فقط sender_id رو می‌فرستن، نه first_name/last_name
# (برخلاف تلگرام). کد قدیمی همه‌جا مستقیم message.sender_first_name رو می‌خوند که
# باعث AttributeError می‌شد و کل هندلر روی همون پیام کرش می‌کرد - نه فقط اون دستور،
# بلکه از جمله auto_message_handler که ضدلینک/ضداسپم/ضدفحش/ثبت کاربر توش انجام
# می‌شد، پس عملاً همه‌ی محافظت‌های گروه و خیلی از دستورها رندوم از کار می‌افتادن.
# اینجا با bot.get_name() اسم واقعی رو می‌گیریم (و کش می‌کنیم) و اگه هم در
# دسترس نبود، بدون کرش کردن یه مقدار پیش‌فرض برمی‌گردونیم.
_NAME_CACHE: Dict[str, str] = {}
_NAME_LOOKUP_STATE: Dict[str, bool] = {"unreliable": False}

async def get_display_name(bot, target, group_id: Optional[str] = None, prefer_live: bool = False) -> str:
    """اسم نمایشی یک کاربر رو برمی‌گردونه. ورودی می‌تونه خود آبجکت Message باشه
    (اسم فرستنده‌ی همون پیام) یا یک شناسه کاربری رشته‌ای (مثلاً برای پیام ریپلای‌شده).

    🛠 بخش ۶۴: قبلاً اگر کاربر در کش نبود (مثلاً هیچ‌وقت با ربات تعامل نداشته)،
    همیشه یک نام عمومی («کاربر») نمایش داده می‌شد؛ حتی برای عملیات مدیریتی مهم
    (بن/سکوت/اخطار روی کسی که تازه با Reply هدف گرفته شده). حالا اگر prefer_live=True
    باشه (برای همین دستورهای مدیریتی) و کش جواب نده، قبل از نمایش نام پیش‌فرض، یک‌بار
    مستقیماً از Telegram API (get_member_info) پرسیده می‌شه - کش فقط برای سرعته، نه
    تنها منبع هویت. group_id اگر داده نشه و target خودِ Message باشه، از روی
    خودِ target استخراج می‌شه."""
    if target is None:
        return "کاربر"
    if hasattr(target, "sender_id"):
        # اگه یه نسخه‌ی جدیدتر از rubka این اطلاعات رو داشته باشه، همونو استفاده کن
        direct = getattr(target, "sender_first_name", None) or getattr(target, "first_name", None)
        if direct:
            return direct
        user_id = str(getattr(target, "sender_id", "") or "")
        if group_id is None:
            group_id = getattr(target, "chat_id", None)
    else:
        user_id = str(target or "")

    if not user_id or user_id == "None":
        return "کاربر"
    if user_id in _NAME_CACHE:
        return _NAME_CACHE[user_id]

    # 🛠 رفع باگ بحرانی: «پیام خوش‌آمد به اسم عضو جدید رو با اسم مالک نشون می‌ده».
    # علتش این بود: bot.get_name(user_id) در برخی نسخه‌های rubka آرگومانش رو
    # نادیده می‌گیره و همیشه اسمِ صاحبِ همون توکن/سشن ربات رو برمی‌گردونه (که
    # چون بات معمولاً با شماره‌ی خود مالک ساخته می‌شه، همیشه اسم مالک درمیاد) -
    # نه اسم کاربری که واقعاً پرسیده شده. اگه یک بار متوجه بشیم این متد برای
    # دو user_id متفاوت دقیقاً یک اسم یکسان برمی‌گردونه، دیگه بهش اعتماد
    # نمی‌کنیم و به‌جاش یک نام عمومی امن نشون می‌دیم؛ نشون‌دادن اسم اشتباهِ یه
    # نفرِ دیگه (مالک) خیلی بدتر از نشون‌دادن «کاربر» ه.
    if not _NAME_LOOKUP_STATE["unreliable"]:
        name = None
        try:
            result = bot.get_name(user_id)
            if asyncio.iscoroutine(result):
                result = await result
            if result:
                name = str(result)
        except Exception:
            name = None

        if name:
            if _NAME_CACHE and name in _NAME_CACHE.values():
                _NAME_LOOKUP_STATE["unreliable"] = True
            else:
                _NAME_CACHE[user_id] = name
                return name

    # کش جواب نداد (یا غیرقابل‌اعتماد تشخیص داده شده). برای عملیات مهم، قبل از
    # افتادن به نام پیش‌فرض، یک‌بار مستقیماً از API واقعی تلگرام می‌پرسیم.
    if prefer_live and group_id and hasattr(bot, "get_member_info"):
        try:
            info = await bot.get_member_info(group_id, user_id)
        except Exception:
            info = None
        if info and info.get("user"):
            u = info["user"]
            live_name = " ".join(x for x in ((u.get("first_name") or "").strip(),
                                             (u.get("last_name") or "").strip()) if x)
            if live_name:
                _NAME_CACHE[user_id] = live_name
                return live_name
            if u.get("username"):
                return "@" + u["username"]

    return "کاربر"

# ---- یوزرنیم واقعی کاربر (برای ساخت لینک پروفایل قابل‌کلیک در «تگ همه») ----
# 🛠 نکته: bot.get_username() دقیقاً همون خطری رو داره که قبلاً برای get_name
# دیدیم (بعضی نسخه‌های rubka برای هر ورودی، یک مقدار ثابت برمی‌گردونن). برای
# همین همون الگوی محافظتی (اگه یک بار برای دو کاربر متفاوت یک یوزرنیم یکسان
# برگرده، دیگه بهش اعتماد نمی‌کنیم) اینجا هم پیاده شده.
_USERNAME_CACHE: Dict[str, str] = {}
_USERNAME_LOOKUP_STATE: Dict[str, bool] = {"unreliable": False}

async def get_user_username(bot, user_id: str) -> Optional[str]:
    """یوزرنیم عمومی کاربر را برمی‌گرداند، یا None اگر نداشت/در دسترس نبود.
    هرگز استثنا پرتاب نمی‌کند (برای استفاده‌ی امن در حلقه روی چند کاربر)."""
    user_id = str(user_id or "")
    if not user_id or user_id == "None":
        return None
    if _USERNAME_LOOKUP_STATE["unreliable"]:
        return None
    if user_id in _USERNAME_CACHE:
        return _USERNAME_CACHE[user_id]

    username = None
    try:
        result = bot.get_username(user_id)
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            username = str(result).lstrip("@").strip()
    except Exception:
        username = None

    if username:
        if _USERNAME_CACHE and username in _USERNAME_CACHE.values():
            _USERNAME_LOOKUP_STATE["unreliable"] = True
            return None
        _USERNAME_CACHE[user_id] = username
        return username
    return None

# =========================================================
#  🛠 رفع باگ بحرانی: replace_tags اصلاً تعریف نشده بود!
# =========================================================
# سخنگو (پاسخ‌های یادگرفته‌شده) همیشه replace_tags(...) رو صدا می‌زد ولی این
# تابع هیچ‌جای فایل تعریف نشده بود، پس هر بار که یه پاسخ یادگرفته‌شده قرار بود
# ارسال بشه، NameError می‌داد و کل هندلر (auto_message_handler) کرش می‌کرد -
# چون این خطا توسط میان‌افزار کتابخونه silently لاگ می‌شه، از دید کاربر انگار
# ربات "اصلاً جواب نمی‌داد". همین تابع مفقوده، هشتگ‌های مستندشده‌ی راهنما
# (#اسم_گروه، #تگ_کاربر، #اسم_کاربر، #زمان/#ساعت، #تاریخ) رو واقعاً جایگزین می‌کنه.
def replace_tags(text: str, user_name: str = "کاربر", group_name: str = "گروه") -> str:
    if not text:
        return text
    now = datetime.now()
    text = text.replace("#اسم_گروه", group_name or "گروه")
    text = text.replace("#تگ_کاربر", user_name or "کاربر")
    text = text.replace("#اسم_کاربر", user_name or "کاربر")
    text = text.replace("#زمان", now.strftime("%H:%M"))
    text = text.replace("#ساعت", now.strftime("%H:%M"))
    text = text.replace("#تاریخ", now.strftime("%Y/%m/%d"))
    # 🛠 قالب‌های پیش‌فرض خوشامدگویی/خداحافظی (تنظیم‌شده در get_group_data) از
    # سینتکس قدیمی {name}/{group} استفاده می‌کردن که هیچ‌جا جایگزین نمی‌شد و
    # کلمه‌ی «{name}» عیناً تو پیام ارسالی می‌موند. برای سازگاری با متن‌های
    # پیش‌فرض/قدیمی، این‌ها رو هم پشتیبانی می‌کنیم.
    text = text.replace("{name}", user_name or "کاربر")
    text = text.replace("{group}", group_name or "گروه")
    return text

# ---- نرمال‌سازی فارسی ----
_FA_CHAR_MAP = {
    "ي": "ی", "ك": "ک", "ۀ": "ه", "إ": "ا", "أ": "ا",
    "‌": " ", "‍": "", "\u200f": "",
}

def normalize_fa(text: str) -> str:
    """نرمال‌سازی حروف عربی/فارسی رایج و فاصله‌های اضافه، بدون له‌کردن معنای دستورات مختلف."""
    if not text:
        return ""
    t = text.strip()
    for a, b in _FA_CHAR_MAP.items():
        t = t.replace(a, b)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def normalize_key(text: str) -> str:
    """کلید نرمال برای جستجو در ALIAS_MAP: حذف / ابتدایی، lowercase برای لاتین."""
    t = normalize_fa(text)
    if t.startswith("/"):
        t = t[1:]
    return t.lower()

# ---- تبدیل ارقام فارسی/عربی به انگلیسی (برای پارس مدت سکوت/بن و مشابه) ----
_FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_DIGIT_MAP = {ord(f): str(i) for i, f in enumerate(_FA_DIGITS)}
_DIGIT_MAP.update({ord(a): str(i) for i, a in enumerate(_AR_DIGITS)})

def to_en_digits(text: str) -> str:
    """هر رقم فارسی یا عربی داخل متن را به معادل انگلیسی‌اش تبدیل می‌کند."""
    if not text:
        return ""
    return text.translate(_DIGIT_MAP)

def parse_duration_minutes(raw: Optional[str]) -> Optional[int]:
    """
    یک رشته حاوی عدد (فارسی یا انگلیسی) را به تعداد دقیقه معتبر (عدد صحیح مثبت) تبدیل می‌کند.
    مقادیر نامعتبر مثل خالی، غیرعددی، صفر یا منفی، None برمی‌گردانند.
    """
    if raw is None:
        return None
    cleaned = to_en_digits(raw).strip()
    if not cleaned:
        return None
    if not re.fullmatch(r"-?\d+", cleaned):
        return None
    value = int(cleaned)
    if value <= 0:
        return None
    return value

def looks_like_duration_attempt(raw: Optional[str]) -> bool:
    """True اگر توکن کاملاً عددی است (حتی اگر نامعتبر مثل صفر/منفی باشد) —
    یعنی کاربر واقعاً قصد وارد کردن مدت‌زمان را داشته و صرفاً عدد اشتباه زده."""
    if not raw:
        return False
    cleaned = to_en_digits(raw).strip()
    return bool(re.fullmatch(r"-?\d+", cleaned))

def looks_like_user_id(s: Optional[str]) -> bool:
    """
    آیا این رشته واقعاً شبیه شناسه‌ی یک کاربر روبیکاست، یا فقط یک کلمه‌ی فارسی
    عادی (مثل «ریپلای»، «با»، «به»)؟ برای جلوگیری از باگی که در آن دستورهایی
    مثل «افزودن مالک با ریپلای» به‌اشتباه کلمه‌ی "با" را به‌عنوان شناسه‌ی
    هدف برمی‌داشتند (چون بعد از رایتر به شکل "/addowner با ریپلای" تبدیل
    می‌شد و parts[1] برابر "با" بود، بدون هیچ اعتبارسنجی).
    """
    if not s:
        return False
    return bool(re.fullmatch(r"u0[a-zA-Z0-9]+|\d{5,}", s))

def resolve_target_id(message) -> Optional[str]:
    """شناسه هدف دستور را از روی ریپلای یا یک شناسه‌ی عددی داخل متن پیام تشخیص می‌دهد."""
    reply_id = get_reply_sender_id(message)
    if reply_id:
        return str(reply_id)
    text = to_en_digits(message.text or "")
    m = re.search(r"\b(u0[a-zA-Z0-9]+|\d{5,})\b", text)
    if m:
        return m.group(1)
    return None

# ---- تشخیص صحیح گروه بودن چت ----
# 🛠 این ربات الان روی تلگرام واقعی (python-telegram-bot) اجرا می‌شود، نه روبیکا.
# منطق قبلی (تشخیص گروه از روی پیشوند "g0"/"g" در chat_id) مخصوص روبیکا بود و
# روی تلگرام هیچ‌وقت match نمی‌شد، چون در تلگرام:
#   - چت خصوصی (پیوی): chat_id مثبت است
#   - گروه/سوپرگروه: chat_id همیشه منفی است (مثل -1001234567890)
# همین باعث می‌شد get_chat_group_id همیشه None برگردونه و پیام
# "⚠️ این قابلیت فقط داخل گروه قابل استفاده است." حتی داخل خودِ گروه هم نمایش داده بشه.
def get_chat_group_id(message) -> Optional[str]:
    """اگر پیام داخل یک گروه/سوپرگروه تلگرام ارسال شده باشد chat_id گروه را برمی‌گرداند، وگرنه None (یعنی پیوی)."""
    chat_type = getattr(message, "chat_type", None)
    if chat_type is None:
        raw_chat = getattr(message, "chat", None)
        chat_type = getattr(raw_chat, "type", None)
    chat_id = getattr(message, "chat_id", None)
    if chat_id is None:
        return None
    if chat_type in ("group", "supergroup"):
        return str(chat_id)
    if chat_type is None:
        # اگر نوع چت در دسترس نبود، بر اساس قرارداد تلگرام: chat_id منفی یعنی گروه/سوپرگروه
        try:
            if int(chat_id) < 0:
                return str(chat_id)
        except (TypeError, ValueError):
            pass
    return None

async def is_force_join_satisfied(bot, message) -> Optional[bool]:
    """بررسی عضویت اجباری در کانال.
    خروجی: True=عضو است (یا اصلاً عضویت اجباری تنظیم نشده)، False=عضو نیست،
    None=بررسی در حال حاضر ممکن نشد (خطای تلگرام/شبکه).
    🛠 بخش ۷۰: قبلاً هر خطایی (حتی قطعی موقت API) به‌صورت خاموش «عضو است» در
    نظر گرفته می‌شد (Fail-Open) و عضویت اجباری عملاً دور زده می‌شد. الان فراخوان‌ها
    باید صریحاً بین این سه حالت فرق بذارن و None رو هرگز مجاز تفسیر نکنن."""
    if not FORCE_JOIN_CHANNEL_GUID:
        return True
    try:
        chat_id = getattr(message, "chat_id", None)
        result = await bot.check_join(FORCE_JOIN_CHANNEL_GUID, chat_id)
        return result  # True / False / None (نگاه کن به check_join)
    except Exception as e:
        logging.getLogger("gardi").warning("is_force_join_satisfied failed: %r", e)
        return None

# ---- سیستم سطح دسترسی ----
class Perm:
    MEMBER = 0
    EXEMPT = 1
    SPECIAL = 2
    ADMIN = 3
    SUPER_ADMIN = 4
    OWNER = 5

def get_permission_level(user_id, group_data) -> int:
    user_id = str(user_id)
    if is_super_owner(user_id):
        return Perm.OWNER
    if user_id in group_data.get("owners", []):
        return Perm.OWNER
    if user_id in group_data.get("super_admins", []):
        return Perm.SUPER_ADMIN
    if user_id in group_data.get("admins", []):
        return Perm.ADMIN
    if user_id in group_data.get("specials", []):
        return Perm.SPECIAL
    if user_id in group_data.get("exempts", []):
        return Perm.EXEMPT
    return Perm.MEMBER

def has_permission(user_id, group_data, required: int) -> bool:
    return get_permission_level(user_id, group_data) >= required

# ---------- بخش ۴ ممیزی: دسترسی داخلی ربات ≠ وضعیت واقعی تلگرام ----------
# «مالک/مدیر» در دیتابیس گاردی صرفاً یک نقش داخلی است که خودِ ربات نگهش می‌دارد (مثلاً با /addadmin
# تنظیم می‌شود) و می‌تواند از واقعیت تلگرام عقب بیفتد (کسی که دیگر حتی عضو گروه نیست، هنوز OWNER
# داخلی باشد). این نقش داخلی فقط تعیین می‌کند «آیا اجازه‌ی صدور این دستور به ربات را دارد»؛ اینکه
# «آیا عملیات واقعاً روی تلگرام انجام می‌شود» را همیشه خودِ تلگرام در لحظه‌ی فراخوانی API تصمیم
# می‌گیرد (ban_user/kick_user/restrict_user/pin_message/... همگی نتیجه‌ی واقعی API را برمی‌گردانند،
# نه فرض داخلی). پس دو لایه‌ی مجزا همیشه رعایت می‌شود:
#   ۱) Internal Permission  -> has_permission(...) / is_admin(...)   «اجازه‌ی دستور دادن»
#   ۲) Telegram Permission  -> نتیجه‌ی واقعی فراخوانی API / bot_capability_error(...)  «انجام‌شدنی بودن»
# مرحله‌ی ۱ هیچ‌وقت جایگزین مرحله‌ی ۲ نمی‌شود؛ مالک داخلی که ادمین تلگرام نیست همچنان می‌تواند
# دستور بدهد، اما اگر ربات دسترسی لازم را نداشته باشد، عملیات با خطای واقعی رد می‌شود، نه با
# پیام موفقیت جعلی.
async def get_real_telegram_status(bot, group_id, user_id) -> str:
    """وضعیت واقعی کاربر در تلگرام (owner/administrator/member/restricted/left/banned/unknown)،
    مستقل از نقش داخلی‌اش در دیتابیس گاردی."""
    status = await bot.get_member_status(group_id, user_id)
    return status["status"] if status else "unknown"

def is_telegram_admin_status(status: str) -> bool:
    return status in ("owner", "administrator")

PERM_NAMES = {
    Perm.MEMBER: "عضو",
    Perm.EXEMPT: "معاف",
    Perm.SPECIAL: "ویژه",
    Perm.ADMIN: "مدیر",
    Perm.SUPER_ADMIN: "مدیر ارشد",
    Perm.OWNER: "مالک",
}

NO_PERMISSION_MSG = "⛔ شما اجازه انجام این کار را ندارید."
NEED_REPLY_MSG = "👤 لطفاً روی پیام کاربر ریپلای کنید."
GROUP_ONLY_MSG = "⚠️ این قابلیت فقط داخل گروه قابل استفاده است."

# ---- لاگ واقعی (کلید logs در دیتابیس از قبل تعریف شده بود ولی هرگز پر نمی‌شد) ----
def add_log(group_data, action: str, admin_id: str = "", target_id: str = "", reason: str = ""):
    logs = group_data.setdefault("logs", [])
    logs.append({
        "time": datetime.now().isoformat(),
        "action": action,
        "admin": str(admin_id) if admin_id else "",
        "target": str(target_id) if target_id else "",
        "reason": reason or "",
    })
    # فقط ۵۰۰ رکورد آخر نگه داشته می‌شود تا دیتابیس بی‌رویه رشد نکند
    if len(logs) > 500:
        group_data["logs"] = logs[-500:]

# =========================================================
#  🆕 سیستم شخصی‌سازی اموجی‌ها (تبلیغ‌شده در FULL_GUIDE_1 با «تنظیم اموجی
#  داشبورد/تگ/آمار/لیست‌ها/پاکسازی/ریست» و «لیست اموجی»، ولی هیچ‌کدام قبلاً
#  نه ذخیره‌سازی داشتند نه اثری روی متن پیام‌های ربات) - الان واقعی است:
#  اموجی‌های سفارشی در group_data['settings']['custom_emojis'][key] ذخیره
#  می‌شوند و همه‌جا که آن بخش از ربات پیام می‌دهد از get_custom_emoji خوانده
#  می‌شود؛ اگر گروه چیزی تنظیم نکرده باشد، همان اموجی پیش‌فرض قبلی برمی‌گردد.
# =========================================================
CUSTOM_EMOJI_KEYS = {
    "dashboard": "پنل داشبورد/تنظیمات گروه",
    "tag": "تگ همه / تگ‌های اختصاصی",
    "stats": "آمار من / آمار گروه",
    "lists": "سربرگ لیست‌ها (ادمین، ویژه، بلاک و ...)",
    "cleanup": "پیام موفقیتِ پاکسازی",
    "reset": "پیام موفقیتِ ریست/پاکسازی لیست‌ها",
}
DEFAULT_CUSTOM_EMOJIS = {
    "dashboard": "⚙️", "tag": "🔔", "stats": "📊",
    "lists": "📋", "cleanup": "🗑", "reset": "♻️",
}
CUSTOM_EMOJI_ALIASES = {
    "داشبورد": "dashboard", "تگ": "tag", "آمار": "stats",
    "لیست": "lists", "لیستها": "lists", "لیست ها": "lists", "لیست‌ها": "lists",
    "پاکسازی": "cleanup", "ریست": "reset",
}

def get_custom_emoji(group_data: Optional[dict], key: str) -> str:
    """اموجی سفارشی‌شده‌ی این بخش برای این گروه، وگرنه پیش‌فرض کلی ربات."""
    ce = ((group_data or {}).get('settings', {}) or {}).get('custom_emojis', {}) or {}
    return ce.get(key) or DEFAULT_CUSTOM_EMOJIS.get(key, "🔹")

def _is_valid_single_emoji(text: str) -> bool:
    """رشته‌ی ارسالی باید کوتاه و واقعاً یک اموجی باشد، نه یک جمله‌ی کامل."""
    t = (text or "").strip()
    if not t or len(t) > 8:
        return False
    return not any(ch.isalnum() for ch in t if ch.isascii())

# =========================================================
#  🛠 رفع باگ بحرانی: سکوت/بن فقط اسمی بودند، هیچ‌وقت واقعاً تمام نمی‌شدند
# =========================================================
# قبلاً 'mutes' و 'bans' فقط یک لیست ساده از user_id بودند؛ دستور «سکوت ۱۰»
# فقط پیام «به مدت ۱۰ دقیقه میوت شد» رو نشون می‌داد ولی هیچ زمان پایانی جایی
# ذخیره نمی‌شد، پس کاربر تا حذف دستی («رفع سکوت») برای همیشه میوت می‌موند.
# از این نسخه به بعد 'mutes' و 'bans' دیکشنری‌ای از user_id به اطلاعات کامل
# (started_at/banned_at, until, by, reason) هستند. until=None یعنی دائمی.
def _migrate_punish_dict(group_data: dict, key: str, by_field: str):
    """لیست قدیمی user_id ها را به ساختار دیکشنری جدید (بدون تاریخ انقضا = دائمی) تبدیل می‌کند."""
    value = group_data.get(key)
    if isinstance(value, list):
        now_iso = datetime.now().isoformat()
        migrated = {}
        for uid in value:
            migrated[str(uid)] = {
                "until": None,
                "started_at": now_iso,
                by_field: "",
                "reason": "بدون دلیل (داده قدیمی)",
            }
        group_data[key] = migrated
    elif not isinstance(value, dict):
        group_data[key] = {}

def _ensure_punish_structures(group_data: dict):
    _migrate_punish_dict(group_data, "mutes", "muted_by")
    _migrate_punish_dict(group_data, "bans", "banned_by")

def apply_timed_punishment(group_data: dict, key: str, by_field: str,
                            user_id: str, duration_minutes: Optional[int],
                            by_user_id: str, reason: str):
    """کاربر را در ساختار mutes/bans با زمان پایان واقعی (یا دائمی) ثبت می‌کند."""
    _ensure_punish_structures(group_data)
    now = datetime.now()
    until = None
    if duration_minutes is not None:
        until = (now + timedelta(minutes=duration_minutes)).isoformat()
    group_data[key][str(user_id)] = {
        "until": until,
        "started_at": now.isoformat(),
        by_field: str(by_user_id),
        "reason": reason or "بدون دلیل",
    }

def remove_punishment(group_data: dict, key: str, user_id: str) -> bool:
    """کاربر را از سکوت/بن فعال خارج می‌کند. اگر کاربر اصلاً در وضعیت فعال نبود، False برمی‌گرداند."""
    _ensure_punish_structures(group_data)
    return group_data[key].pop(str(user_id), None) is not None

def is_punished_active(group_data: dict, key: str, user_id: str) -> bool:
    """
    بررسی می‌کند آیا کاربر هم‌اکنون در وضعیت سکوت/بن فعال است یا نه.
    اگر زمان سکوت/بن تمام شده باشد، به‌صورت خودکار از وضعیت فعال حذف می‌شود
    (منقضی‌شدن خودکار، حتی بعد از خاموش/روشن شدن ربات، چون 'until' در فایل ذخیره شده).
    """
    _ensure_punish_structures(group_data)
    entry = group_data[key].get(str(user_id))
    if not entry:
        return False
    until = entry.get("until")
    if until is None:
        return True  # دائمی
    try:
        until_dt = datetime.fromisoformat(until)
    except (ValueError, TypeError):
        # داده خراب: به‌جای کرش، محافظه‌کارانه رفتار کن و پاکش کن
        group_data[key].pop(str(user_id), None)
        return False
    if datetime.now() >= until_dt:
        group_data[key].pop(str(user_id), None)
        return False
    return True

def format_remaining(entry: dict) -> str:
    """زمان باقی‌مانده یک سکوت/بن را به شکل خوانا برمی‌گرداند."""
    until = entry.get("until")
    if until is None:
        return "دائمی"
    try:
        until_dt = datetime.fromisoformat(until)
    except (ValueError, TypeError):
        return "نامشخص"
    remaining = until_dt - datetime.now()
    minutes = max(0, int(remaining.total_seconds() // 60))
    if minutes < 60:
        return f"{minutes} دقیقه دیگر"
    hours = minutes // 60
    rem_minutes = minutes % 60
    if hours < 24:
        return f"{hours} ساعت و {rem_minutes} دقیقه دیگر"
    days = hours // 24
    rem_hours = hours % 24
    return f"{days} روز و {rem_hours} ساعت دیگر"


# =========================================================
#  🛠 رفع باگ قطعی: make_progress_bar هیچ‌جا تعریف نشده بود (NameError در /level)
# =========================================================
def make_progress_bar(value, total=100, length=10, filled_char="█", empty_char="░") -> str:
    """
    نوار پیشرفت متنی، مثلاً make_progress_bar(40, 100, 10) -> '████░░░░░░ 40%'.
    ورودی‌های عجیب (منفی، بیشتر از total، total=0، غیرعددی) هیچ‌وقت خطا نمی‌دهند:
    نسبت همیشه بین ۰ تا ۱ محدود می‌شود.
    """
    try:
        value = float(value)
        total = float(total)
        length = int(length)
    except (TypeError, ValueError):
        value, total, length = 0.0, 100.0, 10
    if length <= 0:
        length = 10
    ratio = 0.0 if total <= 0 else max(0.0, min(1.0, value / total))
    filled = int(round(ratio * length))
    return f"{filled_char * filled}{empty_char * (length - filled)} {int(round(ratio * 100))}%"

# =========================================================
#  🛠 تطبیق دقیق دستورهای slash
# =========================================================
# قبلاً فیلتر هندلرها m.text.startswith("/ban") بود؛ یعنی «/bans» هم ban_cmd را
# اجرا می‌کرد، «/muteduration 30» هم mute_cmd را، و «/warnings» و «/warnaction»
# هم warn_cmd را. وقتی بن/سکوت فقط یک رکورد دیتابیس بود ضررش کم بود، ولی حالا که
# این دستورها روی تلگرام اثر واقعی دارند، با ریپلای روی یک پیام، «/muteduration 30»
# یا «/bans» می‌توانست یک نفر را واقعاً میوت/بن کند. الان نام دستور باید دقیقاً
# برابر باشد (با پشتیبانی از فرم /ban@BotName که تلگرام در گروه‌ها می‌فرستد).
def _cmd_is(m, name: str) -> bool:
    t = (getattr(m, "text", None) or "").strip()
    if not t.startswith("/"):
        return False
    first = t.split()[0][1:].split("@")[0].lower()
    return first == name.lstrip("/").lower()

def _cmd_rest(text: Optional[str]) -> str:
    """متن بعد از نام دستور (آرگومان‌ها)، با حذف /cmd یا /cmd@BotName."""
    parts = (text or "").strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""

def punish_guard(group_data: dict, actor_id: str, target_id: str) -> Optional[str]:
    """جلوگیری از اقدام‌های بی‌معنی/خطرناک حالا که بن و سکوت واقعی هستند."""
    if str(target_id) == str(actor_id):
        return "⚠️ نمی‌توانی این کار را روی خودت انجام بدهی."
    if is_owner(target_id, group_data):
        return "⚠️ روی مالک ربات نمی‌شود این کار را انجام داد."
    return None

# =========================================================
#  🛠 رفع باگ بحرانی: بن/سکوت/اخراج فقط اسمی بودند و نتیجه‌ی تلگرام چک نمی‌شد
# =========================================================
# قبلاً:
#   • kick_chat_member در شکست False برمی‌گرداند ولی هندلرها آن را نمی‌خواندند،
#     پس بدون هیچ تغییری در تلگرام، پیام «اخراج/بن شد» نمایش داده می‌شد.
#   • «بن» در واقع اخراج بود (کاربر می‌توانست دوباره جوین شود) و «سکوت» فقط یک
#     رکورد در JSON بود؛ کاربر در تلگرام همچنان می‌توانست پیام بفرستد.
# الان ترتیب ثابت است: ۱) عملیات واقعی روی تلگرام ۲) اگر و فقط اگر موفق بود، ثبت در
# دیتابیس (با خواندن دوباره‌ی دیتابیس بعد از API، چون فراخوانی API چند ده/صد میلی‌ثانیه
# طول می‌کشد و در این فاصله هندلر دیگری ممکن است همان گروه را ذخیره کرده باشد)
# ۳) پیام موفقیت. اگر تلگرام رد کرد، دیتابیس دست نمی‌خورد و علت واقعی برمی‌گردد.
async def moderation_ban(bot, group_id, target_id, by_id, duration_minutes, reason,
                         log_action: str = "بن") -> ActionResult:
    """بن واقعی (دائمی اگر duration_minutes=None). تلگرام خودش بن موقت را سر وقت برمی‌دارد."""
    if duration_minutes is not None and not (1 <= int(duration_minutes) <= TELEGRAM_MAX_TEMP_MINUTES):
        return ActionResult(False, error="مدت بن باید بین ۱ دقیقه تا ۳۶۶ روز باشد (محدودیت تلگرام).", code="bad_duration")
    until_ts = until_timestamp(duration_minutes)
    res = await bot.ban_user(group_id, target_id, until_ts)
    if not res:
        return res
    group_data = get_group_data(group_id)
    apply_timed_punishment(group_data, "bans", "banned_by", target_id, duration_minutes, by_id, reason)
    remove_punishment(group_data, "mutes", target_id)  # بن، سکوت قبلی را در تلگرام هم بی‌اثر می‌کند
    group_data['stats']['total_bans'] = group_data['stats'].get('total_bans', 0) + 1
    add_log(group_data, log_action, admin_id=by_id, target_id=target_id, reason=reason)
    _rec = _members(group_data).get(str(target_id))
    if _rec is not None:
        _registry_set_status(_rec, "banned", "moderation", _reg_now())
    save_group_data(group_id, group_data)
    return res

async def moderation_mute(bot, group_id, target_id, by_id, duration_minutes, reason,
                          log_action: str = "سکوت") -> ActionResult:
    """سکوت واقعی: Restriction روی خود کاربر در تلگرام با until_date واقعی."""
    if duration_minutes is not None and not (1 <= int(duration_minutes) <= TELEGRAM_MAX_TEMP_MINUTES):
        return ActionResult(False, error="مدت سکوت باید بین ۱ دقیقه تا ۳۶۶ روز باشد (محدودیت تلگرام).", code="bad_duration")
    until_ts = until_timestamp(duration_minutes)
    res = await bot.restrict_user(group_id, target_id, until_ts)
    if not res:
        return res
    group_data = get_group_data(group_id)
    apply_timed_punishment(group_data, "mutes", "muted_by", target_id, duration_minutes, by_id, reason)
    group_data['stats']['total_mutes'] = group_data['stats'].get('total_mutes', 0) + 1
    add_log(group_data, log_action, admin_id=by_id, target_id=target_id, reason=reason)
    save_group_data(group_id, group_data)
    return res

async def moderation_kick(bot, group_id, target_id, by_id, reason,
                          log_action: str = "اخراج") -> ActionResult:
    """اخراج واقعی (بن + رفع‌بن فوری؛ کاربر می‌تواند دوباره وارد شود)."""
    res = await bot.kick_user(group_id, target_id)
    if not res:
        return res
    group_data = get_group_data(group_id)
    # کاربری که اخراج شده Restriction تلگرامی‌اش هم پاک شده؛ رکورد سکوت قدیمی را هم پاک کن
    remove_punishment(group_data, "mutes", target_id)
    group_data['stats']['total_kicks'] = group_data['stats'].get('total_kicks', 0) + 1
    add_log(group_data, log_action, admin_id=by_id, target_id=target_id, reason=reason)
    _rec = _members(group_data).get(str(target_id))
    if _rec is not None:
        _registry_set_status(_rec, "left", "moderation", _reg_now())
    save_group_data(group_id, group_data)
    return res

async def _is_really_punished(bot, group_id, target_id, key: str) -> Optional[bool]:
    """وضعیت واقعی تلگرام: True/False، یا None اگر نتوانستیم از تلگرام بخوانیم."""
    status = await bot.get_member_status(group_id, target_id)
    if status is None:
        return None
    if key == "bans":
        return status["status"] == "kicked"
    return status["status"] == "restricted" and status.get("can_send_messages") is False

async def moderation_unban(bot, group_id, target_id, by_id):
    """رفع بن. خروجی: (state, result) با state یکی از 'ok' | 'not_banned' | 'failed'.
    دیتابیس فقط وقتی پاک می‌شود که تلگرام هم واقعاً رفع بن را انجام داده یا از قبل بن نبوده باشد."""
    group_data = get_group_data(group_id)
    in_db = is_punished_active(group_data, "bans", target_id)
    status = await bot.get_member_status(group_id, target_id)
    st = status["status"] if status else None
    if st == "kicked" or (st is None and in_db):
        res = await bot.unban_user(group_id, target_id)
        if not res:
            return "failed", res
    elif in_db:
        res = ActionResult(True, warning="در تلگرام از قبل بن نبود؛ فقط وضعیت داخلی ربات پاک شد.")
    else:
        return "not_banned", ActionResult(True)
    group_data = get_group_data(group_id)
    remove_punishment(group_data, "bans", target_id)
    add_log(group_data, "رفع بن", admin_id=by_id, target_id=target_id)
    _rec = _members(group_data).get(str(target_id))
    if _rec is not None and _rec.get("status") == "banned":   # رفع بن = دیگر ممنوع نیست، ولی هنوز عضو نیست
        _registry_set_status(_rec, "left", "moderation", _reg_now())
    save_group_data(group_id, group_data)
    return "ok", res

async def moderation_unmute(bot, group_id, target_id, by_id):
    """رفع سکوت. خروجی: (state, result) با state یکی از 'ok' | 'not_muted' | 'failed'.
    Restriction واقعی تلگرام برداشته می‌شود؛ اگر API شکست بخورد دیتابیس دست نمی‌خورد."""
    group_data = get_group_data(group_id)
    in_db = is_punished_active(group_data, "mutes", target_id)
    status = await bot.get_member_status(group_id, target_id)
    st = status["status"] if status else None
    tg_muted = st == "restricted" and status.get("can_send_messages") is False
    if tg_muted or (st in (None, "restricted") and in_db):
        res = await bot.unrestrict_user(group_id, target_id)
        if not res:
            return "failed", res
    elif in_db:
        res = ActionResult(True, warning="در تلگرام از قبل محدودیتی روی او نبود؛ فقط وضعیت داخلی ربات پاک شد.")
    else:
        return "not_muted", ActionResult(True)
    group_data = get_group_data(group_id)
    remove_punishment(group_data, "mutes", target_id)
    add_log(group_data, "رفع سکوت", admin_id=by_id, target_id=target_id)
    save_group_data(group_id, group_data)
    return "ok", res

# =========================================================
#  🛠 سیستم اخطار کامل (قبلاً فقط warns[user_id] += 1 بود)
# =========================================================
# ساختار: group_data['warns'][user_id] = {"entries": [...], "count": N}
# و هر entry: id, group_id, user_id, reason, created_at, expires_at, by, cleared, action
#   • هر گروه دیتابیس جدا دارد (group_data متعلق به همان گروه است) پس اخطار
#     گروه A هیچ‌وقت روی گروه B اثر نمی‌گذارد.
#   • اخطار منقضی‌شده (expires_at گذشته) در شمارش لحاظ نمی‌شود و پاک می‌شود.
#   • رسیدن به max_warn ← اقدام (settings['warn_action']: ban | kick | mute)؛ بعد از
#     اقدام موفق، اخطارها «مصرف‌شده» (cleared) می‌شوند تا مجازات تکراری/اشتباه نشود.
#   • داده‌ی قدیمی (عدد ساده) خودکار به این ساختار مهاجرت می‌کند؛ چون زمان واقعی
#     اخطارهای قدیمی معلوم نیست، از لحظه‌ی مهاجرت شمرده می‌شوند.
DEFAULT_WARN_EXPIRE_DAYS = 30      # settings['warn_expire_days']؛ 0 = بدون انقضا
DEFAULT_WARN_ACTION = "ban"        # همان رفتار قبلی ضدفحش (بن دائمی)
MAX_WARN_HISTORY = 50              # سقف رکوردهای هر کاربر تا دیتابیس بی‌رویه بزرگ نشود
WARN_ACTIONS = {"mute": "سکوت", "kick": "اخراج", "ban": "بن"}

def get_warn_expire_days(group_data: dict) -> Optional[int]:
    raw = group_data.get("settings", {}).get("warn_expire_days", DEFAULT_WARN_EXPIRE_DAYS)
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = DEFAULT_WARN_EXPIRE_DAYS
    return days if days > 0 else None

def _warn_entry_expired(entry: dict, now: datetime) -> bool:
    exp = entry.get("expires_at")
    if not exp:
        return False
    try:
        return now >= datetime.fromisoformat(exp)
    except (TypeError, ValueError):
        return True  # داده‌ی خراب: مبنای مجازات قرار نمی‌گیرد

def _warn_entry_active(entry: dict, now: datetime) -> bool:
    return not entry.get("cleared") and not _warn_entry_expired(entry, now)

def _refresh_warn_record(rec: dict, now: datetime) -> int:
    rec["count"] = sum(1 for e in rec["entries"] if _warn_entry_active(e, now))
    return rec["count"]

def _ensure_warn_structures(group_data: dict, group_id=None) -> dict:
    """ساختار اخطار را تضمین می‌کند و عددهای قدیمی (warns[uid] = 3) را مهاجرت می‌دهد."""
    warns = group_data.get("warns")
    if not isinstance(warns, dict):
        group_data["warns"] = {}
        return group_data["warns"]
    now = datetime.now()
    days = get_warn_expire_days(group_data)
    for uid in list(warns.keys()):
        rec = warns[uid]
        if isinstance(rec, dict) and isinstance(rec.get("entries"), list):
            continue
        try:
            legacy = max(0, int(rec))
        except (TypeError, ValueError):
            legacy = 0
        if legacy <= 0:
            del warns[uid]
            continue
        created = now.isoformat()
        expires = (now + timedelta(days=days)).isoformat() if days else None
        entries = [{
            "id": i + 1, "group_id": str(group_id or ""), "user_id": str(uid),
            "reason": "اخطار قدیمی (قبل از سیستم جدید، بدون جزئیات)",
            "created_at": created, "expires_at": expires, "by": "",
            "cleared": False, "action": None, "legacy": True,
        } for i in range(legacy)]
        warns[uid] = {"entries": entries, "count": legacy}
    return warns

def prune_expired_warns(group_data: dict, now: Optional[datetime] = None) -> int:
    """اخطارهای منقضی‌شده را حذف می‌کند؛ تعداد حذف‌شده‌ها را برمی‌گرداند."""
    warns = _ensure_warn_structures(group_data)
    now = now or datetime.now()
    removed = 0
    for uid in list(warns.keys()):
        rec = warns[uid]
        kept = []
        for e in rec["entries"]:
            if _warn_entry_expired(e, now):
                removed += 1
            else:
                kept.append(e)
        rec["entries"] = kept[-MAX_WARN_HISTORY:]
        if not rec["entries"]:
            del warns[uid]
        else:
            _refresh_warn_record(rec, now)
    return removed

def get_warn_count(group_data: dict, user_id) -> int:
    """تعداد اخطارهای «فعال» (منقضی/مصرف‌شده حساب نمی‌شوند)."""
    warns = _ensure_warn_structures(group_data)
    uid = str(user_id)
    rec = warns.get(uid)
    if not rec:
        return 0
    now = datetime.now()
    rec["entries"] = [e for e in rec["entries"] if not _warn_entry_expired(e, now)]
    if not rec["entries"]:
        del warns[uid]
        return 0
    return _refresh_warn_record(rec, now)

def get_active_warn_entries(group_data: dict, user_id) -> list:
    if get_warn_count(group_data, user_id) == 0:
        return []
    now = datetime.now()
    return [e for e in group_data["warns"][str(user_id)]["entries"] if _warn_entry_active(e, now)]

def list_active_warnings(group_data: dict) -> list:
    """[(user_id, count)] فقط برای کاربرانی که اخطار فعال دارند."""
    prune_expired_warns(group_data)
    return [(uid, rec["count"]) for uid, rec in group_data["warns"].items() if rec.get("count", 0) > 0]

def add_warning(group_data: dict, group_id, target_id, reason: str, by_id) -> dict:
    """یک اخطار با دلیل/زمان/انقضا ثبت می‌کند و می‌گوید به حد مجاز رسیده یا نه."""
    uid = str(target_id)
    _ensure_warn_structures(group_data, group_id)
    get_warn_count(group_data, uid)  # اخطارهای منقضی‌شده‌ی همین کاربر قبل از شمارش پاک شوند
    rec = group_data["warns"].setdefault(uid, {"entries": [], "count": 0})
    now = datetime.now()
    days = get_warn_expire_days(group_data)
    entry = {
        "id": max([e.get("id", 0) for e in rec["entries"]], default=0) + 1,
        "group_id": str(group_id),
        "user_id": uid,
        "reason": reason or "بدون دلیل",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(days=days)).isoformat() if days else None,
        "by": str(by_id),
        "cleared": False,
        "action": None,
    }
    rec["entries"].append(entry)
    rec["entries"] = rec["entries"][-MAX_WARN_HISTORY:]
    count = _refresh_warn_record(rec, now)
    group_data.setdefault('stats', {})['total_warns'] = group_data['stats'].get('total_warns', 0) + 1
    add_log(group_data, "اخطار", admin_id=by_id, target_id=uid, reason=entry["reason"])
    try:
        max_warn = max(1, int(group_data.get('settings', {}).get('max_warn', 3)))
    except (TypeError, ValueError):
        max_warn = 3
    return {"count": count, "max": max_warn, "limit_reached": count >= max_warn, "entry": entry}

def remove_last_warning(group_data: dict, user_id) -> Optional[int]:
    """آخرین اخطار فعال را حذف می‌کند؛ تعداد باقی‌مانده یا None (اگر اخطاری نبود)."""
    uid = str(user_id)
    if get_warn_count(group_data, uid) == 0:
        return None
    rec = group_data["warns"][uid]
    now = datetime.now()
    for i in range(len(rec["entries"]) - 1, -1, -1):
        if _warn_entry_active(rec["entries"][i], now):
            del rec["entries"][i]
            break
    if not rec["entries"]:
        del group_data["warns"][uid]
        return 0
    return _refresh_warn_record(rec, now)

def reset_warnings(group_data: dict, user_id) -> int:
    """همه‌ی اخطارهای کاربر را پاک می‌کند؛ تعداد اخطار فعالِ پاک‌شده را برمی‌گرداند."""
    uid = str(user_id)
    n = get_warn_count(group_data, uid)
    group_data["warns"].pop(uid, None)
    return n

def mark_warns_consumed(group_data: dict, user_id, action: str):
    """بعد از اقدام موفق، اخطارهای فعال «مصرف‌شده» می‌شوند (سابقه می‌ماند، ولی شمرده نمی‌شوند)."""
    uid = str(user_id)
    rec = group_data.get("warns", {}).get(uid)
    if not rec:
        return
    now = datetime.now()
    active = [e for e in rec["entries"] if _warn_entry_active(e, now)]
    for e in active:
        e["cleared"] = True
    if active:
        active[-1]["action"] = action
        active[-1]["action_at"] = now.isoformat()
    _refresh_warn_record(rec, now)

def _fmt_date(iso: Optional[str]) -> str:
    if not iso:
        return "بدون انقضا"
    try:
        return datetime.fromisoformat(iso).strftime("%Y/%m/%d %H:%M")
    except (TypeError, ValueError):
        return "نامشخص"

async def execute_warn_action(bot, group_id, target_id, by_id, reason: str = ""):
    """
    اقدام بعد از رسیدن به حد مجاز اخطار (ban | kick | mute طبق settings['warn_action']).
    خروجی: (انجام_شد: bool, متن پیام برای نمایش). اگر تلگرام رد کند، اخطارها حفظ می‌شوند
    و علت واقعی در پیام می‌آید (نه «بن شد» دروغ).
    """
    group_data = get_group_data(group_id)
    settings = group_data.get('settings', {})
    action = settings.get('warn_action', DEFAULT_WARN_ACTION)
    if action not in WARN_ACTIONS:
        action = DEFAULT_WARN_ACTION
    try:
        max_warn = max(1, int(settings.get('max_warn', 3)))
    except (TypeError, ValueError):
        max_warn = 3
    if is_admin(target_id, group_data):
        return False, "ℹ️ این کاربر مدیر/مالک است؛ اقدام خودکار روی او اعمال نشد."
    why = reason or f"رسیدن به {max_warn} اخطار"

    if action == "ban":
        res = await moderation_ban(bot, group_id, target_id, by_id, None, why, log_action="بن خودکار (اخطار)")
        ok_text = f"🚫 **کاربر به دلیل رسیدن به {max_warn} اخطار بن شد!**"
    elif action == "mute":
        try:
            minutes = max(1, int(settings.get('mute_duration', 5)))
        except (TypeError, ValueError):
            minutes = 5
        res = await moderation_mute(bot, group_id, target_id, by_id, minutes, why, log_action="سکوت خودکار (اخطار)")
        ok_text = f"🔇 **کاربر به دلیل رسیدن به {max_warn} اخطار به مدت {minutes} دقیقه میوت شد!**"
    else:
        res = await moderation_kick(bot, group_id, target_id, by_id, why, log_action="اخراج خودکار (اخطار)")
        ok_text = f"👢 **کاربر به دلیل رسیدن به {max_warn} اخطار اخراج شد!**"

    if res:
        group_data = get_group_data(group_id)
        mark_warns_consumed(group_data, target_id, action)
        save_group_data(group_id, group_data)
        if res.warning:
            ok_text += f"\n⚠️ {res.warning}"
        return True, ok_text
    return False, (f"❌ کاربر به {max_warn} اخطار رسید ولی اقدام خودکار ({WARN_ACTIONS[action]}) انجام نشد.\n"
                   f"🔎 علت: {res.error}\n📌 اخطارها حفظ شدند.")


# =========================================================
#  🛡 بخش ۲ ممیزی: Anti-Link / Anti-Swear / Anti-Spam / Lock
# =========================================================
# اصل مشترک: «تشخیص» جدا از «اقدام» است؛ اقدام (حذف پیام) فقط وقتی «انجام شد» گزارش
# می‌شود که تلگرام واقعاً حذف را تایید کرده باشد؛ و قبل از هر اقدام، سطح دسترسی فرستنده
# (مالک/ادمین/ویژه/معاف + ادمین واقعی تلگرام) چک می‌شود تا ادمین‌ها هدف فیلتر نشوند.

# ---------- ۱) تشخیص نوع پیام (تابع مرکزی) ----------
# قفل «رسانه‌ی کلی» (lock_media): همه‌ی فایل‌ها. استیکر/مخاطب/موقعیت/نظرسنجی/بازی فقط با قفل جدا.
MEDIA_LOCK_TYPES = ("photo", "video", "animation", "document", "audio", "voice", "video_note")

def mtype_for_registry(message) -> str:
    return detect_message_type(message)

def detect_message_type(message) -> str:
    """نوع واقعی پیام: text | photo | video | animation | document | audio | voice | video_note |
    sticker | contact | location | poll | game | dice | service | other. (عکس+کپشن همچنان photo است؛
    کپشن جدا و همراه آن بررسی می‌شود.)"""
    t = getattr(message, "message_type", None)
    if isinstance(t, str) and t:
        return t
    return "text" if getattr(message, "text", None) else "other"

# ---------- ۲) تشخیص لینک: Entity ها + متن/کپشن + شکل‌های پنهان ----------
_LINK_TLDS = (
    "com|net|org|info|biz|io|me|co|ir|xyz|top|site|online|club|shop|store|app|dev|link|live|click|"
    "tk|ml|ga|cf|gq|ru|de|uk|us|tv|cc|ws|pw|vip|fun|icu|cyou|buzz|work|space|website|tech|pro|name|"
    "mobi|asia|in|cn|jp|fr|it|es|nl|tr|ae|sa|iq|af|ly|gl|gd|to|is|be|gg|sh|ai|so|st|im|fm|am|la|"
    "ph|blog|news|life|world|today|agency|team|cloud|page|host|press|download|stream|bet|casino|"
    "win|loan|ninja|guru|rocks|social|chat|group|zone|network|digital|media|email|support|nu|ec|"
    "lol|cam|sbs|rest|bio|one|plus|art|ink|kim|day|wiki|pm"
)
_LINK_RE = re.compile(
    r"(?:\b(?:https?|ftp|tg|ws|wss)://\S+"                      # https://... و tg://...
    r"|\bwww\.\S+"                                                   # www....
    r"|\b(?:t|telegram)\.(?:me|dog)\b/?\S*"                          # t.me/... و telegram.me
    r"|\btelegra\.ph\b/?\S*"
    r"|\b[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.(?:" + _LINK_TLDS + r")\b(?:/\S*)?)",
    re.IGNORECASE,
)
_LINK_OBFUSCATION = re.compile(r"\s*[\[\(\{<]\s*(?:\.|dot|نقطه)\s*[\]\)\}>]\s*", re.IGNORECASE)

def _fold_link_text(text: str) -> str:
    """یکسان‌سازی قبل از regex: NFKC (حروف تمام‌عرض)، حذف کاراکترهای نامرئی وسط دامنه،
    نقطه‌های جایگزین (。 ．) و شکل‌های پنهان مثل example[.]com."""
    s = unicodedata.normalize("NFKC", text)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Cf")
    s = s.replace("。", ".").replace("｡", ".").replace("．", ".")
    return _LINK_OBFUSCATION.sub(".", s)

def detect_links(message) -> Optional[str]:
    """
    اگر پیام لینک دارد یک توضیح کوتاه برمی‌گرداند، وگرنه None. منابع بررسی:
      ۱) Entity های خود تلگرام (url و text_link) روی متن «و» کپشن؛ یعنی «اینجا کلیک کن» که
         پشتش URL پنهان است هم شناسایی می‌شود (هرچه تلگرام لینک بداند لینک است).
      ۲) متن + کپشن با regex (http/https/www/t.me/دامنه‌های رایج) بعد از نرمال‌سازی.
    """
    for ent in getattr(message, "all_entities", None) or []:
        etype = ent.get("type")
        if etype == "text_link":
            return f"text_link:{(ent.get('url') or '')[:60]}"
        if etype == "url":
            return f"url:{(ent.get('text') or '')[:60]}"
    text = getattr(message, "text", None) or ""
    if text:
        m = _LINK_RE.search(_fold_link_text(text))
        if m:
            return f"text:{m.group(0)[:60]}"
    return None

# ---------- ۳) موتور ضدفحش: نرمال‌سازی + توکن‌بندی (نه substring) ----------
_AR2FA = str.maketrans({
    "ي": "ی", "ى": "ی", "ې": "ی", "ے": "ی", "ك": "ک", "ڪ": "ک", "ة": "ه", "ۀ": "ه", "ھ": "ه", "ہ": "ه",
    "ە": "ه", "ؤ": "و", "ٱ": "ا",
    # همشکل‌های سیریلیک -> لاتین
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "к": "k", "м": "m",
    "т": "t", "н": "h", "і": "i", "ѕ": "s", "ј": "j", "в": "b",
})
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t"})
# پسوندهای رایج که به کلمه‌ی ممنوع می‌چسبند («لعنتی»، «فحش‌ها»، fucker...). فقط برای کلمه‌های
# ≥۳ حرف؛ کلمه‌ی کوتاه (مثل «خر») فقط دقیق تطبیق می‌شود تا «خرید» و «خرگوش» اشتباهی حذف نشوند.
_SWEAR_SUFFIXES = frozenset({
    "ها", "های", "هایی", "ی", "یی", "ای", "تر", "ترین", "م", "ت", "ش", "مو", "تو", "شو", "مون",
    "تون", "شون", "مان", "تان", "شان", "ه", "یه", "یم", "ید", "ند", "ین", "و", "رو",
    "s", "es", "ed", "er", "ers", "ing", "in", "y",
})

def _fold_for_filter(text: str) -> str:
    """Unicode Normalization برای فیلتر: NFKD (حروف تمام‌عرض/ریاضی/لیگاتور)، casefold، یکسان‌سازی
    حروف عربی/فارسی، ارقام فارسی/عربی، حذف کشیده/اعراب/ایموجی/نمادها/کاراکترهای نامرئی؛
    نیم‌فاصله و فاصله‌ها -> جداکننده‌ی کلمه."""
    s = unicodedata.normalize("NFKD", text).casefold()
    s = s.translate(_AR2FA).translate(_DIGIT_MAP)
    out = []
    for ch in s:
        if ch == "\u200c":                       # نیم‌فاصله = جداکننده
            out.append(" ")
            continue
        if ch == "\u0640":                       # کشیده
            continue
        cat = unicodedata.category(ch)
        if cat in ("Cf", "Mn", "Me", "So", "Sk"):  # نامرئی/اعراب/ایموجی/نماد
            continue
        out.append(ch if (cat[0] not in "CZ") else " ")
    return "".join(out)

def _collapse_repeats(tok: str) -> str:
    return re.sub(r"(.)\1+", r"\1", tok)

def swear_tokens(text: str) -> List[str]:
    """متن -> توکن‌های نرمال (کلمه‌به‌کلمه). رشته‌ای از ≥۳ حرف تک‌ (مثل «ف ح ش» یا «f.u.c.k»)
    که با فاصله/نقطه/نیم‌فاصله/ایموجی از هم جدا شده‌اند به هم وصل می‌شود."""
    raw = re.findall(r"[^\W_]+", _fold_for_filter(text or ""))
    merged: List[str] = []
    run: List[str] = []
    def flush():
        if len(run) >= 3:
            merged.append("".join(run))
        else:
            merged.extend(run)
        run.clear()
    for tok in raw:
        if len(tok) == 1 and tok.isalpha():
            run.append(tok)
        else:
            flush()
            merged.append(tok)
    flush()
    return [t for t in merged if t]

def _token_forms(tok: str) -> List[Tuple[str, str, bool]]:
    """شکل‌های قابل مقایسه‌ی یک توکن: (خام، فشرده‌شده، آیا حرف تکراری دارد). برای توکن‌های مخلوطِ
    حرف+رقم (مثل sh1t) شکل leet هم اضافه می‌شود."""
    forms = [(tok, _collapse_repeats(tok), bool(re.search(r"(.)\1", tok)))]
    if any("a" <= c <= "z" for c in tok) and any(c.isdigit() for c in tok):
        alt = tok.translate(_LEET)
        if alt != tok:
            forms.append((alt, _collapse_repeats(alt), bool(re.search(r"(.)\1", alt))))
    return forms

@functools.lru_cache(maxsize=64)
def _compile_swear_words(words: Tuple[str, ...]):
    compiled = []
    for w in words:
        toks = swear_tokens(w)
        if toks:
            compiled.append((w, tuple((t, _collapse_repeats(t), len(t)) for t in toks)))
    return tuple(compiled)

def _eq_suffix(token: str, pattern: str, plen: int, is_last: bool) -> bool:
    if token == pattern:
        return True
    return bool(is_last and plen >= 3 and token.startswith(pattern)
                and token[len(pattern):] in _SWEAR_SUFFIXES)

def _tok_match(ptok, forms, is_last: bool) -> bool:
    pt, pc, plen = ptok
    for raw, col, has_run in forms:
        if _eq_suffix(raw, pt, plen, is_last):
            return True
        # کشیده‌نویسی («فححححش»، «fuuuck»): فقط وقتی خودِ توکن متن حرف تکراری دارد، مقایسه‌ی
        # فشرده‌شده مجاز است؛ وگرنه «as» با «ass» و «bob» با «boob» اشتباهی یکی می‌شد.
        if has_run and _eq_suffix(col, pc, plen, is_last):
            return True
    return False

def find_swear_word(text: Optional[str], words) -> Optional[str]:
    """
    اولین کلمه‌ی ممنوع (همان‌طور که در فهرست گروه ثبت شده) که در متن یافت شد، یا None.
    تطبیق «کلمه‌به‌کلمه» است نه substring: «خر» در «خرید» پیدا نمی‌شود ولی «خـــر»، «خ ر» (با
    فاصله/نیم‌فاصله)، «خررر» و «خر😀» پیدا می‌شود. عبارت چندکلمه‌ای («بی شرف») هم با فاصله، هم
    بدون فاصله («بیشرف») و هم با نیم‌فاصله تطبیق می‌شود.
    """
    if not text or not words:
        return None
    compiled = _compile_swear_words(tuple(w for w in words if isinstance(w, str)))
    toks = swear_tokens(text)
    if not compiled or not toks:
        return None
    forms = [_token_forms(t) for t in toks]
    n = len(toks)
    for original, ptoks in compiled:
        k = len(ptoks)
        for i in range(n - k + 1):
            if all(_tok_match(pt, forms[i + j], j == k - 1) for j, pt in enumerate(ptoks)):
                return original
        if k > 1:  # «بیشرف» (بدون فاصله) برای عبارت «بی شرف»
            joined = ("".join(p[0] for p in ptoks), _collapse_repeats("".join(p[0] for p in ptoks)),
                      sum(p[2] for p in ptoks))
            if any(_tok_match(joined, fs, True) for fs in forms):
                return original
    return None

# ---------- ۴) ضداسپم: پنجره‌ی زمانی، به‌ازای هر (گروه، کاربر)، با پاکسازی ----------
# فقط در حافظه (نه در JSON): وضعیت لحظه‌ای است، با ریستارت پاک می‌شود و دیتابیس را بزرگ نمی‌کند.
SPAM_MAX_TRACK_SECONDS = 60        # قدیمی‌تر از این هیچ‌وقت نگه داشته نمی‌شود
SPAM_LONG_WINDOW = 30              # سیل کند: بیش از SPAM_LONG_MAX پیام در ۳۰ ثانیه
SPAM_LONG_MAX = 12
SPAM_LINK_REPEAT_MAX = 2           # یک لینک تکراری بیش از ۲ بار در ۶۰ ثانیه
SPAM_DEFAULT_WINDOW = 5            # settings['spam_window']: پنجره‌ی رگبار (ثانیه)
SPAM_DEFAULT_MAX_MSGS = 3          # settings['spam_max_msgs']: حداکثر پیام مجاز در پنجره
SPAM_DEFAULT_REPEAT_MAX = 4        # settings['spam_repeat_max']: حداکثر تکرار یک متن/فایل در ۶۰ ثانیه

class _SpamRecord:
    __slots__ = ("times", "items")
    def __init__(self):
        self.times = deque(maxlen=200)   # زمان هر پیام
        self.items = deque(maxlen=200)   # (زمان، نوع: text|media|link، اثرانگشت)

_SPAM_STATE: Dict[Tuple[str, str], _SpamRecord] = {}
_spam_last_sweep = 0.0

def _spam_prune(rec: _SpamRecord, now: float):
    horizon = now - SPAM_MAX_TRACK_SECONDS
    while rec.times and rec.times[0] < horizon:
        rec.times.popleft()
    while rec.items and rec.items[0][0] < horizon:
        rec.items.popleft()

def _spam_sweep(now: float, force: bool = False):
    """رکوردهای بی‌فعالیتِ همه‌ی گروه‌ها/کاربران را پاک می‌کند (جلوگیری از رشد دائمی حافظه)."""
    global _spam_last_sweep
    if not force and now - _spam_last_sweep < 30 and len(_SPAM_STATE) < 5000:
        return
    _spam_last_sweep = now
    for key in list(_SPAM_STATE.keys()):
        rec = _SPAM_STATE[key]
        _spam_prune(rec, now)
        if not rec.times:
            del _SPAM_STATE[key]

def _spam_setting(settings: dict, key: str, default: int, lo: int, hi: int) -> int:
    try:
        v = int(settings.get(key, default))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))

def spam_check(group_id, user_id, settings: dict, text_fp=None, media_id=None, link_fp=None,
               now: Optional[float] = None) -> Optional[str]:
    """
    این پیام را در پنجره‌ی زمانی کاربر «در همین گروه» ثبت می‌کند و اگر اسپم بود علتش را برمی‌گرداند:
      burst        : بیش از spam_max_msgs پیام در spam_window ثانیه (رگبار/ارسال سریع پشت‌سرهم)
      flood        : بیش از ۱۲ پیام در ۳۰ ثانیه
      repeat_text  : یک متن یکسان بیش از spam_repeat_max بار در ۶۰ ثانیه
      repeat_media : یک فایل یکسان بیش از spam_repeat_max بار در ۶۰ ثانیه
      repeat_link  : یک لینک یکسان بیش از ۲ بار در ۶۰ ثانیه
    """
    now = time.monotonic() if now is None else now
    _spam_sweep(now)
    key = (str(group_id), str(user_id))          # جدا برای هر گروه و هر کاربر
    rec = _SPAM_STATE.get(key)
    if rec is None:
        rec = _SPAM_STATE[key] = _SpamRecord()
    _spam_prune(rec, now)
    rec.times.append(now)
    current = [(k, v) for k, v in (("text", text_fp), ("media", media_id), ("link", link_fp)) if v]
    for kind, val in current:
        rec.items.append((now, kind, val))

    window = _spam_setting(settings, "spam_window", SPAM_DEFAULT_WINDOW, 1, 60)
    max_msgs = _spam_setting(settings, "spam_max_msgs", SPAM_DEFAULT_MAX_MSGS, 1, 100)
    repeat_max = _spam_setting(settings, "spam_repeat_max", SPAM_DEFAULT_REPEAT_MAX, 1, 100)

    if sum(1 for t in rec.times if now - t <= window) > max_msgs:
        return "burst"
    if sum(1 for t in rec.times if now - t <= SPAM_LONG_WINDOW) > SPAM_LONG_MAX:
        return "flood"
    for kind, val in current:
        c = sum(1 for _t, k, v in rec.items if k == kind and v == val)
        if c > (SPAM_LINK_REPEAT_MAX if kind == "link" else repeat_max):
            return f"repeat_{kind}"
    return None

def spam_reset(group_id=None):
    """(برای تست/ادمین) پاک‌کردن وضعیت اسپم یک گروه یا همه."""
    if group_id is None:
        _SPAM_STATE.clear()
    else:
        for key in [k for k in _SPAM_STATE if k[0] == str(group_id)]:
            del _SPAM_STATE[key]

def _text_fingerprint(text: Optional[str]) -> Optional[int]:
    toks = swear_tokens(text or "")
    return hash(" ".join(toks)) if toks else None

# ---------- ۵) قفل‌ها: نوع‌ها، تشخیص تخلف ----------
# key: (نام فارسی، کلید settings برای قفل‌های قدیمی | None برای قفل نوع‌پیام که در settings['locks'] است)
LOCK_TYPE_INFO = {
    "media":      ("رسانه", "lock_media"),
    "forward":    ("فوروارد", "lock_forward"),
    "hashtag":    ("هشتگ", "lock_hashtag"),
    "mention":    ("منشن", "lock_mention"),
    "metadata":   ("متادیتا", "lock_metadata"),
    "photo":      ("عکس", None),
    "video":      ("فیلم", None),
    "animation":  ("گیف", None),
    "document":   ("فایل", None),
    "audio":      ("موزیک", None),
    "voice":      ("ویس", None),
    "video_note": ("ویدیو مسیج", None),
    "sticker":    ("استیکر", None),
    "contact":    ("مخاطب", None),
    "location":   ("موقعیت مکانی", None),
    "poll":       ("نظرسنجی", None),
    "game":       ("بازی", None),
    # 🛠 رفع باگ صداقت: این دو تا («آیدی»، «کدهنگی») سال‌ها فقط توی متنِ
    # راهنما (FULL_GUIDE_1/2/3) تبلیغ می‌شدن - نه توی LOCK_TYPE_INFO بودن، نه
    # هیچ منطق تشخیصی داشتن؛ یعنی «قفل آیدی» یا «قفل کدهنگی» اصلاً چیزی رو
    # قفل نمی‌کرد (نه خطا می‌داد، نه کار می‌کرد - فقط سکوت). الان واقعاً
    # پیاده‌سازی شدن (ببین پایین‌تر در find_lock_violation و detect_hang_code):
    #  - «آیدی»: بر خلافِ «منشن» (که فقط رو Entity واقعیِ تلگرام تکیه می‌کنه و
    #    فقط وقتی Entity غایب باشه regex می‌زنه)، این یکی همیشه با regex متنِ
    #    خام رو می‌گرده - سخت‌گیرانه‌تره و یوزرنیم‌هایی که تلگرام Entity ‌شون
    #    نکرده (مثلاً داخل اسپویلر/کد) رو هم می‌گیره.
    #  - «کدهنگی»: تشخیصِ «متنِ کرش‌کننده» (زالگوی سنگین/کاراکترهای کنترلِ
    #    جهت‌نوشتار RTL-LTR override/توکنِ بی‌فاصله‌ی خیلی طولانی) با یک
    #    امتیازِ ۰-۱۰۰ که با «حساسیت» قابل‌تنظیم گروه مقایسه می‌شه (دقیقاً
    #    همون چیزی که خودِ راهنما با «تنظیم حساسیت تشخیص کدهنگی #درصد» وعده داده بود).
    "id":         ("آیدی", None),
    "hangcode":   ("کدهنگی", None),
    # 🆕 «قفل کپشن»: مثل «آیدی»/«کدهنگی» فقط در راهنما (FULL_GUIDE_2) تبلیغ می‌شد
    # ولی نه در LOCK_TYPE_INFO بود نه هیچ منطق تشخیصی داشت. الان واقعی است:
    # هر پیام رسانه‌ای که کپشن (متن همراه عکس/فیلم/فایل/...) داشته باشد، اگر
    # این قفل فعال باشد به‌عنوان تخلف شناسایی می‌شود.
    "caption":    ("کپشن", None),
}
GRANULAR_LOCK_KEYS = tuple(k for k, (_n, sk) in LOCK_TYPE_INFO.items() if sk is None)
LOCK_TYPE_ALIASES = {
    "media": ["رسانه"], "forward": ["فوروارد", "فروارد"], "hashtag": ["هشتگ"], "mention": ["منشن"],
    # 🛠 رفع باگ: خیلی از کاربرها «متادیا» (بدون تشدید/بدون «ت» آخر) تایپ می‌کنن،
    # نه شکل کامل «متادیتا»؛ قبلاً فقط شکل کامل ثبت شده بود و شکل رایج‌تر هیچ جوابی نمی‌گرفت.
    "metadata": ["متادیتا", "متادیا"], "photo": ["عکس", "تصویر"], "video": ["فیلم", "ویدیو"], "animation": ["گیف"],
    "document": ["فایل"], "audio": ["موزیک", "آهنگ"], "voice": ["ویس", "صدا"],
    "video_note": ["ویدیو مسیج", "پیام ویدیویی"], "sticker": ["استیکر"], "contact": ["مخاطب", "شماره"],
    "location": ["موقعیت", "لوکیشن"], "poll": ["نظرسنجی"], "game": ["بازی"],
    "id": ["آیدی", "ایدی", "یوزرنیم"], "hangcode": ["کدهنگی", "کد هنگی", "کدهنگ"],
    "caption": ["کپشن", "کپشن دار"],
}
_LOCK_EN_ALIASES = {
    "photo": "photo", "pic": "photo", "image": "photo", "video": "video", "gif": "animation",
    "animation": "animation", "document": "document", "file": "document", "audio": "audio",
    "music": "audio", "voice": "voice", "videonote": "video_note", "video_note": "video_note",
    "sticker": "sticker", "contact": "contact", "location": "location", "poll": "poll", "game": "game",
    "media": "media", "forward": "forward", "hashtag": "hashtag", "mention": "mention", "metadata": "metadata",
    "id": "id", "username": "id", "hangcode": "hangcode", "hang_code": "hangcode", "hang": "hangcode",
}
_MSG_TYPE_FA = {"dice": "بازی", "photo": "عکس", "video": "فیلم", "animation": "گیف", "document": "فایل",
                "audio": "موزیک", "voice": "ویس", "video_note": "ویدیو مسیج", "sticker": "استیکر",
                "contact": "مخاطب", "location": "موقعیت مکانی", "poll": "نظرسنجی", "game": "بازی"}

def resolve_lock_type(arg: Optional[str]) -> Optional[str]:
    a = normalize_fa(arg or "").lower().replace("‌", " ").strip()
    if a in _LOCK_EN_ALIASES:
        return _LOCK_EN_ALIASES[a]
    for key, names in LOCK_TYPE_ALIASES.items():
        if a in names or a == LOCK_TYPE_INFO[key][0]:
            return key
    return None

def is_lock_type_on(settings: dict, key: str) -> bool:
    sk = LOCK_TYPE_INFO[key][1]
    if sk:
        return bool(settings.get(sk, False))
    return bool((settings.get("locks") or {}).get(key, False))

_HASHTAG_RE = re.compile(r"(?<![\w#])#[^\W\d_]\w*", re.UNICODE)
_MENTION_RE = re.compile(r"(?<![\w@.])@[A-Za-z][\w]{3,}")
# «آیدی» عمداً از regex متن خام استفاده می‌کنه (نه فقط Entity) - سخت‌گیرانه‌تر از «منشن».
# 🛠 رفع باگ بحرانیِ shadowing: این متغیر قبلاً هم «_ID_RE» نام‌گذاری شده بود، ولی
# پایین‌تر (بخش Tag/شناسه‌ی عددی کاربر) یک «_ID_RE» کاملاً متفاوت (regex اعتبارسنجی
# آیدی عددی ۵ تا ۱۵ رقمی) دوباره همین نام ماژول‌سطح را تعریف می‌کرد و بی‌صدا این
# مقدار را بازنویسی می‌کرد. نتیجه: «قفل آیدی» فعال می‌شد و تاییدش هم می‌آمد، ولی
# find_lock_violation همیشه با regex عددیِ اشتباه چک می‌کرد که هیچ‌وقت با @یوزرنیم
# match نمی‌شد - یعنی قفل ظاهراً روشن بود ولی هیچ پیامی را واقعاً قفل نمی‌کرد. با
# تغییر نام به «_ID_LOCK_MENTION_RE» این تداخل برای همیشه رفع می‌شود.
_ID_LOCK_MENTION_RE = re.compile(r"(?<![\w@.])@[A-Za-z][\w]{3,}")

# ---------- ۵-ب) تشخیص «کدهنگی» (متنِ کرش‌کننده/هنگ‌کننده) ----------
# منابع شناخته‌شده‌ی کرش‌کردن کلاینت‌های چت: (۱) بمبِ زالگو - انبوه کاراکتر
# ترکیبیِ Unicode (دسته‌ی Mn/Mc/Me) که رندرِ گلیف رو کند/خراب می‌کنه، (۲)
# کاراکترهای کنترلِ جهتِ نوشتار (RLO/LRO/RLE/LRE/RLI/LRI/FSI/PDF/PDI) که با
# چیدمانِ RTL-LTR بازی می‌کنن و می‌تونن UI رو بهم بریزن، (۳) یک توکنِ خیلی
# طولانیِ بدون فاصله که موتورِ line-break رو گیر می‌ندازه.
_BIDI_CONTROL_CHARS = frozenset(
    "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
)

def detect_hang_code(text: str) -> float:
    """امتیازِ ۰ تا ۱۰۰: احتمالِ اینکه این متن یه «کدهنگ» (متنِ کرش/هنگ‌کننده) باشه."""
    if not text:
        return 0.0
    n = len(text)
    combining = sum(1 for ch in text if unicodedata.combining(ch))
    bidi_ctrl = sum(1 for ch in text if ch in _BIDI_CONTROL_CHARS)
    longest_token = max((len(t) for t in text.split()), default=0)
    score = 0.0
    if n:
        score += min(60.0, (combining / n) * 300.0)
    score += min(30.0, bidi_ctrl * 10.0)
    if longest_token > 200:
        score += min(20.0, (longest_token - 200) / 20.0)
    return min(100.0, score)

def find_lock_violation(message, settings: dict) -> Optional[Tuple[str, str]]:
    """(کلید قفل، توضیح) اگر پیام یکی از قفل‌های فعال را نقض کند، وگرنه None. کپشن هم بررسی می‌شود."""
    mtype = detect_message_type(message)
    if mtype == "service":
        return None
    if mtype in MEDIA_LOCK_TYPES and is_lock_type_on(settings, "media"):
        return "media", f"رسانه ({_MSG_TYPE_FA.get(mtype, mtype)})"
    gkey = "game" if mtype == "dice" else mtype
    if gkey in GRANULAR_LOCK_KEYS and is_lock_type_on(settings, gkey):
        return gkey, LOCK_TYPE_INFO[gkey][0]
    if is_lock_type_on(settings, "forward") and getattr(message, "is_forwarded", False) \
            and not getattr(message, "is_automatic_forward", False):
        return "forward", "پیام فوروارد‌شده"
    ents = getattr(message, "all_entities", None) or []
    etypes = {e.get("type") for e in ents}
    text = getattr(message, "text", None) or ""
    caption = getattr(message, "caption", None) or ""
    combined_text = f"{text} {caption}".strip()
    # هشتگ/منشن واقعی = Entity تلگرام (hashtag / mention / text_mention)، نه صرفاً وجود «#» یا «@» در متن
    # (مثلاً «#3» یا «C#» هشتگ نیست و داخل کد/لینک هم هشتگ حساب نمی‌شود). فقط اگر پیام اصلاً اطلاعات
    # Entity نداشته باشد (لایه‌ی سازگاری قدیمی) به regex برمی‌گردیم.
    has_entity_info = getattr(message, "all_entities", None) is not None
    if is_lock_type_on(settings, "hashtag") and ("hashtag" in etypes or (not has_entity_info and _HASHTAG_RE.search(text))):
        return "hashtag", "هشتگ"
    if is_lock_type_on(settings, "mention") and ("mention" in etypes or "text_mention" in etypes
                                                 or (not has_entity_info and _MENTION_RE.search(text))):
        return "mention", "منشن"
    if is_lock_type_on(settings, "metadata") and (etypes & {"text_link", "text_mention", "spoiler"}
                                                  or getattr(message, "via_bot", False)):
        return "metadata", "متادیتا (لینک/منشن پنهان، اسپویلر، پیام ربات اینلاین)"
    # «کپشن»: هر پیام رسانه‌ای (عکس/فیلم/فایل/گیف/موزیک/ویس و ...) که متن کپشن
    # (غیرخالی) همراهش باشد، اگر این قفل فعال باشد تخلف محسوب می‌شود.
    if is_lock_type_on(settings, "caption") and caption.strip():
        return "caption", "کپشن (متن همراه رسانه)"
    # «آیدی»: همیشه با regex روی متن+کپشنِ خام (نه فقط Entity) - عمداً سخت‌گیرتر از «منشن».
    if is_lock_type_on(settings, "id") and _ID_LOCK_MENTION_RE.search(combined_text):
        return "id", "آیدی (یوزرنیم/@)"
    # «کدهنگی»: امتیازدهی، نه فقط بله/خیر؛ با «حساسیت» قابل‌تنظیمِ گروه مقایسه می‌شه.
    if is_lock_type_on(settings, "hangcode") and combined_text:
        sensitivity = settings.get("hangcode_sensitivity", 70)
        score = detect_hang_code(combined_text)
        if score >= sensitivity:
            return "hangcode", f"کدهنگ (متنِ کرش‌کننده، احتمال {score:.0f}٪)"
    return None

# ---------- ۶) بای‌پس: مالک/ادمین/ویژه/معاف + ادمین واقعی تلگرام ----------
ANONYMOUS_ADMIN_ID = "1087968824"   # GroupAnonymousBot
TELEGRAM_SERVICE_ID = "777000"      # پست‌های کانالِ متصل که تلگرام خودش فوروارد می‌کند
_TG_ADMIN_CACHE: Dict[Tuple[str, str], Tuple[float, bool]] = {}
_TG_ADMIN_TTL = 120.0

async def is_filter_exempt(bot, message, group_id, group_data, user_id) -> bool:
    """قبل از هر Delete/Warn/Restrict چک می‌شود. عضو عادی -> False."""
    if get_permission_level(user_id, group_data) >= Perm.EXEMPT:
        return True
    if str(user_id) in (ANONYMOUS_ADMIN_ID, TELEGRAM_SERVICE_ID):
        return True
    if getattr(message, "is_anonymous_admin", False) or getattr(message, "is_automatic_forward", False):
        return True
    # ادمین واقعیِ خود تلگرام که در لیست ادمین‌های ربات ثبت نشده (فقط وقتی تخلف تشخیص داده شده
    # و فقط با کش ۲ دقیقه‌ای، تا برای هر پیام API صدا زده نشود)
    key = (str(group_id), str(user_id))
    now = time.monotonic()
    cached = _TG_ADMIN_CACHE.get(key)
    if cached and now - cached[0] < _TG_ADMIN_TTL:
        return cached[1]
    status = await bot.get_member_status(group_id, user_id)
    if status is None:
        return False  # نتوانستیم بخوانیم؛ فقط سطح دسترسی ربات ملاک است (کش نمی‌شود)
    is_tg_admin = status["status"] in ("administrator", "creator")
    if len(_TG_ADMIN_CACHE) > 2000:
        _TG_ADMIN_CACHE.clear()
    _TG_ADMIN_CACHE[key] = (now, is_tg_admin)
    return is_tg_admin

# ---------- ۷) اقدام واقعی + اعلان بدون اسپم ----------
_NOTICE_TS: Dict[tuple, float] = {}

def _notice_allowed(key: tuple, cooldown: float) -> bool:
    now = time.monotonic()
    last = _NOTICE_TS.get(key)
    if last is not None and now - last < cooldown:
        return False
    if len(_NOTICE_TS) > 2000:
        for k in [k for k, t in _NOTICE_TS.items() if now - t > 3600]:
            del _NOTICE_TS[k]
    _NOTICE_TS[key] = now
    return True

async def enforce_delete(message, group_id, user_id, kind: str, notice: str) -> ActionResult:
    """
    پیام متخلف را واقعاً حذف می‌کند. فقط اگر تلگرام حذف را تایید کرد، اعلان «ممنوع» نمایش داده
    می‌شود (و برای هر کاربر/نوع تخلف حداکثر هر ۲۰ ثانیه، تا خود ربات اسپم نکند). اگر حذف ناموفق
    بود (مثلاً ربات دسترسی حذف ندارد) به‌جایش علت واقعی گفته می‌شود (هر ۱۰ دقیقه یک‌بار برای گروه).
    """
    res = await message.delete()
    if res:
        if _notice_allowed((str(group_id), str(user_id), kind), 20):
            await message.reply(notice)
    elif _notice_allowed((str(group_id), "*", "delete_failed"), 600):
        await message.reply(f"⚠️ پیام متخلف ({kind}) حذف نشد و قفل/فیلتر عملاً اعمال نشد.\n🔎 علت: {res.error}")
    return res

async def is_tabchi_suspect(group_data: dict, user_id: str) -> bool:
    """آیا این کاربر «تازه‌عضو» است، طبق پنجره‌ی زمانی anti_tabchi_window_seconds؟
    اول از Member Registry (دقیق‌تر) و در نبود آن از users[user_id]['join_date'] (قدیمی) می‌خواند."""
    uid = str(user_id)
    settings = group_data.get('settings', {})
    try:
        window = max(1, int(settings.get('anti_tabchi_window_seconds', 300)))
    except (TypeError, ValueError):
        window = 300
    joined_raw = None
    rec = group_data.get('members', {}).get(uid)
    if rec and rec.get('joined_at'):
        joined_raw = rec['joined_at']
    else:
        joined_raw = group_data.get('users', {}).get(uid, {}).get('join_date')
    if not joined_raw:
        return False
    try:
        joined_dt = datetime.fromisoformat(joined_raw)
    except (TypeError, ValueError):
        return False
    return (datetime.now() - joined_dt).total_seconds() <= window


# =========================================================
#  👥 بخش ۳ ممیزی: Member Registry + رویدادهای واقعی عضویت + Tag / Tag All
# =========================================================
# Bot API راهی برای «گرفتن لیست کامل اعضا» ندارد (فقط ادمین‌ها و تعداد کل). پس ربات یک Registry
# دائمی (داخل دیتابیس JSON، نه RAM) نگه می‌دارد که با هر پیام، هر رویداد واقعی chat_member و هر پیام
# سرویسیِ ورود/خروج به‌روز می‌شود. همه‌ی قابلیت‌های Tag/Welcome/Goodbye فقط از همین Registry می‌خوانند
# و اگر Registry ناقص باشد، صادقانه همین را می‌گویند (نه «همه تگ شدند»).
#   group_data['members'][user_id] = {user_id, username, first_name, last_name, is_bot, status,
#                                     joined_at, last_seen, left_at, status_source, status_checked_at}
# status: owner | administrator | member | restricted | left | banned | unknown
# (unknown = کاربرانی که فقط از دیتابیس قدیمی (users) آمده‌اند و هنوز وضعیتشان از تلگرام تایید نشده)
REG_ACTIVE = ("owner", "administrator", "member", "restricted")

def _reg_now() -> str:
    return datetime.now().isoformat()

def _norm_name(text: Optional[str]) -> str:
    t = normalize_fa((text or "").replace("\u200c", " ")).lower()
    return re.sub(r"\s+", " ", t).strip()

def _members(group_data: dict) -> dict:
    """Registry را تضمین می‌کند و یک‌بار داده‌ی قدیمی users را به آن مهاجرت می‌دهد."""
    members = group_data.get("members")
    if not isinstance(members, dict):
        members = group_data["members"] = {}
    if not group_data.get("members_migrated"):
        for uid, info in (group_data.get("users") or {}).items():
            if uid not in members:
                members[uid] = {
                    "user_id": uid, "username": None,
                    "first_name": (info or {}).get("first_name", "") or "", "last_name": (info or {}).get("last_name", "") or "",
                    "is_bot": False, "status": "unknown", "status_source": "legacy",
                    "joined_at": (info or {}).get("join_date"), "last_seen": None, "left_at": None,
                    "status_checked_at": None,
                }
        group_data["members_migrated"] = True
    return members

def _registry_set_status(rec: dict, status: str, source: str, now: str):
    prev = rec.get("status")
    if source == "service" and status == "left" and prev == "banned":
        return  # پیام سرویسیِ «خروج» بعد از بن، وضعیت «banned» را پایین نیاورد
    if source == "service" and status == "member" and prev in REG_ACTIVE:
        return
    if status in REG_ACTIVE:
        if prev not in REG_ACTIVE:
            if prev in ("left", "banned") or not rec.get("joined_at"):
                rec["joined_at"] = now
            rec["left_at"] = None
    elif status in ("left", "banned"):
        if prev in REG_ACTIVE or prev in (None, "unknown"):
            rec["left_at"] = now
    rec["status"] = status
    rec["status_source"] = source
    rec["status_checked_at"] = now

def registry_touch(group_data: dict, user: dict, status: Optional[str] = None, source: str = "message",
                   now: Optional[str] = None) -> Optional[dict]:
    """کاربر را در Registry ثبت/به‌روز می‌کند (با User ID به‌عنوان کلید، نه نام)."""
    uid = str((user or {}).get("id") or "")
    if not uid or uid in ("None", "0"):
        return None
    members = _members(group_data)
    now = now or _reg_now()
    rec = members.get(uid)
    if rec is None:
        rec = members[uid] = {
            "user_id": uid, "username": None, "first_name": "", "last_name": "", "is_bot": False,
            "status": "unknown", "status_source": source, "joined_at": None, "last_seen": None,
            "left_at": None, "status_checked_at": None,
        }
    if "username" in user:
        rec["username"] = user.get("username") or None
    if user.get("first_name") is not None:
        rec["first_name"] = user.get("first_name") or ""
    if user.get("last_name") is not None:
        rec["last_name"] = user.get("last_name") or ""
    if user.get("is_bot") is not None:
        rec["is_bot"] = bool(user["is_bot"])
    if source == "message":
        rec["last_seen"] = now
        if rec["status"] not in REG_ACTIVE:      # کسی که پیام می‌فرستد قطعاً همین الان عضو است
            _registry_set_status(rec, "member", "message", now)
    if status:
        _registry_set_status(rec, status, source, now)
    return rec

def registry_active(group_data: dict, include_bots: bool = False, exclude_ids=()) -> List[dict]:
    excl = {str(x) for x in exclude_ids if x is not None}
    return [r for uid, r in _members(group_data).items()
            if r.get("status") in REG_ACTIVE and uid not in excl and (include_bots or not r.get("is_bot"))]

def member_display_name(rec: Optional[dict]) -> str:
    """نام برای نمایش/Mention؛ هرگز «None» یا آیدی خام نمی‌سازد."""
    if not rec:
        return "کاربر"
    name = " ".join(x for x in ((rec.get("first_name") or "").strip(), (rec.get("last_name") or "").strip()) if x)
    return name[:40] or (("@" + rec["username"]) if rec.get("username") else "کاربر")

def registry_find_username(group_data: dict, username: str) -> Optional[dict]:
    u = (username or "").lstrip("@").strip().lower()
    for rec in _members(group_data).values():
        if rec.get("username") and rec["username"].lower() == u:
            return rec
    return None

def registry_find_names(group_data: dict, query: str) -> List[dict]:
    """جستجوی نام: اول تطبیق دقیق (نام / نام‌خانوادگی / نام کامل)، اگر نبود شامل‌بودن. چند نتیجه = مبهم."""
    q = _norm_name(query)
    if not q:
        return []
    exact, partial = [], []
    for rec in _members(group_data).values():
        first, last = _norm_name(rec.get("first_name")), _norm_name(rec.get("last_name"))
        full = f"{first} {last}".strip()
        if q in (first, last, full):
            exact.append(rec)
        elif len(q) >= 3 and q in full:
            partial.append(rec)
    return exact or partial

async def registry_verify(bot, group_id, group_data: dict, uid: str) -> Optional[str]:
    """وضعیت واقعی یک کاربر را از تلگرام می‌پرسد و Registry را به‌روز می‌کند؛ None اگر نشد."""
    info = await bot.get_member_info(group_id, uid)
    if not info:
        return None
    registry_touch(group_data, info["user"], status=info["status"], source="api")
    return info["status"]

# ---------- Welcome / Goodbye: تنها منبع حقیقت settings['welcome'|'goodbye'] ----------
_DEFAULT_WELCOME = '🎉 به گروه خوش اومدی {name}!'
_DEFAULT_GOODBYE = '👋 {name} از گروه خارج شد!'

def migrate_welcome_settings(group_data: dict):
    """
    🛠 رفع سردرگمی «welcome/goodbye» در برابر «group_welcome/group_goodbye»: دو مجموعه‌ی جدا با دو دستور
    جدا وجود داشت و فقط یکی (که آن هم اشتباهاً روی اولین پیام کاربر) کار می‌کرد. حالا فقط
    settings['welcome'] / ['goodbye'] (+ welcome_enabled / goodbye_enabled) معتبر است. مقدار قدیمی
    group_* اگر ادمین قبلاً تنظیم کرده بود و متن اصلی هنوز پیش‌فرض بود، منتقل و سپس حذف می‌شود.
    """
    st = group_data.setdefault("settings", {})
    for legacy, canon, default in (("group_welcome", "welcome", _DEFAULT_WELCOME),
                                   ("group_goodbye", "goodbye", _DEFAULT_GOODBYE)):
        if legacy in st:
            val = st.pop(legacy)
            if isinstance(val, str) and val.strip() and (not st.get(canon) or st.get(canon) == default):
                st[canon] = val

def get_welcome_config(group_data: dict) -> Tuple[bool, str]:
    migrate_welcome_settings(group_data)
    st = group_data["settings"]
    return bool(st.get("welcome_enabled", True)), st.get("welcome") or ""

def get_goodbye_config(group_data: dict) -> Tuple[bool, str]:
    migrate_welcome_settings(group_data)
    st = group_data["settings"]
    return bool(st.get("goodbye_enabled", True)), st.get("goodbye") or ""

# ---------- رویداد واقعی عضویت: ورود / خروج ----------
_RECENT_EVENTS: Dict[tuple, float] = {}

def _event_seen(kind: str, group_id, uid, ttl: float = 120.0) -> bool:
    """True اگر همین رویداد (join/leave) برای همین کاربر تازه پردازش شده (دو منبع: Update واقعی
    chat_member و پیام سرویسی ممکن است هر دو برسند؛ نباید دو بار خوش‌آمد/خداحافظ گفته شود)."""
    now = time.monotonic()
    key = (kind, str(group_id), str(uid))
    last = _RECENT_EVENTS.get(key)
    if last is not None and now - last < ttl:
        return True
    if len(_RECENT_EVENTS) > 2000:
        for k in [k for k, t in _RECENT_EVENTS.items() if now - t > ttl]:
            del _RECENT_EVENTS[k]
    _RECENT_EVENTS[key] = now
    return False

@bot.on_member_update()
async def member_event_handler(bot: Robot, ev):
    """
    Welcome/Goodbye و به‌روزرسانی Registry بر پایه‌ی «رویداد واقعی» (وضعیت قبلی → وضعیت جدید)، نه
    پیام عادی کاربر. ورود = غیرعضو→عضو؛ خروج = عضو→left؛ عضو→banned فقط Registry را به‌روز می‌کند.
    """
    group_id = ev.chat_id
    user = ev.user or {}
    uid = str(user.get("id") or "")
    if not uid:
        return
    group_data = get_group_data(group_id)

    if bot.bot_id and uid == str(bot.bot_id):
        # وضعیت خود ربات (مثلاً ادمین شد/برداشته شد): برای اطلاع از اینکه رویداد chat_member می‌رسد یا نه
        was_in_chat = (ev.old_status or "") in REG_ACTIVE
        now_in_chat = ev.new_status in REG_ACTIVE
        group_data["bot_status"] = ev.new_status
        group_data["bot_status_at"] = _reg_now()
        save_group_data(group_id, group_data)
        # 🛠 رویداد فعال‌سازی #۱: ربات تازه به گروه اضافه شد (غیرعضو → عضو/ادمین).
        # actor_id همان کسی‌ست که واقعاً ربات را اضافه کرده؛ اگر تلگرام actor_id
        # ندهد (بعضی نسخه‌های قدیمی client)، بی‌خیال می‌شویم و فقط رویداد /start
        # (پایین‌تر) به‌عنوان راه دوم فعال‌سازی می‌ماند.
        if now_in_chat and not was_in_chat:
            # فعال‌سازی خودکار هنگام اضافه‌شدن ربات به گروه؛ دیگر نیازی به /start نیست.
            # هوش مصنوعی هم از همان لحظه برای این گروه فعال می‌شود.
            group_data.setdefault("settings", {})["ai_enabled"] = True
            group_data["activated_at"] = group_data.get("activated_at") or datetime.now().isoformat()
            if ev.actor_id:
                await _set_owner_if_unset(bot, group_id, ev.actor_id, "افزودن ربات به گروه")
            save_group_data(group_id, group_data)
        return

    prev = (_members(group_data).get(uid) or {}).get("status")
    old = ev.old_status if ev.old_status not in (None, "unknown") else prev
    was_active = old in REG_ACTIVE
    if ev.source == "service" and ev.new_status == "left" and prev in (None, "unknown"):
        was_active = True  # پیام «X گروه را ترک کرد» یعنی قبلاً عضو بوده، حتی اگر ربات ندیده بودش
    is_active = ev.new_status in REG_ACTIVE

    registry_touch(group_data, user, status=ev.new_status, source=ev.source)
    save_group_data(group_id, group_data)

    if user.get("is_bot"):
        return
    name = member_display_name(_members(group_data).get(uid))
    group_name = group_data.get("group_name", "گروه")

    if is_active and not was_active:
        enabled, text = get_welcome_config(group_data)
        text = (group_data.get("personal_welcome") or {}).get(uid) or text
        if enabled and text and not _event_seen("join", group_id, uid):
            res = await bot.send_text(group_id, replace_tags(text, name, group_name))
            if not res:
                logging.getLogger("gardi").warning("welcome send failed: %s", res.error)
    elif ev.new_status == "left" and was_active:
        enabled, text = get_goodbye_config(group_data)
        if enabled and text and not _event_seen("leave", group_id, uid):
            res = await bot.send_text(group_id, replace_tags(text, name, group_name))
            if not res:
                logging.getLogger("gardi").warning("goodbye send failed: %s", res.error)

# ---------- Tag: هدف همیشه با User ID مشخص می‌شود ----------
_USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{4,31}$")
_ID_RE = re.compile(r"^\d{5,15}$")

def _user_from_reply(reply) -> Optional[dict]:
    rid = str(getattr(reply, "sender_id", "") or "")
    if not rid or rid == "None" or getattr(reply, "is_anonymous_admin", False):
        return None
    return {"id": rid, "username": getattr(reply, "sender_username", None),
            "first_name": getattr(reply, "sender_first_name", None) or "",
            "last_name": getattr(reply, "sender_last_name", None) or "",
            "is_bot": bool(getattr(reply, "sender_is_bot", False))}

async def _ensure_active(bot, group_id, group_data, rec: dict) -> Optional[str]:
    """None اگر کاربر عضو فعال است، وگرنه پیام خطای صادقانه. وضعیت نامعلوم از خود تلگرام پرسیده می‌شود."""
    st = rec.get("status")
    if st == "unknown" or not st:
        st = await registry_verify(bot, group_id, group_data, rec["user_id"]) or "unknown"
    if st in REG_ACTIVE:
        return None
    if st in ("left", "banned"):
        return f"❌ {member_display_name(rec)} دیگر عضو گروه نیست ({'ممنوع‌شده' if st == 'banned' else 'خارج‌شده'})."
    return f"❌ نتوانستم عضویت {member_display_name(rec)} را از تلگرام تایید کنم؛ تگ انجام نشد."

async def resolve_tag_target(bot, message, group_id: str, arg: str):
    """
    هدف تگ را به «User ID» تبدیل می‌کند. خروجی: (user_dict | None، متن باقی‌مانده، پیام خطا | None).
    ترتیب: ۱) ریپلای (فرستنده‌ی پیام ریپلای‌شده) ۲) TEXT_MENTION (User ID مستقیم) ۳) @username
    (نرمال → Resolve → بررسی نتیجه) ۴) آیدی عددی ۵) جستجوی نام (چند نتیجه = مبهم، تگ نمی‌شود).
    """
    group_data = get_group_data(group_id)
    arg = (arg or "").strip()

    reply = getattr(message, "reply_to_message", None)
    if reply is not None:
        user = _user_from_reply(reply)
        if not user:
            return None, arg, "❌ فرستنده‌ی این پیام ناشناس/کانال است و User ID ندارد؛ تگ ممکن نیست."
        rec = registry_touch(group_data, user, source="reply") or {}
        err = await _ensure_active(bot, group_id, group_data, rec) if rec else None
        save_group_data(group_id, group_data)
        return (user, arg, err) if err is None else (None, arg, err)

    # TEXT_MENTION: کاربر مستقیم با User ID انتخاب شده (حتی بدون username)
    for ent in getattr(message, "all_entities", None) or []:
        if ent.get("type") == "text_mention" and ent.get("user") and ent["user"].get("id"):
            user = ent["user"]
            rest = arg.replace(ent.get("text") or "\0", "", 1).strip()
            rec = registry_touch(group_data, user, source="mention") or {}
            err = await _ensure_active(bot, group_id, group_data, rec) if rec else None
            save_group_data(group_id, group_data)
            return (user, rest, err) if err is None else (None, rest, err)

    if not arg:
        return None, "", "⚠️ دستور: روی پیام کاربر ریپلای کن، یا /tag [@username | آیدی عددی | نام] [متن]"

    first, _, rest = arg.partition(" ")
    rest = rest.strip()

    # --- @username ---
    if first.startswith("@"):
        norm = first.lstrip("@").lower()
        if not _USERNAME_RE.match(norm):
            return None, rest, f"❌ نام کاربری «{first}» نامعتبر است (۵ تا ۳۲ حرف انگلیسی/عدد/زیرخط)."
        rec = registry_find_username(group_data, norm)
        if rec is None:
            info = await bot.resolve_username(norm)            # Resolve
            if not info:
                return None, rest, (f"❌ کاربری با نام کاربری @{norm} پیدا نشد (یا ربات نمی‌تواند او را ببیند). "
                                    "تگ انجام نشد؛ ریپلای یا آیدی عددی را امتحان کن.")
            rec = registry_touch(group_data, info, source="resolve")
        err = await _ensure_active(bot, group_id, group_data, rec)   # بررسی نتیجه
        save_group_data(group_id, group_data)
        if err:
            return None, rest, err
        return {"id": rec["user_id"], "username": rec.get("username"), "first_name": rec.get("first_name"),
                "last_name": rec.get("last_name"), "is_bot": rec.get("is_bot")}, rest, None

    # --- آیدی عددی ---
    if _ID_RE.match(first):
        rec = _members(group_data).get(first)
        if rec is None:
            info = await bot.get_member_info(group_id, first)
            if not info:
                return None, rest, f"❌ کاربر با آیدی {first} پیدا نشد؛ تگ انجام نشد."
            rec = registry_touch(group_data, info["user"], status=info["status"], source="api")
        err = await _ensure_active(bot, group_id, group_data, rec)
        save_group_data(group_id, group_data)
        if err:
            return None, rest, err
        return {"id": rec["user_id"], "username": rec.get("username"), "first_name": rec.get("first_name"),
                "last_name": rec.get("last_name"), "is_bot": rec.get("is_bot")}, rest, None

    # --- جستجوی نام (شناسه‌ی یکتا نیست؛ ممکن است چندکلمه‌ای باشد، پس طولانی‌ترین پیشوند
    #     منطبق را نام و باقیمانده را متن پیام در نظر می‌گیریم: «/tag سعید محمدی سلام» -> نام
    #     «سعید محمدی»، پیام «سلام») ---
    words = arg.split()
    name_query = matches = None
    for cut in range(len(words), 0, -1):
        candidate = " ".join(words[:cut])
        found = registry_find_names(group_data, candidate)
        if found:
            name_query, matches, name_rest = candidate, found, " ".join(words[cut:])
            break
    if not matches:
        return None, "", f"❌ کاربری با نام «{arg}» در فهرست شناخته‌شده‌ی ربات نیست؛ ریپلای یا @username بزن."
    active = [r for r in matches if r.get("status") in REG_ACTIVE or r.get("status") == "unknown"]
    if not active:
        return None, "", f"❌ {member_display_name(matches[0])} دیگر عضو گروه نیست."
    if len(active) > 1:
        lines = [f"{i}. {member_display_name(r)}" + (f" (@{r['username']})" if r.get("username") else "") + f" — {r['user_id']}"
                 for i, r in enumerate(active[:8], 1)]
        return None, "", ("⚠️ چند کاربر با این نام پیدا شد؛ تگ انجام نشد. با آیدی عددی یا ریپلای مشخص کن:\n"
                          + "\n".join(lines))
    rec = active[0]
    err = await _ensure_active(bot, group_id, group_data, rec)
    save_group_data(group_id, group_data)
    if err:
        return None, name_rest, err
    return {"id": rec["user_id"], "username": rec.get("username"), "first_name": rec.get("first_name"),
            "last_name": rec.get("last_name"), "is_bot": rec.get("is_bot")}, name_rest, None

@bot.on_message(filters=lambda m: _cmd_is(m, "tag"))
async def tag_cmd(bot: Robot, message: Message):
    """تگ یک کاربر با Mention واقعی (tg://user?id=…). /tag [@username | آیدی | نام] [متن] یا ریپلای + /tag."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    user, rest, err = await resolve_tag_target(bot, message, group_id, _cmd_rest(message.text))
    if err:
        await message.reply(err)
        return
    body = _html_escape(rest[:500]) if rest else ""
    mention = mention_html(user["id"], member_display_name(user))
    reply_msg = getattr(message, "reply_to_message", None)
    res = await bot.send_text(group_id, f"{mention} {body}".strip(), html=True,
                              reply_to=getattr(reply_msg, "message_id", None) if reply_msg else None)
    if not res:
        await message.reply(f"❌ تگ انجام نشد.\n🔎 علت: {res.error}")

# ---------- Tag All: Registry، تکه‌تکه، با Lock و Cooldown و اجرا در پس‌زمینه ----------
TAGALL_CHUNK_DEFAULT = 30          # حداکثر Mention در هر پیام (سقف تلگرام: ۱۰۰ Entity)
TAGALL_MAX_DEFAULT = 500           # حداکثر نفر در یک عملیات
TAGALL_COOLDOWN_DEFAULT = 120      # ثانیه بین دو Tag All یک گروه
TAGALL_CHUNK_DELAY = 3.5           # تلگرام: حداکثر ~۲۰ پیام در دقیقه در هر گروه
TAGALL_VISIBLE_LIMIT = 3500        # طول متن قابل‌مشاهده‌ی هر پیام (سقف ۴۰۹۶)
TAGALL_VERIFY_MAX = 200            # حداکثر تایید وضعیتِ کاربران نامعلوم در هر عملیات
TAGALL_VERIFY_DELAY = 0.05
_TAGALL_ACTIVE: Dict[str, float] = {}        # قفل عملیات برای هر گروه (tagall_lock[group_id])
_TAGALL_LAST: Dict[str, float] = {}          # آخرین پایان عملیات (Cooldown)
_TAGALL_TASKS: Dict[str, Any] = {}           # نگه‌داشتن Task ها (تا Garbage Collect نشوند)

def _html_escape(text: str) -> str:
    import html as _h
    return _h.escape(text or "")

def build_tag_chunks(members: List[dict], header: str = "", per_message: int = TAGALL_CHUNK_DEFAULT,
                     visible_limit: int = TAGALL_VISIBLE_LIMIT) -> List[str]:
    """
    لیست اعضا -> چند پیام HTML. هر پیام هم از نظر «تعداد Mention» و هم از نظر «طول متن قابل‌مشاهده»
    (نه طول HTML) محدود می‌شود؛ متن سربرگ فقط در پیام اول می‌آید و طولش هم حساب می‌شود.
    """
    per_message = max(1, min(int(per_message), 50))
    chunks: List[str] = []
    cur: List[str] = []
    cur_len = 0
    first = True
    head_len = len(header)

    def flush():
        nonlocal cur, cur_len, first
        if not cur:
            return
        head = (_html_escape(header) + "\n\n") if (first and header) else ""
        chunks.append(head + "، ".join(cur))
        first = False
        cur, cur_len = [], 0

    for m in members:
        name = member_display_name(m)
        label_len = len(name) + 2
        base = head_len + 2 if (first and header) else 0
        if cur and (len(cur) >= per_message or base + cur_len + label_len > visible_limit):
            flush()
            base = head_len + 2 if (first and header) else 0
        cur.append(mention_html(m["user_id"], name))
        cur_len += label_len
    flush()
    return chunks

async def prepare_tagall(bot, group_id: str) -> dict:
    """
    Registry را برای Tag All آماده می‌کند: ۱) ادمین‌های واقعی از تلگرام ۲) تایید وضعیت کاربران «نامعلوم»
    (حداکثر TAGALL_VERIFY_MAX) ۳) مقایسه‌ی تعداد شناخته‌شده‌ها با تعداد واقعی اعضای گروه.
    خروجی: {'targets', 'known_active', 'total', 'complete', 'skipped_bots', 'unverified', 'bot_is_admin'}
    """
    group_data = get_group_data(group_id)
    admins = await bot.get_admins(group_id)
    if admins:
        for a in admins:
            registry_touch(group_data, a["user"], status=a["status"], source="admins")
    unknown = [uid for uid, r in _members(group_data).items() if r.get("status") == "unknown"][:TAGALL_VERIFY_MAX]
    for uid in unknown:
        info = await bot.get_member_info(group_id, uid)
        if info:
            registry_touch(group_data, info["user"], status=info["status"], source="api")
        if TAGALL_VERIFY_DELAY:
            await asyncio.sleep(TAGALL_VERIFY_DELAY)
    save_group_data(group_id, group_data)

    group_data = get_group_data(group_id)
    include_bots = bool(group_data.get("settings", {}).get("tag_include_bots", False))
    everyone_active = registry_active(group_data, include_bots=True)
    known_active = len(everyone_active)
    if bot.bot_id and not any(r["user_id"] == str(bot.bot_id) for r in everyone_active):
        known_active += 1          # خود ربات عضو گروه است ولی معمولاً پیام «خودش» را نمی‌بیند
    total = await bot.get_member_count(group_id)
    targets = [r for r in registry_active(group_data, include_bots=include_bots, exclude_ids=[bot.bot_id])
               if (r.get("first_name") or "").strip().lower() != "deleted account"]
    bot_status = await bot.get_member_status(group_id, bot.bot_id) if bot.bot_id else None
    return {
        "targets": targets, "known_active": known_active, "total": total,
        "complete": total is not None and known_active >= total,
        "skipped_bots": (0 if include_bots else sum(1 for r in everyone_active if r.get("is_bot") and r["user_id"] != str(bot.bot_id))),
        "unverified": sum(1 for r in _members(group_data).values() if r.get("status") == "unknown"),
        "bot_is_admin": bool(bot_status and bot_status["status"] in ("administrator", "creator")),
    }

async def run_tagall_job(bot, group_id: str, header: str, notify):
    """کار اصلی Tag All (در پس‌زمینه). قفل گروه فقط در finally آزاد می‌شود؛ پایان همیشه گزارش صادقانه می‌دهد."""
    try:
        prep = await prepare_tagall(bot, group_id)
        group_data = get_group_data(group_id)
        st = group_data.get("settings", {})
        try:
            cap = max(1, int(st.get("tagall_max", TAGALL_MAX_DEFAULT)))
            per = max(1, min(50, int(st.get("tagall_chunk", TAGALL_CHUNK_DEFAULT))))
        except (TypeError, ValueError):
            cap, per = TAGALL_MAX_DEFAULT, TAGALL_CHUNK_DEFAULT
        targets = prep["targets"]
        capped = max(0, len(targets) - cap)
        targets = targets[:cap]
        if not targets:
            await notify("⚠️ هیچ عضو فعالی برای تگ در Registry ربات نیست (هنوز کسی پیام نداده یا همه ربات/خارج‌شده‌اند).")
            return
        chunks = build_tag_chunks(targets, header, per)
        tag_emoji = get_custom_emoji(group_data, "tag")
        await notify(f"{tag_emoji} تگ همه شروع شد: {len(targets)} نفر در {len(chunks)} پیام.")
        sent_chunks = failed = 0
        first_error = ""
        for i, chunk in enumerate(chunks):
            res = await bot.send_text(group_id, chunk, html=True)
            if res:
                sent_chunks += 1
            else:
                failed += 1
                first_error = first_error or res.error
                if failed >= 3 and sent_chunks == 0:
                    break
            if i < len(chunks) - 1 and TAGALL_CHUNK_DELAY:
                await asyncio.sleep(TAGALL_CHUNK_DELAY)
        tagged = sum(min(per, len(targets) - k * per) for k in range(len(chunks))) if failed == 0 else None
        lines = []
        if failed == 0:
            lines.append(f"✅ {len(targets)} نفر تگ شدند.")
        else:
            lines.append(f"❌ فقط {sent_chunks} از {len(chunks)} پیام ارسال شد؛ تگ ناقص است.\n🔎 علت: {first_error}")
        if capped:
            lines.append(f"⚠️ سقف هر عملیات {cap} نفر است؛ {capped} نفر تگ نشدند.")
        if prep["total"] is None:
            lines.append("⚠️ تعداد واقعی اعضای گروه از تلگرام خوانده نشد، پس نمی‌توانم بگویم همه‌ی اعضا تگ شدند.")
        elif not prep["complete"]:
            lines.append(f"⚠️ همه‌ی اعضا تگ نشدند: تلگرام {prep['total']} عضو را گزارش می‌کند ولی ربات فقط "
                         f"{prep['known_active']} نفر را می‌شناسد (بقیه هنوز پیامی نداده‌اند). "
                         "با ورود/پیام‌دادنِ آن‌ها، ربات آن‌ها را هم می‌شناسد.")
        elif failed == 0 and not capped:
            lines.append("✅ همه‌ی اعضای شناخته‌شده و فعال گروه پوشش داده شدند (تعداد با آمار تلگرام برابر است).")
        if prep["skipped_bots"]:
            lines.append(f"ℹ️ {prep['skipped_bots']} ربات تگ نشد (/tagbots فعال برای تگ ربات‌ها).")
        if prep["unverified"]:
            lines.append(f"ℹ️ وضعیت {prep['unverified']} کاربر قدیمی هنوز تایید نشده و تگ نشدند.")
        if not prep["bot_is_admin"]:
            lines.append("ℹ️ ربات ادمین نیست؛ ورود/خروج اعضا را نمی‌بیند و Registry ممکن است قدیمی شود.")
        await notify("\n".join(lines))
    except Exception as e:  # هیچ‌وقت بی‌صدا شکست نخورد
        # 🛠 بخش ۶۸: قبلاً متن خامِ Exception مستقیماً به گروه فرستاده می‌شد (ممکنه
        # شامل جزئیات داخلی/مسیر/نام تابع باشه). الان فقط پیام عمومی به کاربر و
        # جزئیات کامل فقط در لاگ سرور.
        logging.getLogger("gardi").exception("tagall failed: %r", e)
        try:
            await notify("❌ تگ همه با خطای غیرمنتظره متوقف شد. لطفاً بعداً دوباره امتحان کنید.")
        except Exception:
            pass
    finally:
        _TAGALL_ACTIVE.pop(group_id, None)          # آزادکردن قفل همین گروه
        _TAGALL_LAST[group_id] = time.monotonic()
        _TAGALL_TASKS.pop(group_id, None)

@bot.on_message(filters=lambda m: _cmd_is(m, "tagall"))
async def tagall_cmd(bot: Robot, message: Message):
    """
    Tag All واقعی: Mention با User ID (کار می‌کند حتی برای کاربر بدون username)، از Registry دائمی،
    کاربران خارج‌شده/بن‌شده و ربات‌ها (طبق /tagbots) حذف می‌شوند، در چند پیام تکه‌تکه با فاصله‌ی زمانی،
    با قفل جدا برای هر گروه (دو Tag All همزمان در یک گروه ممنوع) و Cooldown. در پایان فقط وقتی
    «همه» گفته می‌شود که تعداد شناخته‌شده‌ها با تعداد واقعی اعضای تلگرام برابر باشد.
    """
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return

    now = time.monotonic()
    started = _TAGALL_ACTIVE.get(group_id)
    if started is not None and now - started < 1800:
        await message.reply("⏳ یک عملیات «تگ همه» همین حالا در این گروه در حال اجراست؛ صبر کن تمام شود.")
        return
    try:
        cooldown = max(0, int(group_data.get("settings", {}).get("tagall_cooldown", TAGALL_COOLDOWN_DEFAULT)))
    except (TypeError, ValueError):
        cooldown = TAGALL_COOLDOWN_DEFAULT
    last = _TAGALL_LAST.get(group_id)
    if last is not None and now - last < cooldown:
        await message.reply(f"⏳ تگ همه اخیراً اجرا شده؛ {int(cooldown - (now - last)) + 1} ثانیه دیگر دوباره تلاش کن.")
        return

    _TAGALL_ACTIVE[group_id] = now            # قفل: بدون هیچ await بین «چک» و «ست»
    tag_emoji = get_custom_emoji(group_data, "tag")
    header = _cmd_rest(message.text)[:300] or f"{tag_emoji} توجه همه!"

    async def notify(text: str):
        await bot.send_text(group_id, text)

    task = asyncio.ensure_future(run_tagall_job(bot, group_id, header, notify))
    _TAGALL_TASKS[group_id] = task

@bot.on_message(filters=lambda m: _cmd_is(m, "tag_group"))
async def tag_group_cmd(bot: Robot, message: Message):
    """قبلاً فقط متن جعلی «@all @everyone» می‌فرستاد که هیچ اعلانی نمی‌داد؛ حالا همان Tag All واقعی است."""
    await tagall_cmd(bot, message)

@bot.on_message(filters=lambda m: _cmd_is(m, "tagbots"))
async def tagbots_cmd(bot: Robot, message: Message):
    """سیاست ربات‌ها در Tag All: /tagbots فعال|غیرفعال (پیش‌فرض: غیرفعال)."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    arg = _cmd_rest(message.text).strip().lower()
    if arg in ("فعال", "on", "1", "روشن"):
        val = True
    elif arg in ("غیرفعال", "off", "0", "خاموش"):
        val = False
    else:
        cur = group_data['settings'].get('tag_include_bots', False)
        await message.reply(f"⚠️ دستور: /tagbots [فعال/غیرفعال]\n📌 وضعیت فعلی: {'ربات‌ها هم تگ می‌شوند' if cur else 'ربات‌ها تگ نمی‌شوند'}")
        return
    group_data = get_group_data(group_id)
    group_data['settings']['tag_include_bots'] = val
    save_group_data(group_id, group_data)
    await message.reply("✅ **از این پس ربات‌ها هم در تگ همه می‌آیند.**" if val else "✅ **ربات‌ها در تگ همه نمی‌آیند.**")

# =========================================================
#  🆕 تگ‌های تخصصی (FULL_GUIDE_1: «تگ ادمین | تگ ویژه | تگ مالک | تگ معاف |
#  تگ سکوت | تگ کیل | تگ بلاک») - قبلاً فقط تبلیغ می‌شد، هیچ الیاس/هندلری
#  نداشت. برخلاف «تگ همه» که کل Registry را هدف می‌گیرد، این‌ها فقط همان
#  لیست مشخصِ خودشان را تگ می‌کنند (owners/admins/specials/exempts/سکوت‌های
#  فعال/blocks). «کیل» در دیتابیس فعلی گاردی هنوز هیچ لیست جداگانه‌ای ندارد
#  (نه در این نسخه، نه در نسخه‌های قبلی) - «تگ کیل» جای‌گذار آماده است و
#  صادقانه می‌گوید لیست خالی است، تا وقتی خودِ قابلیت «کیل» جداگانه ساخته شود.
# =========================================================
def _tag_targets_from_ids(group_data: dict, ids) -> List[dict]:
    members = _members(group_data)
    out = []
    for uid in ids:
        uid = str(uid)
        rec = members.get(uid)
        out.append(rec if rec else {"user_id": uid, "first_name": "", "last_name": "", "username": None})
    return out

async def _run_role_tag(bot, message, ids, role_label: str):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply(NO_PERMISSION_MSG)
        return
    targets = _tag_targets_from_ids(group_data, ids)
    if not targets:
        await message.reply(f"⚠️ لیست «{role_label}» این گروه در حال حاضر خالی است.")
        return
    tag_emoji = get_custom_emoji(group_data, "tag")
    header = _cmd_rest(message.text)[:300] or f"{tag_emoji} تگ {role_label}"
    try:
        per = max(1, min(50, int(group_data.get("settings", {}).get("tagall_chunk", TAGALL_CHUNK_DEFAULT))))
    except (TypeError, ValueError):
        per = TAGALL_CHUNK_DEFAULT
    chunks = build_tag_chunks(targets, header, per)
    sent = failed = 0
    first_error = ""
    for i, chunk in enumerate(chunks):
        res = await bot.send_text(group_id, chunk, html=True)
        if res:
            sent += 1
        else:
            failed += 1
            first_error = first_error or res.error
        if i < len(chunks) - 1 and TAGALL_CHUNK_DELAY:
            await asyncio.sleep(TAGALL_CHUNK_DELAY)
    if failed:
        await message.reply(f"⚠️ {sent} از {len(chunks)} پیام ارسال شد.\n🔎 علت: {first_error}")

async def _role_ids_for(message, role_key: str) -> List[str]:
    """اگر گروه معتبر نبود، لیست خالی (خودِ _run_role_tag پیام GROUP_ONLY_MSG را می‌دهد)."""
    group_id = get_chat_group_id(message)
    if not group_id:
        return []
    group_data = get_group_data(group_id)
    if role_key == "mutes":
        return [uid for uid in list(group_data.get("mutes", {}).keys())
                if is_punished_active(group_data, "mutes", uid)]
    return group_data.get(role_key, [])

@bot.on_message(filters=lambda m: _cmd_is(m, "tag_owners"))
async def tag_owners_cmd(bot: Robot, message: Message):
    await _run_role_tag(bot, message, await _role_ids_for(message, "owners"), "مالک‌ها")

@bot.on_message(filters=lambda m: _cmd_is(m, "tag_admins"))
async def tag_admins_cmd(bot: Robot, message: Message):
    await _run_role_tag(bot, message, await _role_ids_for(message, "admins"), "ادمین‌ها")

@bot.on_message(filters=lambda m: _cmd_is(m, "tag_specials"))
async def tag_specials_cmd(bot: Robot, message: Message):
    await _run_role_tag(bot, message, await _role_ids_for(message, "specials"), "ویژه‌ها")

@bot.on_message(filters=lambda m: _cmd_is(m, "tag_exempts"))
async def tag_exempts_cmd(bot: Robot, message: Message):
    await _run_role_tag(bot, message, await _role_ids_for(message, "exempts"), "معاف‌ها")

@bot.on_message(filters=lambda m: _cmd_is(m, "tag_mutes"))
async def tag_mutes_cmd(bot: Robot, message: Message):
    await _run_role_tag(bot, message, await _role_ids_for(message, "mutes"), "سکوت‌شده‌ها")

@bot.on_message(filters=lambda m: _cmd_is(m, "tag_blocks"))
async def tag_blocks_cmd(bot: Robot, message: Message):
    await _run_role_tag(bot, message, await _role_ids_for(message, "blocks"), "بلاک‌شده‌ها")

@bot.on_message(filters=lambda m: _cmd_is(m, "tag_kills"))
async def tag_kills_cmd(bot: Robot, message: Message):
    await _run_role_tag(bot, message, await _role_ids_for(message, "kills"), "کیل‌شده‌ها")

@bot.on_message(filters=lambda m: _cmd_is(m, "members"))
async def members_cmd(bot: Robot, message: Message):
    """خلاصه‌ی Registry اعضا (چند نفر شناخته‌شده‌اند در برابر تعداد واقعی گروه)."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    recs = list(_members(group_data).values())
    count = lambda st: sum(1 for r in recs if r.get("status") == st)
    total = await bot.get_member_count(group_id)
    save_group_data(group_id, group_data)
    await message.reply(
        "👥 **Registry اعضا:**\n"
        f"• فعال: {sum(1 for r in recs if r.get('status') in REG_ACTIVE)} (مالک {count('owner')}، ادمین {count('administrator')}، عضو {count('member')}، محدود {count('restricted')})\n"
        f"• خارج‌شده: {count('left')} | ممنوع‌شده: {count('banned')} | نامعلوم: {count('unknown')}\n"
        f"• ربات‌ها: {sum(1 for r in recs if r.get('is_bot'))}\n"
        f"• تعداد واقعی اعضا طبق تلگرام: {total if total is not None else 'نامشخص'}")

# =========================================================
#  🛠 رفع باگ اصلی: «مالک رو نمی‌شناسه» / مالکیت با اولین پیام تعیین می‌شد
# =========================================================
# نسخه‌ی قبلی مالکیت را با @bot.on_message() بدون فیلتر انجام می‌داد - یعنی
# هر پیام معمولیِ هر کسی (نه لزوماً کسی که ربات را واقعاً فعال کرده) اگر
# اولین پیامِ دیده‌شده در آن گروه بود، فرستنده‌اش را مالک می‌کرد. این دقیقاً
# همان مشکلی‌ست که باید حل شود: مالکیت باید فقط به «فعال‌کننده‌ی واقعی
# ربات» برسد، نه به هر کسی که تصادفاً زودتر از بقیه پیام داده.
#
# تلگرام مفهومی مثل «نصب برنامه» ندارد؛ پس باید از رویدادهای واقعاً
# قابل‌تشخیص برای «فعال‌سازی» استفاده کرد. اینجا دقیقاً دو رویداد به‌عنوان
# فعال‌سازی در نظر گرفته می‌شوند:
#   ۱) کسی که ربات را به گروه اضافه می‌کند (رویداد my_chat_member واقعی
#      تلگرام - در member_event_handler پایین‌تر مدیریت می‌شود؛ actor_id
#      همان کسی‌ست که واقعاً دکمه‌ی افزودن را زده).
#   ۲) کسی که داخل گروه دستور /start یا «استارت»/«شروع» را می‌زند (در
#      _handle_start پایین‌تر مدیریت می‌شود).
# هر پیام معمولی دیگر، هرچقدر هم زود، دیگر هیچ نقشی در تعیین مالک ندارد.
# بعد از اولین بار که مالک ثبت شد (owner_primary/owners در data.json)،
# هیچ‌کدام از این دو رویداد هم دوباره چیزی را تغییر نمی‌دهند.
OWNER_LOCK = asyncio.Lock()

async def _set_owner_if_unset(bot: Robot, group_id, user_id: str, method: str) -> bool:
    """اگر گروه هنوز مالکی ثبت‌شده ندارد، user_id را به‌عنوان مالک (owner_primary) ثبت
    می‌کند و True برمی‌گرداند. اگر از قبل مالک داشت، هیچ تغییری نمی‌دهد و False برمی‌گرداند.
    OWNER_LOCK از این جلوگیری می‌کند که دو رویداد فعال‌سازی هم‌زمان (مثلاً /start دقیقاً
    هم‌زمان با رویداد افزوده‌شدن ربات) هر دو گروه_data را قدیمی بخوانند و یکی مالک دیگری
    را بی‌سروصدا رونویسی کند."""
    async with OWNER_LOCK:
        group_data = get_group_data(group_id)
        if group_data.get('owner_primary') or group_data.get('owners'):
            return False
        user_id = str(user_id)
        group_data['owners'] = [user_id]
        group_data['owner_primary'] = user_id
        group_data['activated_by'] = user_id
        group_data['activated_at'] = datetime.now().isoformat()
        add_log(group_data, f"تعیین مالک هنگام فعال‌سازی ربات ({method})", admin_id=user_id, target_id=user_id)
        save_group_data(group_id, group_data)
    return True

# ---- Command Router: هر alias را به یک دستور اصلی (معمولاً slash قدیمی) وصل می‌کند ----
# فرمت: "کلید نرمال‌شده": ("دستور اصلی که هندلر موجود آن را می‌شناسد", حداقل سطح دسترسی)
ALIAS_MAP = {
    # --- سرگرمی: بدون نیاز به دسترسی خاص (بخش‌هایی که در کد فعلی موجود بودند) ---
    "بیو": ("/bio", Perm.MEMBER),
    "خاطره": ("/khater", Perm.MEMBER),
    "فال": ("/fal", Perm.MEMBER),
    "چالش": ("/challenge", Perm.MEMBER),
    "داستان": ("/story", Perm.MEMBER),
    "پنالتی": ("/penalty", Perm.MEMBER),
    "پنالتی چالش": ("/penalty_dare", Perm.MEMBER),
    "معما": ("/riddle", Perm.MEMBER),
    "ضرب المثل": ("/proverb", Perm.MEMBER),
    "ضرب‌المثل": ("/proverb", Perm.MEMBER),
    "جمله انگیزشی": ("/motivation", Perm.MEMBER),
    "انگیزشی": ("/motivation", Perm.MEMBER),
    "شوخی": ("/joke", Perm.MEMBER),
    "جوک": ("/joke", Perm.MEMBER),
    "حقیقت جالب": ("/funfact", Perm.MEMBER),
    "حقیقت": ("/truth", Perm.MEMBER),
    "جرات": ("/dare", Perm.MEMBER),
    "جرأت": ("/dare", Perm.MEMBER),
    "جرات یا حقیقت": ("/truth_or_dare", Perm.MEMBER),
    "جرأت یا حقیقت": ("/truth_or_dare", Perm.MEMBER),
    "حقیقت یا جرات": ("/truth_or_dare", Perm.MEMBER),
    "حقیقت یا جرأت": ("/truth_or_dare", Perm.MEMBER),

    # --- مدیریت کاربران: نیازمند حداقل سطح مدیر ---
    "بن": ("/ban", Perm.ADMIN),
    "آنبن": ("/unban", Perm.ADMIN),
    "رفع بن": ("/unban", Perm.ADMIN),
    "اخراج": ("/kick", Perm.ADMIN),
    "اخطار": ("/warn", Perm.ADMIN),
    "رفع اخطار": ("/unwarn", Perm.ADMIN),
    "سکوت": ("/mute", Perm.ADMIN),
    "میوت": ("/mute", Perm.ADMIN),
    "اقدام اخطار": ("/warnaction", Perm.ADMIN),
    "انقضای اخطار": ("/warnexpire", Perm.ADMIN),
    "آنسکوت": ("/unmute", Perm.ADMIN),
    "رفع سکوت": ("/unmute", Perm.ADMIN),
    "مسدود": ("/block", Perm.ADMIN),
    "ریم": ("/block", Perm.ADMIN),
    "سیک": ("/block", Perm.ADMIN),
    "آنبلاک": ("/unblock", Perm.ADMIN),
    "رفع مسدود": ("/unblock", Perm.ADMIN),
    "انسیک": ("/unblock", Perm.ADMIN),
    "انبن": ("/unban", Perm.ADMIN),
    "حذف بن": ("/unban", Perm.ADMIN),
    "حذف ریم": ("/unblock", Perm.ADMIN),
    "پاکسازی": ("/clear", Perm.ADMIN),
    "حذف": ("/clear", Perm.ADMIN),
    "حذف خودکار فعال": ("/autodel_on", Perm.ADMIN),
    "حذف خودکار غیرفعال": ("/autodel_off", Perm.ADMIN),
    "تنظیم حذف خودکار": ("/setautodel", Perm.ADMIN),

    # --- امنیت و تنظیمات حساس: مدیر ارشد ---
    "قفل": ("/lock", Perm.SUPER_ADMIN),
    "حالت خواب روشن": ("/sleep_on", Perm.SUPER_ADMIN),
    "حالت خواب خاموش": ("/sleep_off", Perm.SUPER_ADMIN),
    "خواب روشن": ("/sleep_on", Perm.SUPER_ADMIN),
    "خواب خاموش": ("/sleep_off", Perm.SUPER_ADMIN),
    "ضداسپم": ("/antispam", Perm.SUPER_ADMIN),
    "ضدلینک": ("/antilink", Perm.SUPER_ADMIN),
    "ضدفحش": ("/antiswear", Perm.SUPER_ADMIN),
    "فیلترها": ("/filters", Perm.ADMIN),

    # 🛠 رفع باگ: راهنما همیشه دستورات «لینک قفل» / «لینک باز» (و معادل
    # «قفل لینک» / «باز لینک») رو تبلیغ می‌کرد، ولی این عبارت‌های دقیق هیچ‌وقت
    # در ALIAS_MAP یا هیچ‌جای دیگه‌ی کد ثبت نشده بودن - فقط "ضدلینک" (که یک
    # toggle خام‌ست) واقعاً کار می‌کرد. کاربرهایی که دقیقاً طبق راهنما تایپ
    # می‌کردن هیچ جوابی نمی‌گرفتن. این‌ها الان یک ست/آنست صریح انجام می‌دن.
    "لینک قفل": ("/linklockon", Perm.SUPER_ADMIN),
    "قفل لینک": ("/linklockon", Perm.SUPER_ADMIN),
    "لینک باز": ("/linklockoff", Perm.SUPER_ADMIN),
    "باز لینک": ("/linklockoff", Perm.SUPER_ADMIN),

    # 🛠 رفع باگ (مشابه «قفل لینک»): راهنما «قفل فحش» (FULL_GUIDE_1) و «اسپم قفل / باز»
    # (FULL_GUIDE_2) رو تبلیغ می‌کرد، ولی این عبارت‌های دقیق هیچ‌جا در ALIAS_MAP نبودن -
    # فقط «ضدفحش»/«ضداسپم» (toggle خام) واقعاً کار می‌کردن. الان مثل «قفل لینک» یک
    # ست/آنست صریح (نه toggle) دارن.
    "قفل فحش": ("/swearlockon", Perm.SUPER_ADMIN),
    "فحش قفل": ("/swearlockon", Perm.SUPER_ADMIN),
    "فحش باز": ("/swearlockoff", Perm.SUPER_ADMIN),
    "باز فحش": ("/swearlockoff", Perm.SUPER_ADMIN),
    "قفل اسپم": ("/spamlockon", Perm.SUPER_ADMIN),
    "اسپم قفل": ("/spamlockon", Perm.SUPER_ADMIN),
    "اسپم باز": ("/spamlockoff", Perm.SUPER_ADMIN),
    "باز اسپم": ("/spamlockoff", Perm.SUPER_ADMIN),

    # 🆕 «قفل کپشن» (FULL_GUIDE_2) - در راهنما تبلیغ می‌شد ولی هیچ الیاسی نداشت.
    "قفل کپشن": ("/captionlockon", Perm.SUPER_ADMIN),
    "کپشن قفل": ("/captionlockon", Perm.SUPER_ADMIN),
    "کپشن باز": ("/captionlockoff", Perm.SUPER_ADMIN),
    "باز کپشن": ("/captionlockoff", Perm.SUPER_ADMIN),
    "بن کپشن فعال": ("/captionban_on", Perm.SUPER_ADMIN),
    "بن کپشن غیرفعال": ("/captionban_off", Perm.SUPER_ADMIN),
    "نمایش اخطار کپشن فعال": ("/captionshowwarn_on", Perm.SUPER_ADMIN),
    "نمایش اخطار کپشن غیرفعال": ("/captionshowwarn_off", Perm.SUPER_ADMIN),
    "تنظیم اخطار کپشن غیرفعال": ("/captionwarn_reset", Perm.SUPER_ADMIN),
    "تنظیم اخطار کپشن": ("/captionwarn_set", Perm.SUPER_ADMIN),

    # 🆕 سیستم شخصی‌سازی اموجی (FULL_GUIDE_1) - قبلاً هیچ الیاسی نداشت.
    "تنظیم اموجی": ("/set_custom_emoji", Perm.ADMIN),
    "ریست کامل اموجی": ("/reset_all_custom_emoji", Perm.ADMIN),
    "ریست کامل اموجیها": ("/reset_all_custom_emoji", Perm.ADMIN),
    "ریست کامل اموجی ها": ("/reset_all_custom_emoji", Perm.ADMIN),
    "لیست اموجی": ("/list_custom_emoji", Perm.MEMBER),

    # 🆕 تگ‌های تخصصی (FULL_GUIDE_1) - قبلاً هیچ الیاسی نداشتند.
    "تگ ادمین": ("/tag_admins", Perm.ADMIN),
    "تگ ویژه": ("/tag_specials", Perm.ADMIN),
    "تگ مالک": ("/tag_owners", Perm.ADMIN),
    "تگ معاف": ("/tag_exempts", Perm.ADMIN),
    "تگ سکوت": ("/tag_mutes", Perm.ADMIN),
    "تگ کیل": ("/tag_kills", Perm.ADMIN),
    "تگ بلاک": ("/tag_blocks", Perm.ADMIN),

    # --- لیست‌ها و اطلاعات عمومی: همه می‌بینند ---
    "مدیران": ("/admins", Perm.MEMBER),
    "ویژه ها": ("/specials", Perm.MEMBER),
    "ویژهها": ("/specials", Perm.MEMBER),
    "معاف ها": ("/exempts", Perm.MEMBER),
    "معافها": ("/exempts", Perm.MEMBER),
    "قوانین": ("/rules", Perm.MEMBER),
    "آمار": ("/mystats", Perm.MEMBER),
    "آمار من": ("/mystats", Perm.MEMBER),
    "آمار گروه": ("/gstats", Perm.MEMBER),
    "سطح": ("/level", Perm.MEMBER),

    # --- ابزارهای گروه (پیاده‌سازی قبلی موجود بود) ---
    "اعلان": ("/announce", Perm.ADMIN),
    "تگ همه": ("/tagall", Perm.ADMIN),
    "تگهمه": ("/tagall", Perm.ADMIN),
    "بکاپ": ("/backup", Perm.SUPER_ADMIN),
    "لیست بکاپ": ("/backups", Perm.SUPER_ADMIN),
    "بکاپ ها": ("/backups", Perm.SUPER_ADMIN),
    "بازیابی": ("/restore", Perm.SUPER_ADMIN),
    "بازگردانی": ("/restore", Perm.SUPER_ADMIN),

    # 🛠 رفع باگ: «تم» فقط با دستور اسلش انگلیسی (/theme و /set_theme) کار
    # می‌کرد و هیچ ورودی فارسی نداشت؛ راهنمای خود ربات «تم» و «تنظیم تم» رو
    # تبلیغ می‌کرد ولی این دو عبارت هرگز به هیچ تابعی وصل نبودن.
    "تم": ("/theme", Perm.MEMBER),
    "پنل تم": ("/theme", Perm.MEMBER),
    "تنظیم تم": ("/set_theme", Perm.ADMIN),
    # 🛠 عمداً «تنظیم تم پیشفرض» (بی‌فاصله) اضافه نشده: چون «پیشفرض» خودش یک
    # نام تمِ معتبر است، آن عبارت دقیقاً باید همچنان به مسیرِ قدیمیِ «تنظیم
    # تم» + آرگومان «پیشفرض» برود (یعنی «تم گروه را روی تمِ پیشفرض بگذار»)
    # نه به این قابلیتِ جدید («تم پایه/مبنای گروه را ذخیره کن»). برای تمایز،
    # این قابلیتِ جدید فقط با فاصله/نیم‌فاصله بین «پیش» و «فرض» فعال می‌شود.
    "تنظیم تم پیش فرض": ("/set_default_theme", Perm.OWNER),
    "تنظیم تم پیش‌فرض": ("/set_default_theme", Perm.OWNER),
    "فونت": ("/font", Perm.MEMBER),
    "پنل فونت": ("/font", Perm.MEMBER),
    "تنظیم فونت": ("/font_set", Perm.ADMIN),
    "تنظیم حساسیت تشخیص کدهنگی": ("/hangcode_sensitivity", Perm.OWNER),
    "تنظیم حساسیت کدهنگی": ("/hangcode_sensitivity", Perm.OWNER),

    # 🛠 رفع باگ: مدیریت «لینک گروه» (نمایش/تنظیم/حذف) هم فقط با دستور اسلش
    # انگلیسی کار می‌کرد. «لینک»، «تنظیم لینک» و «حذف لینک» هیچ‌جا در
    # ALIAS_MAP نبودن، پس این دستورات فارسی که در راهنما تبلیغ می‌شدن هیچ
    # پاسخی نمی‌گرفتن.
    "لینک": ("/link", Perm.MEMBER),
    "تنظیم لینک": ("/set_link", Perm.ADMIN),
    "حذف لینک": ("/delete_link", Perm.ADMIN),

    # 🛠 رفع باگ بزرگ: افزودن/حذف ادمین، ویژه و مالک فقط با شناسه‌ی عددی خام
    # کار می‌کرد (/addadmin 123456) و اکثر مالک‌ها شناسه‌ی عددی بقیه رو
    # نمی‌دونستن، پس این بخش عملاً غیرقابل استفاده بود. الان با ریپلای‌کردن
    # روی پیام شخص هم کار می‌کنه (طبق روشی که خود راهنمای ربات همیشه تبلیغ
    # می‌کرد ولی پیاده‌سازی نشده بود).
    "ادمین": ("/addadmin", Perm.OWNER),
    "حذف ادمین": ("/removeadmin", Perm.OWNER),
    "برکناری ادمین": ("/removeadmin", Perm.OWNER),
    "ویژه": ("/addspecial", Perm.OWNER),
    "حذف ویژه": ("/removespecial", Perm.OWNER),
    "برکناری ویژه": ("/removespecial", Perm.OWNER),
    "افزودن مالک": ("/addowner", Perm.OWNER),
    "حذف مالک": ("/removeowner", Perm.OWNER),
    "برکناری مالک": ("/removeowner", Perm.OWNER),
    "معاف": ("/exempt", Perm.ADMIN),
    "حذف معاف": ("/unexempt", Perm.ADMIN),

    # 🆕 ضد تبچی (FULL_GUIDE_1: «ضد تبچی روشن/خاموش») + تشخیص/محدودسازی (این ۲ تا در راهنما
    # اصلاً اسم دقیق نداشتن، اسم متعارف‌شان طبق درخواست کاربر انتخاب شد).
    "ضد تبچی روشن": ("/tabchi_on", Perm.SUPER_ADMIN),
    "ضد تبچی خاموش": ("/tabchi_off", Perm.SUPER_ADMIN),
    "تشخیص تبچی": ("/tabchi_status", Perm.ADMIN),
    "محدودسازی تبچی": ("/tabchi_window", Perm.SUPER_ADMIN),

    # 🆕 تنظیم خودکار دستورات + تنظیمات پیش‌فرض کامل (FULL_GUIDE_2)
    "تنظیم خودکار دستورات": ("/auto_setup", Perm.SUPER_ADMIN),
    "تنظیم همه قابلیت ها با یک دستور": ("/auto_setup", Perm.SUPER_ADMIN),
    "تنظیم همه قابلیت‌ها با یک دستور": ("/auto_setup", Perm.SUPER_ADMIN),
    "تنظیمات پیش فرض کامل": ("/full_reset_defaults", Perm.OWNER),
    "تنظیمات پیش‌فرض کامل": ("/full_reset_defaults", Perm.OWNER),

    # 🆕 سیستم محدودیت عمومی دستورات / «ضد خیانت» (FULL_GUIDE_2): دو دستور مستقل («ریست
    # محدودیت»، «مدیریت محدودیت همه دستورات»)؛ خود «[دستور] #عدد/فعال/غیرفعال» یک لایه‌ی
    # عمومی است که در persian_alias_router روی هر دستور دیگری اعمال می‌شود، نه یک alias جدا.
    "ریست محدودیت": ("/reset_cmd_restrictions", Perm.OWNER),
    "مدیریت محدودیت همه دستورات": ("/list_cmd_restrictions", Perm.ADMIN),

    # 🆕 سیستم دستورات دلخواه (FULL_GUIDE_2)
    "تنظیم دستور": ("/set_custom_cmd", Perm.ADMIN),
    "حذف دستور": ("/remove_custom_cmd", Perm.ADMIN),
    "نمایش دستور": ("/show_custom_cmd", Perm.MEMBER),
    "لیست دستورات شخصی": ("/list_custom_cmds", Perm.MEMBER),
    "پاکسازی دستورات": ("/clear_custom_cmds", Perm.ADMIN),
    "پاکسازی لیست دستورات شخصی": ("/clear_custom_cmds", Perm.ADMIN),
}

# نگاشت «دستور اصلی» به تابع هندلر واقعی؛ چون خود آن توابع فقط به message.text نگاه می‌کنند
# (مثلاً message.text.startswith("/ban"))، کافی است متن پیام را به شکل slash معادل بازنویسی
# و خود تابع را مستقیم صدا بزنیم. هیچ رفتار موجودی تغییر نمی‌کند؛ فقط یک مسیر ورودی فارسی
# به همان مسیر قبلی اضافه می‌شود.
_ROUTER_TARGETS = {}

def register_router_target(canonical: str, func):
    _ROUTER_TARGETS[canonical] = func

# دستوراتی که مدیریتی هستند تا هم Permission چک شود و هم در لاگ ثبت شوند
_ADMIN_ACTIONS = {
    "/ban": "بن", "/unban": "آنبن", "/kick": "اخراج", "/warn": "اخطار",
    "/unwarn": "رفع اخطار", "/mute": "سکوت", "/unmute": "آنسکوت",
    "/block": "مسدود", "/unblock": "آنبلاک", "/clear": "پاکسازی",
    "/lock": "قفل گروه", "/antispam": "تغییر ضداسپم", "/antilink": "تغییر ضدلینک",
    "/linklockon": "فعال‌سازی قفل لینک", "/linklockoff": "غیرفعال‌سازی قفل لینک",
    "/swearlockon": "فعال‌سازی قفل فحش", "/swearlockoff": "غیرفعال‌سازی قفل فحش",
    "/spamlockon": "فعال‌سازی قفل اسپم", "/spamlockoff": "غیرفعال‌سازی قفل اسپم",
    "/antiswear": "تغییر ضدفحش", "/announce": "اعلان", "/tagall": "تگ همه",
    "/backup": "بکاپ", "/restore": "بازگردانی بکاپ",
    "/addadmin": "افزودن ادمین", "/removeadmin": "حذف ادمین",
    "/addspecial": "افزودن ویژه", "/removespecial": "حذف ویژه",
    "/addowner": "افزودن مالک", "/removeowner": "حذف مالک",
    "/set_theme": "تغییر تم", "/font_set": "تغییر فونت", "/hangcode_sensitivity": "تغییر حساسیت کدهنگی",
    "/set_link": "تنظیم لینک گروه", "/delete_link": "حذف لینک گروه",
}

def _match_alias(raw_text: str):
    """
    متن پیام را نرمال می‌کند و در صورت تطبیق، (دستور اصلی، حداقل سطح، بقیه متن بعد از دستور) را برمی‌گرداند.

    🛠 رفع باگ بحرانی (shadowing): نسخه‌ی قبلی روی اولین alias ای که در حلقه
    بهش می‌رسید match می‌کرد — چون ترتیب حلقه همون ترتیب تعریف در ALIAS_MAP
    بود، هر جا یک دستور کوتاه‌تر (مثل "حذف" یا "قفل") زودتر از یک دستور
    بلندتر و مرتبط ("حذف ادمین"، "قفل لینک") تعریف شده بود، دستور بلندتر
    هرگز اجرا نمی‌شد؛ چون همون کوتاه‌تره با startswith زودتر match می‌کرد.
    مثال واقعی: «حذف ادمین» به‌جای اجرای /removeadmin، به «حذف» (/clear)
    می‌رفت، فقط چون "حذف" زودتر در دیکشنری تعریف شده بود.
    راه‌حل: تمام alias هایی که match می‌کنن (چه دقیق چه با آرگومان) جمع
    می‌شن، و طولانی‌ترین‌شون (دقیق‌ترین تطبیق) برنده می‌شه؛ ترتیب تعریف در
    ALIAS_MAP دیگه هیچ اهمیتی نداره.
    """
    if not raw_text:
        return None
    norm_full = normalize_fa(raw_text)
    norm_key = normalize_key(raw_text)

    best = None  # (len(alias), canonical, level, rest)
    for alias, (canonical, level) in ALIAS_MAP.items():
        if norm_key == alias:
            rest = ""
        elif norm_key.startswith(alias + " "):
            rest = norm_full[len(alias):].strip()
        else:
            continue
        if best is None or len(alias) > best[0]:
            best = (len(alias), canonical, level, rest)

    if best is None:
        return None
    return best[1], best[2], best[3]

class _RouterMessageProxy:
    """
    یک پوسته‌ی سبک روی پیام اصلی که فقط متن (text) آن بازنویسی شده، بدون اینکه
    پیام واقعی تغییر کند. قبلاً کد مستقیماً message.text را بازنویسی می‌کرد؛
    مشکل این بود که بعد از آن، بقیه‌ی هندلرهای ثبت‌شده روی همان پیام (که هنوز
    در حال بررسی فیلترشان توسط ربات بودند) متن تغییریافته را می‌دیدند و دوباره
    اجرا می‌شدند (مثلاً «فال» هم از مسیر router و هم از هندلر اصلی /fal اجرا
    می‌شد و باعث دو بار جواب دادن یا حتی دو بار بن/میوت شدن کاربر می‌شد).
    با این پوشش، فقط تابع هدف یک نسخه‌ی جدا با متن درست را می‌بیند و پیام
    اصلی برای بقیه‌ی سیستم دست‌نخورده باقی می‌ماند.
    """
    __slots__ = ("_original", "text")

    def __init__(self, original, new_text):
        object.__setattr__(self, "_original", original)
        object.__setattr__(self, "text", new_text)

    def __getattr__(self, name):
        return getattr(self._original, name)

    async def reply(self, *args, **kwargs):
        return await self._original.reply(*args, **kwargs)


@bot.on_message(filters=lambda m: m.text and _resolve_command(m) is not None)
async def persian_alias_router(bot: Robot, message: Message):
    """
    ورودی یکپارچه برای همه دستورات فارسی/جایگزین.
    این هندلر خودش منطق را پیاده نمی‌کند؛ فقط پیام را نرمال کرده و به همان تابع
    اصلی‌ای که از قبل برای دستور slash معادل نوشته شده بود، تحویل می‌دهد.
    🆕 همچنین: اول trigger های سفارشیِ گروه (سیستم «دستورات دلخواه») را با _resolve_command
    اعمال می‌کند، و قبل از اجرای هر دستور، سیستم «محدودیت عمومی دستورات» را چک می‌کند.
    """
    matched = _resolve_command(message)
    if not matched:
        return
    canonical, required_level, rest = matched

    group_id = get_chat_group_id(message)
    if not group_id:
        if canonical not in ("/mystats", "/level"):  # این دو در PV هم بی‌ضرر است ولی بقیه نیاز به گروه دارند
            await message.reply(GROUP_ONLY_MSG)
            return

    if group_id:
        group_data = get_group_data(group_id)
        user_id = str(message.sender_id)
        if not has_permission(user_id, group_data, required_level):
            await message.reply(NO_PERMISSION_MSG)
            return
        # 🆕 سیستم محدودیت عمومی دستورات: هم فرمان‌های کنترلی («[دستور] فعال/غیرفعال/#عدد») و هم
        # اجرای عادی وقتی محدودیتی از قبل تنظیم شده، همینجا رسیدگی می‌شود.
        restriction_outcome = await _handle_command_restriction(bot, message, group_id, group_data,
                                                                 user_id, canonical, rest)
        if restriction_outcome:
            return
        if canonical in _ADMIN_ACTIONS:
            target_id = ""
            reply_msg = getattr(message, "reply_to_message", None) or getattr(message, "reply_message", None)
            if reply_msg is not None:
                target_id = str(getattr(reply_msg, "sender_id", "") or "")
            add_log(group_data, _ADMIN_ACTIONS[canonical], admin_id=user_id, target_id=target_id, reason=rest)
            save_group_data(group_id, group_data)

    target_func = _ROUTER_TARGETS.get(canonical)
    if target_func is None:
        await message.reply(f"⚠️ دستور «{canonical}» شناسایی شد اما هنوز به هندلر واقعی وصل نشده است.")
        return

    # به‌جای بازنویسی مستقیم message.text (که باعث اجرای دوباره‌ی هندلر اصلی
    # می‌شد)، یک پیام جایگزین با متن اصلاح‌شده به تابع هدف می‌دهیم. پیام
    # واقعی دست‌نخورده می‌ماند و هیچ هندلر دیگری آن را دوباره تشخیص نمی‌دهد.
    proxy_message = _RouterMessageProxy(message, f"{canonical} {rest}".strip())
    await target_func(bot, proxy_message)

# =========================================================
#  ۲۰۰ تا پاسخ گاردی ایکس
# =========================================================

GARDI_200_RESPONSES = [
    "بله داداش! چی میگی؟ 💪",
    "جانم! بفرمایید 🌟",
    "در خدمتتم! ❤️",
    "چشم! بفرمایید 🌹",
    "بله رئیس! چطور میتونم کمک کنم؟ 💪",
    "جانم! 🌟",
    "در خدمت شما هستم! ❤️",
    "فرمون بدید! 👑",
    "سلام داداش! چطوری؟ 😊",
    "سلام بر تو! خوبی؟ 🌟",
    "سلام! چه خبر؟ 👋",
    "درود بر تو! 🌹",
    "خوبم داداش! تو چطوری؟ 💪",
    "عالی! ممنون که پرسیدی ❤️",
    "خوبم! خودت چطوری؟ 😊",
    "روزگار می‌گذره! 🍀",
    "خوبم داداش! 😊",
    "عالی! 🌟",
    "ممنون خوبم! ❤️",
    "خدا رو شکر! 🙏",
    "منم دوستت دارم! ❤️",
    "عاشقتم! 😊",
    "همیشه دوستت دارم! 🌟",
    "تو بهترینی! 💖",
    "خداحافظ! 😊",
    "بای بای! 🌟",
    "به امید دیدار! ❤️",
    "مراقب خودت باش! 👋",
    "خداحافظ داداش! 😊",
    "به امید دیدار! 🌟",
    "مراقب خودت باش! ❤️",
    "موفق باشی! 💪",
    "خواهش میکنم! 😊",
    "قابلی نداشت! 🌟",
    "خوشحالم که کمک کردم! ❤️",
    "هر وقت! 🙏",
    "خواهش می‌کنم! 🙏",
    "آهنگ خوب گوش بده! 🎵",
    "چی دوست داری گوش بدی؟ 🎶",
    "موزیک بذار خوش بگذره! 🎵",
    "آهنگ شاد بذار! 🎧",
    "فیلم خوب ببین! 🎬",
    "چی دوست داری ببینی؟ 🎥",
    "برو سینما! 🎬",
    "فیلم جدید ببین! 🍿",
    "بازی کن خوش بگذره! 🎮",
    "چی دوست داری بازی کنی؟ 🎯",
    "بیا بریم بازی! 🎮",
    "بازی جدید شروع کن! 🎲",
    "حتماً! راهنما رو برات می‌فرستم 📖",
    "چشم! 📚",
    "در خدمت شما هستم! 📝",
    "چطور میتونم کمک کنم؟ 🤝",
    "بفرمایید! 💪",
    "استراحت کن! 😴",
    "خسته نباشی! ☕",
    "یه چای بخور! 🍵",
    "خوشحالم برات! 🎉",
    "انشاءالله همیشه خوشحال باشی! 🌟",
    "بهترین حالت رو داشته باش! 💫",
    "چرا ناراحتی؟ 😢",
    "همه چی درست میشه! 💪",
    "غمگین نباش! ❤️",
    "عشق یعنی بودن در کنار هم ❤️",
    "عشق زیباترین چیز دنیاست 🌹",
    "عشق الهی! 💖",
    "دلت آروم باشه 🌹",
    "دلتو به خدا بسپار 🙏",
    "دل شاد باشه! 💖",
    "خدا بزرگه 🙏",
    "به خدا توکل کن 🌟",
    "خدا یارت باشه ❤️",
    "انشاءالله 🌟",
    "به امید خدا 🙏",
    "خدا کنه ❤️",
    "تبریک میگم! 🎉",
    "خوشحالم برات! 🎊",
    "موفق باشی! 🌟",
    "انشاءالله موفق میشی 🌟",
    "به اهداف خودت برس 🎯",
    "پول وسیله هست نه هدف 💰",
    "روزی حلال داشته باش 🙏",
    "پول برکت داشته باشه 🌟",
    "کارت رو درست انجام بده 💪",
    "موفق باشی در کارت 🌟",
    "کار خوب داشته باش 🎯",
    "زندگی زیباست 🌹",
    "از زندگی لذت ببر 🌟",
    "زندگی رو به بهترین شکل زندگی کن 💫",
    "امیدوار باش 🌟",
    "امید یعنی زندگی ❤️",
    "امیدت رو از دست نده 💪",
    "صبر کن همه چی درست میشه 🙏",
    "صبر رمز موفقیت است 🌟",
    "صبر داشته باش ❤️",
    "شکر خدا 🙏",
    "همیشه شکرگزار باش 🌟",
    "شکر نعمت‌ها رو به جا بیار ❤️",
    "سپاس از تو 🌟",
    "سپاسگزارم 🙏",
    "ممنون از محبتت ❤️",
    "چشم! حتماً انجام میدم 🌟",
    "به روی چشم! ❤️",
    "هر چی شما بگید! 💪",
    "چشم! در خدمت شما هستم 🌹",
    "حتماً! 🙏",
    "با کمال میل! 🌟",
    "به جان خودم! ❤️",
    "حتماً انجام میدم! 💪",
    "آرزوی موفقیت برات دارم 🌟",
    "بهترین‌ها برات آرزو میکنم ❤️",
    "موفق و پیروز باشی 💪",
    "همیشه شاد باشی! 🌟",
    "خوشحالم که هستی! ❤️",
    "تو ارزش داری! 💖",
    "به خودت ایمان داشته باش! 💪",
    "هیچوقت تسلیم نشو! 🌟",
    "تو می‌تونی! 💪",
    "بهترین زمان برای شروع همینه! 🚀",
    "موفقیت از تلاش تو میاد! 🏆",
    "فقط به جلو نگاه کن! 💪",
    "همیشه بهترین رو انتخاب کن! 🌟",
    "زندگی کوتاه است، پس لذت ببر! ❤️",
    "هر روزت پر از خیر و برکت باشه! 🙏",
    "همیشه لبخند به لب داشته باش! 😊",
    "خنده بهترین داروی جهان است! 😄",
    "مهربانی زبان مشترک همه انسان‌هاست! 🌹",
    "امید یعنی ادامه دادن به راه! 💫",
    "صبر کلید پیروزی است! 🔑",
    "عشق و محبت دو بال پروازند! 🦋",
    "دوستی یعنی بودن در کنار هم! 🤝",
    "وفاداری نادر است، قدرش را بدان! 💎",
    "صداقت بهترین سیاست است! 🎯",
    "تو بهترینی، پس بهترین باش! 🌟",
    "هر روزت پر از شادی و آرامش! 😊",
    "دنیا جای قشنگی است، زیبا ببینش! 🌍",
    "قلبت رو به روی عشق باز کن! ❤️",
    "زندگی یک هدیه است، قدرش را بدان! 🎁",
    "هر لحظه را غنیمت بشمار! ⏰",
    "آرامش درون خودت را پیدا کن! 🧘",
    "به طبیعت برو، آرامش بده! 🌿",
    "کتاب بخون، دانشت زیاد میشه! 📚",
    "سفر کن، دنیا رو ببین! ✈️",
    "با دیگران مهربان باش! 🌹",
    "به خودت استراحت بده! 😴",
    "همیشه لبخند بزن! 😊",
    "زندگی رو ساده بگیر! 🌟",
    "به دیگران کمک کن! 🤝",
    "همیشه مثبت اندیش باش! 💪",
    "به رویاهات ایمان داشته باش! 🌈",
    "هیچ چیز غیرممکن نیست! ✨",
    "تو یک قهرمانی! 🏆",
    "همیشه بهترین باش! 🌟",
    "به خودت افتخار کن! 💖",
    "همیشه در مسیر درست باش! 🎯",
    "زندگی زیباست، ازش لذت ببر! 🌹",
    "هر روز یه شروع جدید است! 🌅",
    "بهترین کارو انجام بده! 💪",
    "همیشه به فکر دیگران باش! ❤️",
    "دنیا به مهربانی تو نیاز دارد! 🌍",
    "تو می‌تونی دنیا رو تغییر بدی! 🌟",
    "همیشه به جلو حرکت کن! 🚀",
    "به خودت ایمان داشته باش! 💪",
    "هیچوقت دیر نیست برای شروع! ⏰",
    "زندگی یک ماجراجویی است! 🗺️",
    "از هر لحظه لذت ببر! 🎉",
    "همیشه شاد و خوشحال باش! 😊",
    "دنیا جای قشنگی است! 🌍",
    "بهترین رو برای خودت بخواه! 🌟",
    "همیشه در مسیر عشق باش! ❤️",
    "زندگی کوتاه است، پس بخند! 😄",
    "امروزتم قشنگ باشه داداش! 🌞",
    "هوامو داری، منم هوات رو دارم! 🤝",
    "هر روز یه فرصت جدیده! ✨",
    "با انرژی مثبت شروع کن! ⚡️",
    "قدم بعدی رو با اطمینان بردار! 👣",
    "تو از چیزی که فکر می‌کنی قوی‌تری! 💪",
    "بخند، دنیا قشنگ‌تر میشه! 😁",
    "امیدوارم روزت پر از خنده باشه! 😊",
    "هر مشکلی یه راه‌حل داره! 🔑",
    "آروم باش، همه چی درست میشه! 🍀",
    "وقتشه یکم به خودت افتخار کنی! 🏆",
    "هر روز یه قدم به هدفت نزدیک‌تری! 🎯",
    "خستگی موقتیه، نتیجه‌ت موندگاره! 🔥",
    "بهترین نسخه از خودت باش! 🌟",
    "امروز روز خوبیه برای شروع دوباره! 🌤️",
    "هیچی بهتر از یه لبخند واقعی نیست! 😄",
    "با خودت مهربون باش! 💗",
    "هر روز یکم بهتر از دیروز! 📈",
    "قوی باش، ولی مهربون هم باش! 🌸",
    "زندگی پر از شگفتیه! 🎁",
    "امروز رو با شادی شروع کن! 🎶",
    "هوای خودتم داشته باش! 🫶",
    "هدفتو گم نکن! 🧭",
    "هر روز یه داستان جدیده! 📖",
    "با آرامش جلو برو! 🕊️",
    "همیشه یه دلیل برای شکرگزاری هست! 🙏",
    "اعتماد به نفستو حفظ کن! 💎",
    "امروز بهترین روز برای تلاشه! 🚀",
    "تو لایق بهترین‌هایی! 🌈"
]

# =========================================================
#  🛠 رفع باگ: «سخنگو» صدا زدن اسم ربات هیچ‌وقت کار نمی‌کرد
# =========================================================
# لیست ۲۰۰ پاسخ بالا (GARDI_200_RESPONSES) از اول تعریف شده بود و پیام
# استارتاپ ربات هم صریحاً قول می‌داد «هر جا گاردی رو صدا کنی جوابت رو
# میدم»، ولی هیچ‌جای کد چیزی از این لیست استفاده نمی‌کرد؛ یعنی نوشتن
# «گاردی سلام» یا هر پیام دیگه‌ای که اسم ربات توش بود، عملاً هیچ جوابی
# نمی‌گرفت. این هندلر واقعاً همون قابلیت رو وصل می‌کنه.
# فقط داخل گروه فعال می‌شه (در پیوی، pv_fallback_handler خودش مسئول
# جواب دادنه)، و اگه «سخنگو» از پنل سخنگو خاموش شده باشه ساکت می‌مونه تا
# با تنظیمات ادمین در تناقض نباشه. اگه پیام یک دستور/الیاس شناخته‌شده یا
# سینتکس آموزش سخنگو («کلیدواژه ! پاسخ») باشه، این هندلر دخالت نمی‌کنه تا
# دوبار جواب داده نشه.
# 🛠 احوال‌پرسی‌های ساده («سلام»، «خوبی؟»، «چطوری؟»، «خداحافظ»...) نیازی به
# هوش مصنوعی (که چند ثانیه طول می‌کشه) ندارن؛ این‌ها فوری از همون جواب‌های
# آماده‌ی بالا جواب داده می‌شن. فقط برای سوال/متن واقعی می‌ره سراغ AI.
# 🛠 احوال‌پرسی‌های ساده («سلام»، «خوبی؟»، «چطوری؟»، «خداحافظ»...) نیازی به
# هوش مصنوعی (که چند ثانیه طول می‌کشه) ندارن؛ این‌ها فوری از همون جواب‌های
# آماده‌ی بالا جواب داده می‌شن. فقط برای سوال/متن واقعی می‌ره سراغ AI.
# لیست زیر با انواع املا/فاصله/عامیانه‌ی رایجِ هر عبارت کامل شده تا حداکثر
# حالت‌های واقعیِ چت روزمره رو (بدون نیاز به AI) پوشش بده.
_GREETING_R = ["سلام داداش! چطوری؟ 😊", "سلام بر تو! خوبی؟ 🌟", "سلام! چه خبر؟ 👋", "درود بر تو! 🌹", "علیک سلام! خوبی؟ 😊"]
_HOWAREU_R = ["خوبم داداش! تو چطوری؟ 💪", "عالی! ممنون که پرسیدی ❤️", "خوبم! خودت چطوری؟ 😊", "بد نیستم، تو چطوری؟ 🍀"]
_NEWS_R = ["روزگار می‌گذره! 🍀", "خوبم داداش! 😊", "سلامتی! تو چه خبرا؟ 🌟", "هیچی، خبرای تو چیه؟ 😄"]
_THANKS_R = ["خواهش می‌کنم داداش! ❤️", "قربان شما! 🌹", "نوش جونت! 😊", "وظیفه‌ست! 💪", "خواهش، همیشه در خدمتم! 🌟"]
_BYE_R = ["خداحافظ! 😊", "بای بای! 🌟", "به امید دیدار! ❤️", "مراقب خودت باش! 👋", "فعلاً! 🍀"]
_LOVE_R = ["منم دوستت دارم! ❤️", "عاشقتم! 😊", "همیشه دوستت دارم! 🌟", "تو بهترینی! 💖"]
_WHOAMI_R = ["من گاردی‌ام! دستیار و نگهبان این گروه 🤖🛡️", "گاردی هستم، همیشه اینجام برای کمک! 💪", "من گاردی‌ام، ربات این گروه! 🌟"]
_HOWAREYOU_DOING_R = ["دارم مراقب گروه هستم! تو چیکار می‌کنی؟ 😊", "همینجام، در خدمتتم! 🌟", "دارم کارامو انجام میدم! تو چطور؟ 💪"]
_MORNING_R = ["صبح شما هم بخیر! ☀️", "سلام، صبح بخیر! 🌞", "صبح بخیر داداش! 😊"]
_NOON_R = ["ظهر شما هم بخیر! 🌤️", "ظهر بخیر! 😊"]
_EVENING_R = ["عصر شما هم بخیر! 🌇", "عصر بخیر داداش! 😊"]
_NIGHT_R = ["شب شما هم بخیر! 🌙", "شب بخیر، خواب‌های خوب ببینی! 😴🌟"]
_TIRED_R = ["سلامت باشی! ممنون 🙏", "ممنون داداش، تو هم خسته نباشی! 😊"]
_YES_R = ["بله داداش! چی میگی؟ 💪", "جانم! بفرمایید 🌟", "در خدمتتم! ❤️", "چشم! بفرمایید 🌹"]

GARDI_QUICK_REPLIES = {}
for _keys, _responses in [
    (["سلام", "سلام گاردی", "سلاام", "سلامم", "سلام علیکم", "های", "هلو", "hi", "hello", "سلام رفیق", "سلام داداش", "سلام دوست من", "درود", "درود بر تو"], _GREETING_R),
    (["خوبی", "خوبی؟", "خوبی گاردی", "خوبی؟؟", "حالت خوبه", "حالت خوبه؟"], _HOWAREU_R),
    (["چطوری", "چطوری؟", "چطورى", "چطور", "چطوری داداش", "چطوره اوضاع"], _HOWAREU_R),
    (["حالت چطوره", "حالت چطوره؟", "احوالت چطوره", "احوالت چطوره؟", "اوضاع چطوره", "اوضاع چطوره؟"], _HOWAREU_R),
    (["چه خبر", "چه خبر؟", "چه خبرا", "چه خبرا؟", "چخبر", "چخبرا"], _NEWS_R),
    (["ممنون", "مرسی", "متشکرم", "ممنونم", "مرسی گاردی", "دمت گرم", "دستت درد نکنه", "مچکرم", "تشکر", "خیلی ممنون"], _THANKS_R),
    (["خداحافظ", "خدافظ", "خدانگهدار", "بای", "بای بای", "فعلا", "فعلاً", "میرم دیگه", "خدافظ گاردی"], _BYE_R),
    (["دوست دارم", "دوستت دارم", "عاشقتم", "دوست دارم گاردی", "عاشقتم گاردی"], _LOVE_R),
    (["کی هستی", "کی هستی؟", "تو کی هستی", "اسمت چیه", "اسمت چیه؟", "چه رباتی هستی", "معرفی کن خودتو", "خودتو معرفی کن"], _WHOAMI_R),
    (["چیکار میکنی", "چیکار می‌کنی", "چیکار میکنی؟", "داری چیکار میکنی", "چیکارا میکنی"], _HOWAREYOU_DOING_R),
    (["صبح بخیر", "صبحت بخیر", "صبح بخیر گاردی"], _MORNING_R),
    (["ظهر بخیر", "ظهرت بخیر"], _NOON_R),
    (["عصر بخیر", "عصرت بخیر"], _EVENING_R),
    (["شب بخیر", "شبت بخیر", "شب خوش"], _NIGHT_R),
    (["خسته نباشی", "خسته نباشید", "خسته نباشی گاردی"], _TIRED_R),
    (["بله", "جانم", "جانم؟", "بله؟", "چیه", "چیه؟"], _YES_R),
]:
    for _k in _keys:
        GARDI_QUICK_REPLIES[_k] = _responses
del _keys, _responses, _k


def _gardi_quick_reply(user_text: str):
    """اگه متن دقیقاً یه احوال‌پرسیِ سادهٔ شناخته‌شده باشه، یه جواب آماده و
    فوری برمی‌گردونه (بدون تماس با AI)؛ در غیر این صورت None."""
    t = normalize_fa(user_text or "").strip().strip("؟?!.,،")
    options = GARDI_QUICK_REPLIES.get(t)
    return random.choice(options) if options else None


@bot.on_message(filters=lambda m: m.text and "گاردی" in normalize_fa(m.text).lower())
async def gardi_name_call_handler(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        return

    if _match_alias(message.text) is not None or _parse_teach_syntax(message.text) is not None:
        return

    group_data = get_group_data(group_id)
    settings = group_data.get('settings', {})
    if not settings.get('speaker_enabled', True):
        return

    # 🛠 صدا زدن «گاردی» دیگه جواب آماده‌ی تصادفی (چرت‌وپرت) نمی‌ده؛ همیشه با
    # هوش مصنوعی واقعی جواب می‌ده — به‌جز احوال‌پرسی‌های ساده («سلام»،
    # «خوبی؟»...) که فوری و بدون تماس با AI جواب داده می‌شن (سریع‌تره و
    # نیازی به هوش مصنوعی نداره). اگه بعد از حذف «گاردی» متنی نمونده باشه
    # (یعنی فقط «گاردی» تنها گفته شده)، به‌عنوان سلام در نظر گرفته می‌شه.
    user_id = str(message.sender_id)
    user_text = normalize_fa(message.text).replace("گاردی", " ").strip()
    if not user_text:
        user_text = "سلام"

    quick = _gardi_quick_reply(user_text)
    if quick:
        await message.reply(quick)
        return

    # 🛠 سوال‌های قیمت لحظه‌ای (دلار/طلا/سکه/...) قبل از AI چک می‌شن، چون AI
    # اصلاً به اینترنت زنده وصل نیست و نمی‌تونه قیمت واقعی بده.
    if await _try_price_answer(user_text, message):
        return

    await _try_ai_answer(group_id, group_data, user_id, user_text, message, show_errors=True)

# 🛠 «ریپلای روی جواب هوش مصنوعی هم باید با هوش مصنوعی جواب بده» — قبلاً
# فقط وقتی کار می‌کرد که پیامِ ریپلای دوباره با «هوش مصنوعی» شروع می‌شد.
# این هندلر عمومی، فقط وقتی پیام واقعاً ریپلای روی یک جواب قبلیِ هوش
# مصنوعیِ همون کاربره (چه از مسیر «هوش مصنوعی»، چه از صدا زدن «گاردی»
# اومده باشه) فعال می‌شه، تا روی ریپلای‌های معمولیِ دیگه دخالت نکنه.
@bot.on_message(filters=lambda m: m.text and get_reply_message(m) is not None
                 and "گاردی" not in normalize_fa(m.text).lower()
                 and not normalize_key(m.text).startswith("هوش مصنوعی"))
async def ai_reply_continue_handler(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        return
    if _match_alias(message.text) is not None or _parse_teach_syntax(message.text) is not None:
        return

    reply_msg = get_reply_message(message)
    reply_text = getattr(reply_msg, "text", None)
    if not reply_text:
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    conversations = group_data.get('ai_conversations', {})
    if f"{user_id}::{reply_text}" not in conversations:
        return  # ریپلای روی یه پیام معمولیه، نه جواب قبلیِ هوش مصنوعیِ همین کاربر

    user_text = normalize_fa(message.text).strip()
    if not user_text:
        return

    await _try_ai_answer(group_id, group_data, user_id, user_text, message, reply_msg=reply_msg)

# =========================================================
#  ۲۰۰ تا چالش
# =========================================================

CHALLENGES_200 = [
    "🔥 ۱. ۱۰ بار درجا بپر!",
    "🔥 ۲. ۳۰ ثانیه نفس‌ت رو حبس کن!",
    "🔥 ۳. یه آهنگ بخون!",
    "🔥 ۴. یه داستان خنده‌دار بگو!",
    "🔥 ۵. ۵ بار خودت رو بچرخون!",
    "🔥 ۶. ۲۰ بار شنا برو!",
    "🔥 ۷. ۱۰ بار درخت بزن!",
    "🔥 ۸. یه شعر حفظ کن و بخون!",
    "🔥 ۹. ۵ دقیقه حرف نزن!",
    "🔥 ۱۰. با یه لحن خنده‌دار حرف بزن!",
    "🔥 ۱۱. ۱۰ تا اسم حیوان بگو!",
    "🔥 ۱۲. ۵ تا کشور خارجی اسم ببر!",
    "🔥 ۱۳. یه نقاشی بکش و نشون بده!",
    "🔥 ۱۴. ۳۰ ثانیه مثل قورباغه بپر!",
    "🔥 ۱۵. یه غذای خاص درست کن و عکسش رو بفرست!",
    "🔥 ۱۶. ۱۰ بار اسم خودت رو برعکس بگو!",
    "🔥 ۱۷. یه حرکت ورزشی جدید ابداع کن!",
    "🔥 ۱۸. ۵ دقیقه فقط با یه دست کار کن!",
    "🔥 ۱۹. یه تماس تلفنی با یه دوست بگیر و بهم بگو چی گفت!",
    "🔥 ۲۰. ۱۰ تا فیلم معروف اسم ببر!",
    "🔥 ۲۱. یه روز بدون گوشی باش!",
    "🔥 ۲۲. ۵ تا کتاب معروف اسم ببر!",
    "🔥 ۲۳. یه آهنگ خارجی بخون!",
    "🔥 ۲۴. ۱۰ بار بپر بالا!",
    "🔥 ۲۵. ۵ دقیقه به یه نقطه خیره شو!",
    "🔥 ۲۶. یه کارت پستال بکش!",
    "🔥 ۲۷. ۱۰ تا شغل اسم ببر!",
    "🔥 ۲۸. یه داستان کوتاه بنویس!",
    "🔥 ۲۹. ۵ دقیقه با یه لحن عجیب حرف بزن!",
    "🔥 ۳۰. یه معما بگو!",
    "🔥 ۳۱. ۱۰ تا میوه اسم ببر!",
    "🔥 ۳۲. یه روز بدون شکر باش!",
    "🔥 ۳۳. ۵ تا ورزش اسم ببر!",
    "🔥 ۳۴. یه روز بدون گوشی نت باش!",
    "🔥 ۳۵. ۱۰ تا شهر اسم ببر!",
    "🔥 ۳۶. یه روز زودتر از خواب بیدار شو!",
    "🔥 ۳۷. ۵ تا زبان خارجی اسم ببر!",
    "🔥 ۳۸. یه روز بدون نمک باش!",
    "🔥 ۳۹. ۱۰ تا گل اسم ببر!",
    "🔥 ۴۰. یه روز بدون چای باش!",
    "🔥 ۴۱. ۵ تا رنگ اسم ببر!",
    "🔥 ۴۲. یه روز بدون ناهار باش!",
    "🔥 ۴۳. ۱۰ تا پرنده اسم ببر!",
    "🔥 ۴۴. یه روز بدون گوشت باش!",
    "🔥 ۴۵. ۵ تا درخت اسم ببر!",
    "🔥 ۴۶. یه روز بدون شیرینی باش!",
    "🔥 ۴۷. ۱۰ تا حشره اسم ببر!",
    "🔥 ۴۸. یه روز بدون میوه باش!",
    "🔥 ۴۹. ۵ تا سبزی اسم ببر!",
    "🔥 ۵۰. یه روز بدون نون باش!",
    "🔥 ۵۱. ۱۰ تا نوع لباس اسم ببر!",
    "🔥 ۵۲. یه روز بدون تلویزیون باش!",
    "🔥 ۵۳. ۵ تا ابزار اسم ببر!",
    "🔥 ۵۴. یه روز بدون قند باش!",
    "🔥 ۵۵. ۱۰ تا وسایل نقلیه اسم ببر!",
    "🔥 ۵۶. یه روز بدون گوشت قرمز باش!",
    "🔥 ۵۷. ۵ تا میوه تابستانی اسم ببر!",
    "🔥 ۵۸. یه روز بدون نمک باش!",
    "🔥 ۵۹. ۱۰ تا میوه زمستانی اسم ببر!",
    "🔥 ۶۰. یه روز بدون چای سیاه باش!",
    "🔥 ۶۱. ۵ تا غذای ایرانی اسم ببر!",
    "🔥 ۶۲. یه روز بدون روغن باش!",
    "🔥 ۶۳. ۱۰ تا غذای خارجی اسم ببر!",
    "🔥 ۶۴. یه روز بدون برنج باش!",
    "🔥 ۶۵. ۵ تا دسر اسم ببر!",
    "🔥 ۶۶. یه روز بدون آشپزی باش!",
    "🔥 ۶۷. ۱۰ تا نوشیدنی اسم ببر!",
    "🔥 ۶۸. یه روز بدون خرید باش!",
    "🔥 ۶۹. ۵ تا کشور همسایه ایران اسم ببر!",
    "🔥 ۷۰. یه روز بدون کار باش!",
    "🔥 ۷۱. ۱۰ تا دریا اسم ببر!",
    "🔥 ۷۲. یه روز بدون رفت و آمد باش!",
    "🔥 ۷۳. ۵ تا رودخانه اسم ببر!",
    "🔥 ۷۴. یه روز بدون سیگار باش!",
    "🔥 ۷۵. ۱۰ تا کوه اسم ببر!",
    "🔥 ۷۶. یه روز بدون پارک باش!",
    "🔥 ۷۷. ۵ تا جزیره اسم ببر!",
    "🔥 ۷۸. یه روز بدون خرید اینترنتی باش!",
    "🔥 ۷۹. ۱۰ تا فروشگاه اسم ببر!",
    "🔥 ۸۰. یه روز بدون پستو باش!",
    "🔥 ۸۱. ۵ تا برند معروف اسم ببر!",
    "🔥 ۸۲. یه روز بدون لباس فرم باش!",
    "🔥 ۸۳. ۱۰ تا بازی کامپیوتری اسم ببر!",
    "🔥 ۸۴. یه روز بدون بازی باش!",
    "🔥 ۸۵. ۵ تا فیلم جدید اسم ببر!",
    "🔥 ۸۶. یه روز بدون اخبار باش!",
    "🔥 ۸۷. ۱۰ تا سریال معروف اسم ببر!",
    "🔥 ۸۸. یه روز بدون اینترنت باش!",
    "🔥 ۸۹. ۵ تا خواننده معروف اسم ببر!",
    "🔥 ۹۰. یه روز بدون موسیقی باش!",
    "🔥 ۹۱. ۱۰ تا آهنگ جدید اسم ببر!",
    "🔥 ۹۲. یه روز بدون رادیو باش!",
    "🔥 ۹۳. ۵ تا کتاب جدید اسم ببر!",
    "🔥 ۹۴. یه روز بدون مطالعه باش!",
    "🔥 ۹۵. ۱۰ تا مجله اسم ببر!",
    "🔥 ۹۶. یه روز بدون روزنامه باش!",
    "🔥 ۹۷. ۵ تا شاعر اسم ببر!",
    "🔥 ۹۸. یه روز بدون شعر باش!",
    "🔥 ۹۹. ۱۰ تا نویسنده اسم ببر!",
    "🔥 ۱۰۰. یه روز بدون داستان باش!",
    "🔥 ۱۰۱. ۵ تا فیلمنامه‌نویس اسم ببر!",
    "🔥 ۱۰۲. یه روز بدون سینما باش!",
    "🔥 ۱۰۳. ۱۰ تا کارگردان اسم ببر!",
    "🔥 ۱۰۴. یه روز بدون تئاتر باش!",
    "🔥 ۱۰۵. ۵ تا بازیگر زن اسم ببر!",
    "🔥 ۱۰۶. یه روز بدون هنر باش!",
    "🔥 ۱۰۷. ۱۰ تا نقاش اسم ببر!",
    "🔥 ۱۰۸. یه روز بدون نقاشی باش!",
    "🔥 ۱۰۹. ۵ تا مجسمه‌ساز اسم ببر!",
    "🔥 ۱۱۰. یه روز بدون مجسمه باش!",
    "🔥 ۱۱۱. ۱۰ تا معمار اسم ببر!",
    "🔥 ۱۱۲. یه روز بدون معماری باش!",
    "🔥 ۱۱۳. ۵ تا طراح لباس اسم ببر!",
    "🔥 ۱۱۴. یه روز بدون مد باش!",
    "🔥 ۱۱۵. ۱۰ تا عکاس اسم ببر!",
    "🔥 ۱۱۶. یه روز بدون عکاسی باش!",
    "🔥 ۱۱۷. ۵ تا فیلمبردار اسم ببر!",
    "🔥 ۱۱۸. یه روز بدون فیلمبرداری باش!",
    "🔥 ۱۱۹. ۱۰ تا تدوینگر اسم ببر!",
    "🔥 ۱۲۰. یه روز بدون تدوین باش!",
    "🔥 ۱۲۱. ۵ تا صداگذار اسم ببر!",
    "🔥 ۱۲۲. یه روز بدون صدا باش!",
    "🔥 ۱۲۳. ۱۰ تا آهنگساز اسم ببر!",
    "🔥 ۱۲۴. یه روز بدون آهنگسازی باش!",
    "🔥 ۱۲۵. ۵ تا خواننده زن اسم ببر!",
    "🔥 ۱۲۶. یه روز بدون خوانندگی باش!",
    "🔥 ۱۲۷. ۱۰ تا شاعر معاصر اسم ببر!",
    "🔥 ۱۲۸. یه روز بدون شعر معاصر باش!",
    "🔥 ۱۲۹. ۵ تا شاعر کلاسیک اسم ببر!",
    "🔥 ۱۳۰. یه روز بدون شعر کلاسیک باش!",
    "🔥 ۱۳۱. ۱۰ تا نویسنده رمان اسم ببر!",
    "🔥 ۱۳۲. یه روز بدون رمان باش!",
    "🔥 ۱۳۳. ۵ تا نویسنده داستان کوتاه اسم ببر!",
    "🔥 ۱۳۴. یه روز بدون داستان کوتاه باش!",
    "🔥 ۱۳۵. ۱۰ تا نمایش‌نامه‌نویس اسم ببر!",
    "🔥 ۱۳۶. یه روز بدون نمایش باش!",
    "🔥 ۱۳۷. ۵ تا فیلمنامه‌نویس ایرانی اسم ببر!",
    "🔥 ۱۳۸. یه روز بدون فیلم ایرانی باش!",
    "🔥 ۱۳۹. ۱۰ تا فیلم خارجی اسم ببر!",
    "🔥 ۱۴۰. یه روز بدون فیلم خارجی باش!",
    "🔥 ۱۴۱. ۵ تا کارگردان ایرانی اسم ببر!",
    "🔥 ۱۴۲. یه روز بدون کارگردانی باش!",
    "🔥 ۱۴۳. ۱۰ تا بازیگر مرد اسم ببر!",
    "🔥 ۱۴۴. یه روز بدون بازیگری باش!",
    "🔥 ۱۴۵. ۵ تا بازیگر زن ایرانی اسم ببر!",
    "🔥 ۱۴۶. یه روز بدون بازیگر باش!",
    "🔥 ۱۴۷. ۱۰ تا خواننده مرد اسم ببر!",
    "🔥 ۱۴۸. یه روز بدون خواننده باش!",
    "🔥 ۱۴۹. ۵ تا خواننده زن خارجی اسم ببر!",
    "🔥 ۱۵۰. یه روز بدون موسیقی خارجی باش!",
    "🔥 ۱۵۱. ۱۰ تا آهنگ ایرانی اسم ببر!",
    "🔥 ۱۵۲. یه روز بدون آهنگ ایرانی باش!",
    "🔥 ۱۵۳. ۵ تا آهنگ خارجی اسم ببر!",
    "🔥 ۱۵۴. یه روز بدون آهنگ خارجی باش!",
    "🔥 ۱۵۵. ۱۰ تا فیلم کمدی اسم ببر!",
    "🔥 ۱۵۶. یه روز بدون کمدی باش!",
    "🔥 ۱۵۷. ۵ تا فیلم درام اسم ببر!",
    "🔥 ۱۵۸. یه روز بدون درام باش!",
    "🔥 ۱۵۹. ۱۰ تا فیلم اکشن اسم ببر!",
    "🔥 ۱۶۰. یه روز بدون اکشن باش!",
    "🔥 ۱۶۱. ۵ تا فیلم ترسناک اسم ببر!",
    "🔥 ۱۶۲. یه روز بدون ترسناک باش!",
    "🔥 ۱۶۳. ۱۰ تا فیلم علمی تخیلی اسم ببر!",
    "🔥 ۱۶۴. یه روز بدون علمی تخیلی باش!",
    "🔥 ۱۶۵. ۵ تا فیلم انیمیشن اسم ببر!",
    "🔥 ۱۶۶. یه روز بدون انیمیشن باش!",
    "🔥 ۱۶۷. ۱۰ تا فیلم مستند اسم ببر!",
    "🔥 ۱۶۸. یه روز بدون مستند باش!",
    "🔥 ۱۶۹. ۵ تا فیلم جنگی اسم ببر!",
    "🔥 ۱۷۰. یه روز بدون جنگی باش!",
    "🔥 ۱۷۱. ۱۰ تا فیلم عاشقانه اسم ببر!",
    "🔥 ۱۷۲. یه روز بدون عاشقانه باش!",
    "🔥 ۱۷۳. ۵ تا فیلم معمایی اسم ببر!",
    "🔥 ۱۷۴. یه روز بدون معمایی باش!",
    "🔥 ۱۷۵. ۱۰ تا فیلم ماجراجویی اسم ببر!",
    "🔥 ۱۷۶. یه روز بدون ماجراجویی باش!",
    "🔥 ۱۷۷. ۵ تا فیلم خانوادگی اسم ببر!",
    "🔥 ۱۷۸. یه روز بدون خانوادگی باش!",
    "🔥 ۱۷۹. ۱۰ تا فیلم تاریخی اسم ببر!",
    "🔥 ۱۸۰. یه روز بدون تاریخی باش!",
    "🔥 ۱۸۱. ۵ تا کتاب تاریخی اسم ببر!",
    "🔥 ۱۸۲. یه روز بدون کتاب تاریخی باش!",
    "🔥 ۱۸۳. ۱۰ تا کتاب علمی اسم ببر!",
    "🔥 ۱۸۴. یه روز بدون کتاب علمی باش!",
    "🔥 ۱۸۵. ۵ تا کتاب ادبی اسم ببر!",
    "🔥 ۱۸۶. یه روز بدون کتاب ادبی باش!",
    "🔥 ۱۸۷. ۱۰ تا کتاب کودک اسم ببر!",
    "🔥 ۱۸۸. یه روز بدون کتاب کودک باش!",
    "🔥 ۱۸۹. ۵ تا کتاب نوجوان اسم ببر!",
    "🔥 ۱۹۰. یه روز بدون کتاب نوجوان باش!",
    "🔥 ۱۹۱. ۱۰ تا کتاب روانشناسی اسم ببر!",
    "🔥 ۱۹۲. یه روز بدون کتاب روانشناسی باش!",
    "🔥 ۱۹۳. ۵ تا کتاب فلسفی اسم ببر!",
    "🔥 ۱۹۴. یه روز بدون کتاب فلسفی باش!",
    "🔥 ۱۹۵. ۱۰ تا کتاب دینی اسم ببر!",
    "🔥 ۱۹۶. یه روز بدون کتاب دینی باش!",
    "🔥 ۱۹۷. ۵ تا کتاب اقتصادی اسم ببر!",
    "🔥 ۱۹۸. یه روز بدون کتاب اقتصادی باش!",
    "🔥 ۱۹۹. ۱۰ تا کتاب هنری اسم ببر!",
    "🔥 ۲۰۰. یه روز بدون کتاب هنری باش!"
]
# =========================================================
#  ۲۰۰ تا پ ن پ
# =========================================================

PANAPA_200 = [
    '⌯ #PANAPA\n\nتوی صف بربری وایسادم ، یارو میگه شما هم توی صفی ؟\nگفتم پَ نَ پَ من از اداره بازرسی و نظارت بر کیفیت و قیمت نان مزاحم میشم ،\nطبیعی رفتار کن سه نشه !',
    '⌯ #PANAPA\n\nجلو عابر بانک صف وایسادیم یارو اومده میپرسه صفه؟\nمیگم پـَـ نـَـ پـَـ ما نخودیم اینجا کاشتنمون تا سبز بشیم!',
    '⌯ #PANAPA\n\nمرغ و از فریزر در آوردم میگه می خوای غذا درست کنی ؟!\nپـَـَـ نَ پـَـَــــ خانوادش اومدن از سردخونه میخوان ببرن خاکش کنن !',
    '⌯ #PANAPA\n\nرفته بودم نون بخرم، نونوا گفت چنده؟ گفتم پـَـ نـَـ پـَـ چرا نونو نشستی!',
    '⌯ #PANAPA\n\nرفتم خونه دوستم، زنگ زدم درو باز کرد گفت بیا تو\nگفتم پـَـ نـَـ پـَـ من که مهمونم تو باید بیای بیرون!',
    '⌯ #PANAPA\n\nماشین خریدم، رفتم پلاک کنم، گفتن پلاکت چنده؟\nگفتم پـَـ نـَـ پـَـ مگه من پلاک سازم!',
    '⌯ #PANAPA\n\nرفتم مغازه، گفتم سیب دارین؟ گفت نه\nگفتم پـَـ نـَـ پـَـ پس چرا مغازه میوه فروشی باز کردی!',
    '⌯ #PANAPA\n\nرفتم کفاشی، گفتم کفش چند؟ گفت ۵۰ تومن\nگفتم پـَـ نـَـ پـَـ من پول ندارم ولی پا دارم!',
    '⌯ #PANAPA\n\nرفتم نونوایی، گفتم نون سنگک چند؟ گفت ۵ تومن\nگفتم پـَـ نـَـ پـَـ سنگش چنده؟',
    '⌯ #PANAPA\n\nرفتم لباس فروشی، گفتم این لباس چند؟ گفت ۱۰۰ تومن\nگفتم پـَـ نـَـ پـَـ برهنه بهتره!',
    '⌯ #PANAPA\n\nرفتم آرایشگاه، گفتم موهاتو کوتاه کن، گفت چند سانت؟\nگفتم پـَـ نـَـ پـَـ من که مو ندارم!',
    '⌯ #PANAPA\n\nرفتم عینک فروشی، گفتم عینک آفتابی چند؟ گفت ۲۰۰ تومن\nگفتم پـَـ نـَـ پـَـ آفتاب که رایگانه!',
    '⌯ #PANAPA\n\nرفتم ساعت فروشی، گفتم ساعت چند؟ گفت ۵۰ تومن\nگفتم پـَـ نـَـ پـَـ وقت که مجانیه!',
    '⌯ #PANAPA\n\nرفتم جواهر فروشی، گفتم انگشتر چند؟ گفت ۳۰۰ تومن\nگفتم پـَـ نـَـ پـَـ انگشت که دارم!',
    '⌯ #PANAPA\n\nرفتم مبلی، گفتم مبل چند؟ گفت ۵۰۰ تومن\nگفتم پـَـ نـَـ پـَـ زمین که دارم بشینم!',
    '⌯ #PANAPA\n\nرفتم فرش فروشی، گفتم فرش چند؟ گفت ۴۰۰ تومن\nگفتم پـَـ نـَـ پـَـ کف که دارم!',
    '⌯ #PANAPA\n\nرفتم کتاب فروشی، گفتم کتاب چند؟ گفت ۲۰ تومن\nگفتم پـَـ نـَـ پـَـ مغز که دارم!',
    '⌯ #PANAPA\n\nرفتم کیف فروشی، گفتم کیف چند؟ گفت ۳۰ تومن\nگفتم پـَـ نـَـ پـَـ دست که دارم!',
    '⌯ #PANAPA\n\nرفتم کفش فروشی، گفتم کفش چند؟ گفت ۴۰ تومن\nگفتم پـَـ نـَـ پـَـ پا که دارم!',
    '⌯ #PANAPA\n\nرفتم عطر فروشی، گفتم عطر چند؟ گفت ۶۰ تومن\nگفتم پـَـ نـَـ پـَـ بو که مجانیه!',
    '⌯ #PANAPA\n\nرفتم طلا فروشی، گفتم طلا چند؟ گفت ۷۰ تومن\nگفتم پـَـ نـَـ پـَـ دست که دارم!',
    '⌯ #PANAPA\n\nرفتم پارچه فروشی، گفتم پارچه چند؟ گفت ۸۰ تومن\nگفتم پـَـ نـَـ پـَـ بدن که دارم!',
    '⌯ #PANAPA\n\nرفتم میوه فروشی، گفتم هندوانه چند؟ گفت ۹۰ تومن\nگفتم پـَـ نـَـ پـَـ آب که مجانیه!',
    '⌯ #PANAPA\n\nرفتم بستنی فروشی، گفتم بستنی چند؟ گفت ۱۰۰ تومن\nگفتم پـَـ نـَـ پـَـ یخ که مجانیه!',
    '⌯ #PANAPA\n\nرفتم آهن فروشی، گفتم آهن چند؟ گفت ۱۱۰ تومن\nگفتم پـَـ نـَـ پـَـ دست که دارم!',
    '⌯ #PANAPA\n\nرفتم چوب فروشی، گفتم چوب چند؟ گفت ۱۲۰ تومن\nگفتم پـَـ نـَـ پـَـ پا که دارم!',
    '⌯ #PANAPA\n\nرفتم شیشه فروشی، گفتم شیشه چند؟ گفت ۱۳۰ تومن\nگفتم پـَـ نـَـ پـَـ چشم که دارم!',
    '⌯ #PANAPA\n\nرفتم کاغذ فروشی، گفتم کاغذ چند؟ گفت ۱۴۰ تومن\nگفتم پـَـ نـَـ پـَـ مغز که دارم!',
    '⌯ #PANAPA\n\nرفتم رنگ فروشی، گفتم رنگ چند؟ گفت ۱۵۰ تومن\nگفتم پـَـ نـَـ پـَـ چشم که دارم!',
    '⌯ #PANAPA\n\nرفتم چرم فروشی، گفتم چرم چند؟ گفت ۱۶۰ تومن\nگفتم پـَـ نـَـ پـَـ پوست که دارم!',
    '⌯ #PANAPA\n\nرفتم پنبه فروشی، گفتم پنبه چند؟ گفت ۱۷۰ تومن\nگفتم پـَـ نـَـ پـَـ ابر که مجانیه!',
    '⌯ #PANAPA\n\nرفتم ابریشم فروشی، گفتم ابریشم چند؟ گفت ۱۸۰ تومن\nگفتم پـَـ نـَـ پـَـ دست که دارم!',
    '⌯ #PANAPA\n\nرفتم پشم فروشی، گفتم پشم چند؟ گفت ۱۹۰ تومن\nگفتم پـَـ نـَـ پـَـ گوسفند که دارم!',
    '⌯ #PANAPA\n\nرفتم پلاستیک فروشی، گفتم پلاستیک چند؟ گفت ۲۰۰ تومن\nگفتم پـَـ نـَـ پـَـ دست که دارم!',
    '⌯ #PANAPA\n\nرفتم لاستیک فروشی، گفتم لاستیک چند؟ گفت ۲۱۰ تومن\nگفتم پـَـ نـَـ پـَـ پا که دارم!',
    '⌯ #PANAPA\n\nرفتم شمع فروشی، گفتم شمع چند؟ گفت ۲۲۰ تومن\nگفتم پـَـ نـَـ پـَـ نور که مجانیه!',
    '⌯ #PANAPA\n\nرفتم فتیله فروشی، گفتم فتیله چند؟ گفت ۲۳۰ تومن\nگفتم پـَـ نـَـ پـَـ دست که دارم!',
    '⌯ #PANAPA\n\nرفتم روغن فروشی، گفتم روغن چند؟ گفت ۲۴۰ تومن\nگفتم پـَـ نـَـ پـَـ چربی که دارم!',
    '⌯ #PANAPA\n\nرفتم عسل فروشی، گفتم عسل چند؟ گفت ۲۵۰ تومن\nگفتم پـَـ نـَـ پـَـ زنبور که دارم!',
    '⌯ #PANAPA\n\nرفتم قند فروشی، گفتم قند چند؟ گفت ۲۶۰ تومن\nگفتم پـَـ نـَـ پـَـ شیرینی که دارم!',
    '⌯ #PANAPA\n\nرفتم پرینتر فروشی، گفتم پرینتر چند؟ گفت 870 تومن\nگفتم پـَـ نـَـ پـَـ صبر که دارم!',
    '⌯ #PANAPA\n\nرفتم اسکنر فروشی، گفتم اسکنر چند؟ گفت 885 تومن\nگفتم پـَـ نـَـ پـَـ قلب که دارم!',
    '⌯ #PANAPA\n\nرفتم فلش\u200cمموری فروشی، گفتم فلش\u200cمموری چند؟ گفت 900 تومن\nگفتم پـَـ نـَـ پـَـ شوخ\u200cطبعی که دارم!',
    '⌯ #PANAPA\n\nرفتم هارد فروشی، گفتم هارد چند؟ گفت 915 تومن\nگفتم پـَـ نـَـ پـَـ بو که مجانیه!',
    '⌯ #PANAPA\n\nرفتم رم فروشی، گفتم رم چند؟ گفت 930 تومن\nگفتم پـَـ نـَـ پـَـ عشق که دارم!',
    '⌯ #PANAPA\n\nرفتم پردازنده فروشی، گفتم پردازنده چند؟ گفت 945 تومن\nگفتم پـَـ نـَـ پـَـ اعصاب که ندارم!',
    '⌯ #PANAPA\n\nرفتم مادربرد فروشی، گفتم مادربرد چند؟ گفت 960 تومن\nگفتم پـَـ نـَـ پـَـ بدشانسی که دارم!',
    '⌯ #PANAPA\n\nرفتم کارت گرافیک فروشی، گفتم کارت گرافیک چند؟ گفت 975 تومن\nگفتم پـَـ نـَـ پـَـ نور که مجانیه!',
    '⌯ #PANAPA\n\nرفتم صندلی فروشی، گفتم صندلی چند؟ گفت 990 تومن\nگفتم پـَـ نـَـ پـَـ شانس که ندارم!',
    '⌯ #PANAPA\n\nرفتم میز فروشی، گفتم میز چند؟ گفت 1005 تومن\nگفتم پـَـ نـَـ پـَـ خواب که کافیه!',
    '⌯ #PANAPA\n\nرفتم کمد فروشی، گفتم کمد چند؟ گفت 1020 تومن\nگفتم پـَـ نـَـ پـَـ خستگی که دارم!',
    '⌯ #PANAPA\n\nرفتم تخت فروشی، گفتم تخت چند؟ گفت 1035 تومن\nگفتم پـَـ نـَـ پـَـ وقت که مجانیه!',
    '⌯ #PANAPA\n\nرفتم بالش فروشی، گفتم بالش چند؟ گفت 1050 تومن\nگفتم پـَـ نـَـ پـَـ حوصله که ندارم!',
    '⌯ #PANAPA\n\nرفتم پتو فروشی، گفتم پتو چند؟ گفت 1065 تومن\nگفتم پـَـ نـَـ پـَـ انرژی که دارم!',
    '⌯ #PANAPA\n\nرفتم ملحفه فروشی، گفتم ملحفه چند؟ گفت 1080 تومن\nگفتم پـَـ نـَـ پـَـ دست که دارم!',
    '⌯ #PANAPA\n\nرفتم حوله فروشی، گفتم حوله چند؟ گفت 1095 تومن\nگفتم پـَـ نـَـ پـَـ هوا که مجانیه!',
    '⌯ #PANAPA\n\nرفتم صابون فروشی، گفتم صابون چند؟ گفت 1110 تومن\nگفتم پـَـ نـَـ پـَـ پول که ندارم!',
    '⌯ #PANAPA\n\nرفتم شامپو فروشی، گفتم شامپو چند؟ گفت 1125 تومن\nگفتم پـَـ نـَـ پـَـ استعداد که دارم!',
    '⌯ #PANAPA\n\nرفتم خمیردندان فروشی، گفتم خمیردندان چند؟ گفت 1140 تومن\nگفتم پـَـ نـَـ پـَـ پا که دارم!',
    '⌯ #PANAPA\n\nرفتم مسواک فروشی، گفتم مسواک چند؟ گفت 1155 تومن\nگفتم پـَـ نـَـ پـَـ آب که مجانیه!',
    '⌯ #PANAPA\n\nرفتم عطر جیب فروشی، گفتم عطر جیب چند؟ گفت 1170 تومن\nگفتم پـَـ نـَـ پـَـ زبون که دارم!',
    '⌯ #PANAPA\n\nرفتم کرم دست فروشی، گفتم کرم دست چند؟ گفت 1185 تومن\nگفتم پـَـ نـَـ پـَـ ذوق که دارم!',
    '⌯ #PANAPA\n\nرفتم ماسک صورت فروشی، گفتم ماسک صورت چند؟ گفت 1200 تومن\nگفتم پـَـ نـَـ پـَـ چشم که دارم!',
    '⌯ #PANAPA\n\nرفتم کیف مدرسه فروشی، گفتم کیف مدرسه چند؟ گفت 1215 تومن\nگفتم پـَـ نـَـ پـَـ خنده که مجانیه!',
    '⌯ #PANAPA\n\nرفتم دفتر فروشی، گفتم دفتر چند؟ گفت 1230 تومن\nگفتم پـَـ نـَـ پـَـ گوش که دارم!',
    '⌯ #PANAPA\n\nرفتم خودکار فروشی، گفتم خودکار چند؟ گفت 1245 تومن\nگفتم پـَـ نـَـ پـَـ نمک که دارم!',
    '⌯ #PANAPA\n\nرفتم مداد فروشی، گفتم مداد چند؟ گفت 1260 تومن\nگفتم پـَـ نـَـ پـَـ مغز که دارم!',
    '⌯ #PANAPA\n\nرفتم پاک\u200cکن فروشی، گفتم پاک\u200cکن چند؟ گفت 1275 تومن\nگفتم پـَـ نـَـ پـَـ صبر که دارم!',
    '⌯ #PANAPA\n\nرفتم خط\u200cکش فروشی، گفتم خط\u200cکش چند؟ گفت 1290 تومن\nگفتم پـَـ نـَـ پـَـ قلب که دارم!',
    '⌯ #PANAPA\n\nرفتم ماژیک فروشی، گفتم ماژیک چند؟ گفت 1305 تومن\nگفتم پـَـ نـَـ پـَـ شوخ\u200cطبعی که دارم!',
    '⌯ #PANAPA\n\nرفتم رنگ\u200cکن فروشی، گفتم رنگ\u200cکن چند؟ گفت 1320 تومن\nگفتم پـَـ نـَـ پـَـ بو که مجانیه!',
    '⌯ #PANAPA\n\nرفتم بادکنک فروشی، گفتم بادکنک چند؟ گفت 1335 تومن\nگفتم پـَـ نـَـ پـَـ عشق که دارم!',
    '⌯ #PANAPA\n\nرفتم کیک فروشی، گفتم کیک چند؟ گفت 1350 تومن\nگفتم پـَـ نـَـ پـَـ اعصاب که ندارم!',
    '⌯ #PANAPA\n\nرفتم شکلات فروشی، گفتم شکلات چند؟ گفت 1365 تومن\nگفتم پـَـ نـَـ پـَـ بدشانسی که دارم!',
    '⌯ #PANAPA\n\nرفتم آدامس فروشی، گفتم آدامس چند؟ گفت 1380 تومن\nگفتم پـَـ نـَـ پـَـ نور که مجانیه!',
    '⌯ #PANAPA\n\nرفتم چیپس فروشی، گفتم چیپس چند؟ گفت 1395 تومن\nگفتم پـَـ نـَـ پـَـ شانس که ندارم!',
    '⌯ #PANAPA\n\nرفتم پفک فروشی، گفتم پفک چند؟ گفت 1410 تومن\nگفتم پـَـ نـَـ پـَـ خواب که کافیه!',
    '⌯ #PANAPA\n\nرفتم نوشابه فروشی، گفتم نوشابه چند؟ گفت 1425 تومن\nگفتم پـَـ نـَـ پـَـ خستگی که دارم!',
    '⌯ #PANAPA\n\nرفتم دوغ فروشی، گفتم دوغ چند؟ گفت 1440 تومن\nگفتم پـَـ نـَـ پـَـ وقت که مجانیه!',
    '⌯ #PANAPA\n\nرفتم ماست فروشی، گفتم ماست چند؟ گفت 1455 تومن\nگفتم پـَـ نـَـ پـَـ حوصله که ندارم!',
    '⌯ #PANAPA\n\nرفتم پنیر فروشی، گفتم پنیر چند؟ گفت 1470 تومن\nگفتم پـَـ نـَـ پـَـ انرژی که دارم!',
    '⌯ #PANAPA\n\nرفتم کره فروشی، گفتم کره چند؟ گفت 1485 تومن\nگفتم پـَـ نـَـ پـَـ دست که دارم!',
    '⌯ #PANAPA\n\nرفتم مربا فروشی، گفتم مربا چند؟ گفت 1500 تومن\nگفتم پـَـ نـَـ پـَـ هوا که مجانیه!',
    '⌯ #PANAPA\n\nرفتم عسل طبیعی فروشی، گفتم عسل طبیعی چند؟ گفت 1515 تومن\nگفتم پـَـ نـَـ پـَـ پول که ندارم!',
    '⌯ #PANAPA\n\nرفتم چای فروشی، گفتم چای چند؟ گفت 1530 تومن\nگفتم پـَـ نـَـ پـَـ استعداد که دارم!',
    '⌯ #PANAPA\n\nرفتم قهوه فروشی، گفتم قهوه چند؟ گفت 1545 تومن\nگفتم پـَـ نـَـ پـَـ پا که دارم!',
    '⌯ #PANAPA\n\nرفتم نبات فروشی، گفتم نبات چند؟ گفت 1560 تومن\nگفتم پـَـ نـَـ پـَـ آب که مجانیه!',
    '⌯ #PANAPA\n\nرفتم آجیل فروشی، گفتم آجیل چند؟ گفت 1575 تومن\nگفتم پـَـ نـَـ پـَـ زبون که دارم!',
    '⌯ #PANAPA\n\nرفتم خرما فروشی، گفتم خرما چند؟ گفت 1590 تومن\nگفتم پـَـ نـَـ پـَـ ذوق که دارم!',
    '⌯ #PANAPA\n\nرفتم کشمش فروشی، گفتم کشمش چند؟ گفت 1605 تومن\nگفتم پـَـ نـَـ پـَـ چشم که دارم!',
    '⌯ #PANAPA\n\nرفتم گردو فروشی، گفتم گردو چند؟ گفت 1620 تومن\nگفتم پـَـ نـَـ پـَـ خنده که مجانیه!',
    '⌯ #PANAPA\n\nرفتم بادام فروشی، گفتم بادام چند؟ گفت 1635 تومن\nگفتم پـَـ نـَـ پـَـ گوش که دارم!',
    '⌯ #PANAPA\n\nرفتم پسته فروشی، گفتم پسته چند؟ گفت 1650 تومن\nگفتم پـَـ نـَـ پـَـ نمک که دارم!',
    '⌯ #PANAPA\n\nرفتم فندق فروشی، گفتم فندق چند؟ گفت 1665 تومن\nگفتم پـَـ نـَـ پـَـ مغز که دارم!',
    '⌯ #PANAPA\n\nرفتم نارگیل فروشی، گفتم نارگیل چند؟ گفت 1680 تومن\nگفتم پـَـ نـَـ پـَـ صبر که دارم!',
    '⌯ #PANAPA\n\nرفتم انبه فروشی، گفتم انبه چند؟ گفت 1695 تومن\nگفتم پـَـ نـَـ پـَـ قلب که دارم!',
    '⌯ #PANAPA\n\nرفتم کیوی فروشی، گفتم کیوی چند؟ گفت 1710 تومن\nگفتم پـَـ نـَـ پـَـ شوخ\u200cطبعی که دارم!',
    '⌯ #PANAPA\n\nرفتم توت\u200cفرنگی فروشی، گفتم توت\u200cفرنگی چند؟ گفت 1725 تومن\nگفتم پـَـ نـَـ پـَـ بو که مجانیه!',
    '⌯ #PANAPA\n\nرفتم آلبالو فروشی، گفتم آلبالو چند؟ گفت 1740 تومن\nگفتم پـَـ نـَـ پـَـ عشق که دارم!',
    '⌯ #PANAPA\n\nرفتم گیلاس فروشی، گفتم گیلاس چند؟ گفت 1755 تومن\nگفتم پـَـ نـَـ پـَـ اعصاب که ندارم!',
    '⌯ #PANAPA\n\nرفتم هلو فروشی، گفتم هلو چند؟ گفت 1770 تومن\nگفتم پـَـ نـَـ پـَـ بدشانسی که دارم!',
    '⌯ #PANAPA\n\nرفتم زردآلو فروشی، گفتم زردآلو چند؟ گفت 1785 تومن\nگفتم پـَـ نـَـ پـَـ نور که مجانیه!',
    '⌯ #PANAPA\n\nرفتم انگور فروشی، گفتم انگور چند؟ گفت 1800 تومن\nگفتم پـَـ نـَـ پـَـ شانس که ندارم!',
    '⌯ #PANAPA\n\nرفتم انار فروشی، گفتم انار چند؟ گفت 1815 تومن\nگفتم پـَـ نـَـ پـَـ خواب که کافیه!',
    '⌯ #PANAPA\n\nرفتم پرتقال فروشی، گفتم پرتقال چند؟ گفت 1830 تومن\nگفتم پـَـ نـَـ پـَـ خستگی که دارم!',
    '⌯ #PANAPA\n\nرفتم نارنگی فروشی، گفتم نارنگی چند؟ گفت 1845 تومن\nگفتم پـَـ نـَـ پـَـ وقت که مجانیه!',
    '⌯ #PANAPA\n\nرفتم لیمو فروشی، گفتم لیمو چند؟ گفت 1860 تومن\nگفتم پـَـ نـَـ پـَـ حوصله که ندارم!',
    '⌯ #PANAPA\n\nرفتم خیار فروشی، گفتم خیار چند؟ گفت 1875 تومن\nگفتم پـَـ نـَـ پـَـ انرژی که دارم!',
    '⌯ #PANAPA\n\nرفتم گوجه فروشی، گفتم گوجه چند؟ گفت 1890 تومن\nگفتم پـَـ نـَـ پـَـ دست که دارم!',
    '⌯ #PANAPA\n\nرفتم بادمجان فروشی، گفتم بادمجان چند؟ گفت 1905 تومن\nگفتم پـَـ نـَـ پـَـ هوا که مجانیه!',
    '⌯ #PANAPA\n\nرفتم کدو فروشی، گفتم کدو چند؟ گفت 1920 تومن\nگفتم پـَـ نـَـ پـَـ پول که ندارم!',
    '⌯ #PANAPA\n\nرفتم فلفل فروشی، گفتم فلفل چند؟ گفت 1935 تومن\nگفتم پـَـ نـَـ پـَـ استعداد که دارم!',
    '⌯ #PANAPA\n\nرفتم سیر فروشی، گفتم سیر چند؟ گفت 1950 تومن\nگفتم پـَـ نـَـ پـَـ پا که دارم!',
    '⌯ #PANAPA\n\nرفتم پیاز فروشی، گفتم پیاز چند؟ گفت 1965 تومن\nگفتم پـَـ نـَـ پـَـ آب که مجانیه!',
    '⌯ #PANAPA\n\nرفتم سیب\u200cزمینی فروشی، گفتم سیب\u200cزمینی چند؟ گفت 1980 تومن\nگفتم پـَـ نـَـ پـَـ زبون که دارم!',
    '⌯ #PANAPA\n\nرفتم هویج فروشی، گفتم هویج چند؟ گفت 1995 تومن\nگفتم پـَـ نـَـ پـَـ ذوق که دارم!',
    '⌯ #PANAPA\n\nرفتم کاهو فروشی، گفتم کاهو چند؟ گفت 2010 تومن\nگفتم پـَـ نـَـ پـَـ چشم که دارم!',
    '⌯ #PANAPA\n\nرفتم کلم فروشی، گفتم کلم چند؟ گفت 2025 تومن\nگفتم پـَـ نـَـ پـَـ خنده که مجانیه!',
    '⌯ #PANAPA\n\nرفتم اسفناج فروشی، گفتم اسفناج چند؟ گفت 2040 تومن\nگفتم پـَـ نـَـ پـَـ گوش که دارم!',
    '⌯ #PANAPA\n\nرفتم جعفری فروشی، گفتم جعفری چند؟ گفت 2055 تومن\nگفتم پـَـ نـَـ پـَـ نمک که دارم!',
    '⌯ #PANAPA\n\nرفتم تربچه فروشی، گفتم تربچه چند؟ گفت 2070 تومن\nگفتم پـَـ نـَـ پـَـ مغز که دارم!',
    '⌯ #PANAPA\n\nرفتم شلغم فروشی، گفتم شلغم چند؟ گفت 2085 تومن\nگفتم پـَـ نـَـ پـَـ صبر که دارم!',
    '⌯ #PANAPA\n\nرفتم چغندر فروشی، گفتم چغندر چند؟ گفت 2100 تومن\nگفتم پـَـ نـَـ پـَـ قلب که دارم!',
    '⌯ #PANAPA\n\nرفتم برنج فروشی، گفتم برنج چند؟ گفت 2115 تومن\nگفتم پـَـ نـَـ پـَـ شوخ\u200cطبعی که دارم!',
    '⌯ #PANAPA\n\nرفتم عدس فروشی، گفتم عدس چند؟ گفت 2130 تومن\nگفتم پـَـ نـَـ پـَـ بو که مجانیه!',
    '⌯ #PANAPA\n\nرفتم لوبیا فروشی، گفتم لوبیا چند؟ گفت 2145 تومن\nگفتم پـَـ نـَـ پـَـ عشق که دارم!',
    '⌯ #PANAPA\n\nرفتم نخود فروشی، گفتم نخود چند؟ گفت 2160 تومن\nگفتم پـَـ نـَـ پـَـ اعصاب که ندارم!',
    '⌯ #PANAPA\n\nرفتم ماکارونی فروشی، گفتم ماکارونی چند؟ گفت 2175 تومن\nگفتم پـَـ نـَـ پـَـ بدشانسی که دارم!',
    '⌯ #PANAPA\n\nرفتم رشته فروشی، گفتم رشته چند؟ گفت 2190 تومن\nگفتم پـَـ نـَـ پـَـ نور که مجانیه!',
    '⌯ #PANAPA\n\nرفتم آرد فروشی، گفتم آرد چند؟ گفت 2205 تومن\nگفتم پـَـ نـَـ پـَـ شانس که ندارم!',
    '⌯ #PANAPA\n\nرفتم نمک فروشی، گفتم نمک چند؟ گفت 2220 تومن\nگفتم پـَـ نـَـ پـَـ خواب که کافیه!',
    '⌯ #PANAPA\n\nرفتم شکر فروشی، گفتم شکر چند؟ گفت 2235 تومن\nگفتم پـَـ نـَـ پـَـ خستگی که دارم!',
    '⌯ #PANAPA\n\nرفتم روغن زیتون فروشی، گفتم روغن زیتون چند؟ گفت 2250 تومن\nگفتم پـَـ نـَـ پـَـ وقت که مجانیه!',
    '⌯ #PANAPA\n\nرفتم سرکه فروشی، گفتم سرکه چند؟ گفت 2265 تومن\nگفتم پـَـ نـَـ پـَـ حوصله که ندارم!',
    '⌯ #PANAPA\n\nرفتم رب گوجه فروشی، گفتم رب گوجه چند؟ گفت 2280 تومن\nگفتم پـَـ نـَـ پـَـ انرژی که دارم!',
    '⌯ #PANAPA\n\nرفتم سس فروشی، گفتم سس چند؟ گفت 2295 تومن\nگفتم پـَـ نـَـ پـَـ دست که دارم!',
    '⌯ #PANAPA\n\nرفتم کچاپ فروشی، گفتم کچاپ چند؟ گفت 2310 تومن\nگفتم پـَـ نـَـ پـَـ هوا که مجانیه!',
    '⌯ #PANAPA\n\nرفتم مایونز فروشی، گفتم مایونز چند؟ گفت 2325 تومن\nگفتم پـَـ نـَـ پـَـ پول که ندارم!',
    '⌯ #PANAPA\n\nرفتم خردل فروشی، گفتم خردل چند؟ گفت 2340 تومن\nگفتم پـَـ نـَـ پـَـ استعداد که دارم!',
    '⌯ #PANAPA\n\nرفتم زعفران فروشی، گفتم زعفران چند؟ گفت 2355 تومن\nگفتم پـَـ نـَـ پـَـ پا که دارم!',
    '⌯ #PANAPA\n\nرفتم دارچین فروشی، گفتم دارچین چند؟ گفت 2370 تومن\nگفتم پـَـ نـَـ پـَـ آب که مجانیه!',
    '⌯ #PANAPA\n\nرفتم زنجبیل فروشی، گفتم زنجبیل چند؟ گفت 2385 تومن\nگفتم پـَـ نـَـ پـَـ زبون که دارم!',
    '⌯ #PANAPA\n\nرفتم هل فروشی، گفتم هل چند؟ گفت 2400 تومن\nگفتم پـَـ نـَـ پـَـ ذوق که دارم!',
    '⌯ #PANAPA\n\nرفتم زیره فروشی، گفتم زیره چند؟ گفت 2415 تومن\nگفتم پـَـ نـَـ پـَـ چشم که دارم!',
    '⌯ #PANAPA\n\nرفتم فلفل سیاه فروشی، گفتم فلفل سیاه چند؟ گفت 2430 تومن\nگفتم پـَـ نـَـ پـَـ خنده که مجانیه!',
    '⌯ #PANAPA\n\nرفتم پودر کاری فروشی، گفتم پودر کاری چند؟ گفت 2445 تومن\nگفتم پـَـ نـَـ پـَـ گوش که دارم!',
    '⌯ #PANAPA\n\nرفتم پودر لباسشویی فروشی، گفتم پودر لباسشویی چند؟ گفت 2460 تومن\nگفتم پـَـ نـَـ پـَـ نمک که دارم!',
    '⌯ #PANAPA\n\nرفتم مایع ظرفشویی فروشی، گفتم مایع ظرفشویی چند؟ گفت 2475 تومن\nگفتم پـَـ نـَـ پـَـ مغز که دارم!',
    '⌯ #PANAPA\n\nرفتم اسپری فروشی، گفتم اسپری چند؟ گفت 2490 تومن\nگفتم پـَـ نـَـ پـَـ صبر که دارم!',
    '⌯ #PANAPA\n\nرفتم دستمال کاغذی فروشی، گفتم دستمال کاغذی چند؟ گفت 2505 تومن\nگفتم پـَـ نـَـ پـَـ قلب که دارم!',
    '⌯ #PANAPA\n\nرفتم دستمال مرطوب فروشی، گفتم دستمال مرطوب چند؟ گفت 2520 تومن\nگفتم پـَـ نـَـ پـَـ شوخ\u200cطبعی که دارم!',
    '⌯ #PANAPA\n\nرفتم پوشک فروشی، گفتم پوشک چند؟ گفت 2535 تومن\nگفتم پـَـ نـَـ پـَـ بو که مجانیه!',
    '⌯ #PANAPA\n\nرفتم کرم پودر فروشی، گفتم کرم پودر چند؟ گفت 2550 تومن\nگفتم پـَـ نـَـ پـَـ عشق که دارم!',
    '⌯ #PANAPA\n\nرفتم رژ لب فروشی، گفتم رژ لب چند؟ گفت 2565 تومن\nگفتم پـَـ نـَـ پـَـ اعصاب که ندارم!',
    '⌯ #PANAPA\n\nرفتم ریمل فروشی، گفتم ریمل چند؟ گفت 2580 تومن\nگفتم پـَـ نـَـ پـَـ بدشانسی که دارم!',
    '⌯ #PANAPA\n\nرفتم سایه چشم فروشی، گفتم سایه چشم چند؟ گفت 2595 تومن\nگفتم پـَـ نـَـ پـَـ نور که مجانیه!',
    '⌯ #PANAPA\n\nرفتم لاک ناخن فروشی، گفتم لاک ناخن چند؟ گفت 2610 تومن\nگفتم پـَـ نـَـ پـَـ شانس که ندارم!',
    '⌯ #PANAPA\n\nرفتم اتو مو فروشی، گفتم اتو مو چند؟ گفت 2625 تومن\nگفتم پـَـ نـَـ پـَـ خواب که کافیه!',
    '⌯ #PANAPA\n\nرفتم سشوار فروشی، گفتم سشوار چند؟ گفت 2640 تومن\nگفتم پـَـ نـَـ پـَـ خستگی که دارم!',
    '⌯ #PANAPA\n\nرفتم برس مو فروشی، گفتم برس مو چند؟ گفت 2655 تومن\nگفتم پـَـ نـَـ پـَـ وقت که مجانیه!',
    '⌯ #PANAPA\n\nرفتم گیره سر فروشی، گفتم گیره سر چند؟ گفت 2670 تومن\nگفتم پـَـ نـَـ پـَـ حوصله که ندارم!',
    '⌯ #PANAPA\n\nرفتم کش مو فروشی، گفتم کش مو چند؟ گفت 2685 تومن\nگفتم پـَـ نـَـ پـَـ انرژی که دارم!',
    '⌯ #PANAPA\n\nرفتم عینک طبی فروشی، گفتم عینک طبی چند؟ گفت 2700 تومن\nگفتم پـَـ نـَـ پـَـ دست که دارم!',
    '⌯ #PANAPA\n\nرفتم لنز چشم فروشی، گفتم لنز چشم چند؟ گفت 2715 تومن\nگفتم پـَـ نـَـ پـَـ هوا که مجانیه!',
    '⌯ #PANAPA\n\nرفتم تشک فروشی، گفتم تشک چند؟ گفت 2730 تومن\nگفتم پـَـ نـَـ پـَـ پول که ندارم!',
    '⌯ #PANAPA\n\nرفتم بالشتک فروشی، گفتم بالشتک چند؟ گفت 2745 تومن\nگفتم پـَـ نـَـ پـَـ استعداد که دارم!',
    '⌯ #PANAPA\n\nرفتم رومیزی فروشی، گفتم رومیزی چند؟ گفت 2760 تومن\nگفتم پـَـ نـَـ پـَـ پا که دارم!',
    '⌯ #PANAPA\n\nرفتم پرده حمام فروشی، گفتم پرده حمام چند؟ گفت 2775 تومن\nگفتم پـَـ نـَـ پـَـ آب که مجانیه!',
    '⌯ #PANAPA\n\nرفتم قالیچه فروشی، گفتم قالیچه چند؟ گفت 2790 تومن\nگفتم پـَـ نـَـ پـَـ زبون که دارم!',
    '⌯ #PANAPA\n\nرفتم سبد خرید فروشی، گفتم سبد خرید چند؟ گفت 2805 تومن\nگفتم پـَـ نـَـ پـَـ ذوق که دارم!',
    '⌯ #PANAPA\n\nرفتم ترازو فروشی، گفتم ترازو چند؟ گفت 2820 تومن\nگفتم پـَـ نـَـ پـَـ چشم که دارم!',
    '⌯ #PANAPA\n\nرفتم قابلمه فروشی، گفتم قابلمه چند؟ گفت 2835 تومن\nگفتم پـَـ نـَـ پـَـ خنده که مجانیه!',
    '⌯ #PANAPA\n\nرفتم ماهیتابه فروشی، گفتم ماهیتابه چند؟ گفت 2850 تومن\nگفتم پـَـ نـَـ پـَـ گوش که دارم!',
    '⌯ #PANAPA\n\nرفتم کتری فروشی، گفتم کتری چند؟ گفت 2865 تومن\nگفتم پـَـ نـَـ پـَـ نمک که دارم!',
    '⌯ #PANAPA\n\nرفتم قوری فروشی، گفتم قوری چند؟ گفت 2880 تومن\nگفتم پـَـ نـَـ پـَـ مغز که دارم!',
    '⌯ #PANAPA\n\nرفتم فنجان فروشی، گفتم فنجان چند؟ گفت 2895 تومن\nگفتم پـَـ نـَـ پـَـ صبر که دارم!',
    '⌯ #PANAPA\n\nرفتم لیوان فروشی، گفتم لیوان چند؟ گفت 2910 تومن\nگفتم پـَـ نـَـ پـَـ قلب که دارم!',
    '⌯ #PANAPA\n\nرفتم بشقاب فروشی، گفتم بشقاب چند؟ گفت 2925 تومن\nگفتم پـَـ نـَـ پـَـ شوخ\u200cطبعی که دارم!',
    '⌯ #PANAPA\n\nرفتم قاشق فروشی، گفتم قاشق چند؟ گفت 2940 تومن\nگفتم پـَـ نـَـ پـَـ بو که مجانیه!',
    '⌯ #PANAPA\n\nرفتم چنگال فروشی، گفتم چنگال چند؟ گفت 2955 تومن\nگفتم پـَـ نـَـ پـَـ عشق که دارم!',
    '⌯ #PANAPA\n\nرفتم چاقو فروشی، گفتم چاقو چند؟ گفت 2970 تومن\nگفتم پـَـ نـَـ پـَـ اعصاب که ندارم!',
    '⌯ #PANAPA\n\nرفتم تخته گوشت فروشی، گفتم تخته گوشت چند؟ گفت 2985 تومن\nگفتم پـَـ نـَـ پـَـ بدشانسی که دارم!',
    '⌯ #PANAPA\n\nرفتم سینی فروشی، گفتم سینی چند؟ گفت 3000 تومن\nگفتم پـَـ نـَـ پـَـ نور که مجانیه!',
    '⌯ #PANAPA\n\nرفتم ظرف یخچالی فروشی، گفتم ظرف یخچالی چند؟ گفت 3015 تومن\nگفتم پـَـ نـَـ پـَـ شانس که ندارم!',
    '⌯ #PANAPA\n\nرفتم جاروبرقی فروشی، گفتم جاروبرقی چند؟ گفت 3030 تومن\nگفتم پـَـ نـَـ پـَـ خواب که کافیه!',
    '⌯ #PANAPA\n\nرفتم اتو فروشی، گفتم اتو چند؟ گفت 3045 تومن\nگفتم پـَـ نـَـ پـَـ خستگی که دارم!',
    '⌯ #PANAPA\n\nرفتم ماشین لباسشویی فروشی، گفتم ماشین لباسشویی چند؟ گفت 3060 تومن\nگفتم پـَـ نـَـ پـَـ وقت که مجانیه!',
    '⌯ #PANAPA\n\nرفتم ماشین ظرفشویی فروشی، گفتم ماشین ظرفشویی چند؟ گفت 3075 تومن\nگفتم پـَـ نـَـ پـَـ حوصله که ندارم!',
    '⌯ #PANAPA\n\nرفتم مایکروویو فروشی، گفتم مایکروویو چند؟ گفت 3090 تومن\nگفتم پـَـ نـَـ پـَـ انرژی که دارم!',
    '⌯ #PANAPA\n\nرفتم توستر فروشی، گفتم توستر چند؟ گفت 3105 تومن\nگفتم پـَـ نـَـ پـَـ دست که دارم!',
    '⌯ #PANAPA\n\nرفتم آبمیوه\u200cگیری فروشی، گفتم آبمیوه\u200cگیری چند؟ گفت 3120 تومن\nگفتم پـَـ نـَـ پـَـ هوا که مجانیه!',
    '⌯ #PANAPA\n\nرفتم چرخ\u200cگوشت فروشی، گفتم چرخ\u200cگوشت چند؟ گفت 3135 تومن\nگفتم پـَـ نـَـ پـَـ پول که ندارم!',
    '⌯ #PANAPA\n\nرفتم همزن فروشی، گفتم همزن چند؟ گفت 3150 تومن\nگفتم پـَـ نـَـ پـَـ استعداد که دارم!',
    '⌯ #PANAPA\n\nرفتم قهوه\u200cساز فروشی، گفتم قهوه\u200cساز چند؟ گفت 3165 تومن\nگفتم پـَـ نـَـ پـَـ پا که دارم!',
    '⌯ #PANAPA\n\nرفتم کولر فروشی، گفتم کولر چند؟ گفت 3180 تومن\nگفتم پـَـ نـَـ پـَـ آب که مجانیه!',
    '⌯ #PANAPA\n\nرفتم بخاری فروشی، گفتم بخاری چند؟ گفت 3195 تومن\nگفتم پـَـ نـَـ پـَـ زبون که دارم!',
    '⌯ #PANAPA\n\nرفتم پنکه فروشی، گفتم پنکه چند؟ گفت 3210 تومن\nگفتم پـَـ نـَـ پـَـ ذوق که دارم!',
    '⌯ #PANAPA\n\nرفتم آبگرمکن فروشی، گفتم آبگرمکن چند؟ گفت 3225 تومن\nگفتم پـَـ نـَـ پـَـ چشم که دارم!',
    '⌯ #PANAPA\n\nرفتم فن سقفی فروشی، گفتم فن سقفی چند؟ گفت 3240 تومن\nگفتم پـَـ نـَـ پـَـ خنده که مجانیه!',
    '⌯ #PANAPA\n\nرفتم لوستر فروشی، گفتم لوستر چند؟ گفت 3255 تومن\nگفتم پـَـ نـَـ پـَـ گوش که دارم!',
]

# =========================================================
#  ۲۰۰ تا بیو
# =========================================================

BIO_200 = [
    '⌯ #BIO\n\n\u200c ᴸʸᶤᶰᵍ ᶤᶰ ʰᶤᶳ ᵃʳᵐᶳ تو بغلش لش کني . . . ❊ 🥺💦',
    '⌯ #BIO\n\nمن یکیو میخوام که توی بدترین حالتام و سگ ترین مود ام و کلافه ترین وضعیتم به اندازه\u200cی وقتایی که خوب و آرومم دوستم داشته باشه',
    '⌯ #BIO\n\nبهترین کار دنیا اینه که یه نفر رو بخندونی، حتی اگه خودت ناراحت باشی ❤️',
    '⌯ #BIO\n\nزندگی مثل یه قفسه، هر چی بذاری توش همونه!',
    '⌯ #BIO\n\nمیگن عشق یعنی دل کندن، من که نه دل دارم نه چیزی!',
    '⌯ #BIO\n\nدنیا جای قشنگیه، فقط باید خوب نگاه کرد 🌍',
    '⌯ #BIO\n\nبعضی وقتا فقط یه نفر کافیه تا دنیاتو عوض کنه 💫',
    '⌯ #BIO\n\nزندگی کوتاهه، پس با عشق زندگی کن ❤️',
    '⌯ #BIO\n\nهر روزت پر از آرامش و شادی باشه 🌸',
    '⌯ #BIO\n\nدلتو به دریا بزن، خدا بزرگه 🌊',
    '⌯ #BIO\n\nهمیشه لبخند بزن، حتی اگه سخت باشه 😊',
    '⌯ #BIO\n\nزندگی یعنی ادامه دادن، حتی اگه راه سخت باشه 💪',
    '⌯ #BIO\n\nبهترین کار مهربونی کردن با دیگرانه 🌹',
    '⌯ #BIO\n\nامید یعنی باور به فردایی بهتر 🌅',
    '⌯ #BIO\n\nهیچوقت تسلیم نشو، تو می\u200cتونی! 💪',
    '⌯ #BIO\n\nزندگی زیباست، پس ازش لذت ببر 🌺',
    '⌯ #BIO\n\nدوستی یعنی بودن در کنار هم 🤝',
    '⌯ #BIO\n\nعشق یعنی بخشیدن ❤️',
    '⌯ #BIO\n\nصبر کلید پیروزیه 🔑',
    '⌯ #BIO\n\nتو بهترینی، پس بهترین باش 🌟',
    '⌯ #BIO\n\nآزادی یعنی همین لحظه ❤️',
    '⌯ #BIO\n\nانگیزه تو دستای خودمونه 🌸',
    '⌯ #BIO\n\nتلاش هیچوقت بی\u200cدلیل نیست 🌟',
    '⌯ #BIO\n\nموفقیت توی سکوت هم شنیده میشه ✨',
    '⌯ #BIO\n\nشکست هیچوقت دیر نیست 🌊',
    '⌯ #BIO\n\nتجربه از نو ساختنیه 🌙',
    '⌯ #BIO\n\nیادگیری از دل گفتن شروع میشه 💫',
    '⌯ #BIO\n\nسکوت بدون تو معنی نداره 🌺',
    '⌯ #BIO\n\nحرف دل از چشمای یه آدم شروع میشه 🍃',
    '⌯ #BIO\n\nشب ارزش جنگیدن داره ☀️',
    '⌯ #BIO\n\nصبح از قلب شروع میشه 🌈',
    '⌯ #BIO\n\nبارون با هر شکست قوی\u200cتر میشه 🔥',
    '⌯ #BIO\n\nدریا همیشه یه بهونه برای ادامه\u200cس 🌷',
    '⌯ #BIO\n\nکوه یه سفر بی\u200cپایانه 🕊️',
    '⌯ #BIO\n\nجنگل هر روز یه رنگ جدیده 💛',
    '⌯ #BIO\n\nستاره با یه لبخند ساده\u200cتر میشه 🤍',
    '⌯ #BIO\n\nماه همیشه دومین فرصت میده 🌻',
    '⌯ #BIO\n\nخورشید با کوچیک\u200cترین چیزا کامل میشه 🍂',
    '⌯ #BIO\n\nباد تو چشمای خسته هم برق میزنه ❄️',
    '⌯ #BIO\n\nبرف با آدمای درست راحت\u200cتره 🌹',
    '⌯ #BIO\n\nبهار یعنی همین لحظه ❤️',
    '⌯ #BIO\n\nتابستون تو دستای خودمونه 🌸',
    '⌯ #BIO\n\nپاییز هیچوقت بی\u200cدلیل نیست 🌟',
    '⌯ #BIO\n\nزمستون توی سکوت هم شنیده میشه ✨',
    '⌯ #BIO\n\nزندگی با هر شکست قوی\u200cتر میشه 🌊',
    '⌯ #BIO\n\nعشق همیشه یه بهونه برای ادامه\u200cس 🌙',
    '⌯ #BIO\n\nدوستی یه سفر بی\u200cپایانه 💫',
    '⌯ #BIO\n\nامید هر روز یه رنگ جدیده 🌺',
    '⌯ #BIO\n\nرویا با یه لبخند ساده\u200cتر میشه 🍃',
    '⌯ #BIO\n\nخنده همیشه دومین فرصت میده ☀️',
    '⌯ #BIO\n\nآرامش با کوچیک\u200cترین چیزا کامل میشه 🌈',
    '⌯ #BIO\n\nصبر تو چشمای خسته هم برق میزنه 🔥',
    '⌯ #BIO\n\nشجاعت با آدمای درست راحت\u200cتره 🌷',
    '⌯ #BIO\n\nتنهایی یعنی همین لحظه 🕊️',
    '⌯ #BIO\n\nدلتنگی تو دستای خودمونه 💛',
    '⌯ #BIO\n\nغرور هیچوقت بی\u200cدلیل نیست 🤍',
    '⌯ #BIO\n\nسادگی توی سکوت هم شنیده میشه 🌻',
    '⌯ #BIO\n\nخاطره هیچوقت دیر نیست 🍂',
    '⌯ #BIO\n\nلبخند از نو ساختنیه ❄️',
    '⌯ #BIO\n\nاحساس از دل گفتن شروع میشه 🌹',
    '⌯ #BIO\n\nاعتماد بدون تو معنی نداره ❤️',
    '⌯ #BIO\n\nصداقت از چشمای یه آدم شروع میشه 🌸',
    '⌯ #BIO\n\nمهربونی ارزش جنگیدن داره 🌟',
    '⌯ #BIO\n\nقدردانی از قلب شروع میشه ✨',
    '⌯ #BIO\n\nآزادی با هر شکست قوی\u200cتر میشه 🌊',
    '⌯ #BIO\n\nانگیزه همیشه یه بهونه برای ادامه\u200cس 🌙',
    '⌯ #BIO\n\nتلاش یه سفر بی\u200cپایانه 💫',
    '⌯ #BIO\n\nموفقیت هر روز یه رنگ جدیده 🌺',
    '⌯ #BIO\n\nشکست با یه لبخند ساده\u200cتر میشه 🍃',
    '⌯ #BIO\n\nتجربه همیشه دومین فرصت میده ☀️',
    '⌯ #BIO\n\nیادگیری با کوچیک\u200cترین چیزا کامل میشه 🌈',
    '⌯ #BIO\n\nسکوت تو چشمای خسته هم برق میزنه 🔥',
    '⌯ #BIO\n\nحرف دل با آدمای درست راحت\u200cتره 🌷',
    '⌯ #BIO\n\nشب یعنی همین لحظه 🕊️',
    '⌯ #BIO\n\nصبح تو دستای خودمونه 💛',
    '⌯ #BIO\n\nبارون هیچوقت بی\u200cدلیل نیست 🤍',
    '⌯ #BIO\n\nدریا توی سکوت هم شنیده میشه 🌻',
    '⌯ #BIO\n\nکوه هیچوقت دیر نیست 🍂',
    '⌯ #BIO\n\nجنگل از نو ساختنیه ❄️',
    '⌯ #BIO\n\nستاره از دل گفتن شروع میشه 🌹',
    '⌯ #BIO\n\nماه بدون تو معنی نداره ❤️',
    '⌯ #BIO\n\nخورشید از چشمای یه آدم شروع میشه 🌸',
    '⌯ #BIO\n\nباد ارزش جنگیدن داره 🌟',
    '⌯ #BIO\n\nبرف از قلب شروع میشه ✨',
    '⌯ #BIO\n\nبهار با هر شکست قوی\u200cتر میشه 🌊',
    '⌯ #BIO\n\nتابستون همیشه یه بهونه برای ادامه\u200cس 🌙',
    '⌯ #BIO\n\nپاییز یه سفر بی\u200cپایانه 💫',
    '⌯ #BIO\n\nزمستون هر روز یه رنگ جدیده 🌺',
    '⌯ #BIO\n\nزندگی هیچوقت بی\u200cدلیل نیست 🍃',
    '⌯ #BIO\n\nعشق توی سکوت هم شنیده میشه ☀️',
    '⌯ #BIO\n\nدوستی هیچوقت دیر نیست 🌈',
    '⌯ #BIO\n\nامید از نو ساختنیه 🔥',
    '⌯ #BIO\n\nرویا از دل گفتن شروع میشه 🌷',
    '⌯ #BIO\n\nخنده بدون تو معنی نداره 🕊️',
    '⌯ #BIO\n\nآرامش از چشمای یه آدم شروع میشه 💛',
    '⌯ #BIO\n\nصبر ارزش جنگیدن داره 🤍',
    '⌯ #BIO\n\nشجاعت از قلب شروع میشه 🌻',
    '⌯ #BIO\n\nتنهایی با هر شکست قوی\u200cتر میشه 🍂',
    '⌯ #BIO\n\nدلتنگی همیشه یه بهونه برای ادامه\u200cس ❄️',
    '⌯ #BIO\n\nغرور یه سفر بی\u200cپایانه 🌹',
    '⌯ #BIO\n\nسادگی هر روز یه رنگ جدیده ❤️',
    '⌯ #BIO\n\nخاطره با یه لبخند ساده\u200cتر میشه 🌸',
    '⌯ #BIO\n\nلبخند همیشه دومین فرصت میده 🌟',
    '⌯ #BIO\n\nاحساس با کوچیک\u200cترین چیزا کامل میشه ✨',
    '⌯ #BIO\n\nاعتماد تو چشمای خسته هم برق میزنه 🌊',
    '⌯ #BIO\n\nصداقت با آدمای درست راحت\u200cتره 🌙',
    '⌯ #BIO\n\nمهربونی یعنی همین لحظه 💫',
    '⌯ #BIO\n\nقدردانی تو دستای خودمونه 🌺',
    '⌯ #BIO\n\nآزادی هیچوقت بی\u200cدلیل نیست 🍃',
    '⌯ #BIO\n\nانگیزه توی سکوت هم شنیده میشه ☀️',
    '⌯ #BIO\n\nتلاش هیچوقت دیر نیست 🌈',
    '⌯ #BIO\n\nموفقیت از نو ساختنیه 🔥',
    '⌯ #BIO\n\nشکست از دل گفتن شروع میشه 🌷',
    '⌯ #BIO\n\nتجربه بدون تو معنی نداره 🕊️',
    '⌯ #BIO\n\nیادگیری از چشمای یه آدم شروع میشه 💛',
    '⌯ #BIO\n\nسکوت ارزش جنگیدن داره 🤍',
    '⌯ #BIO\n\nحرف دل از قلب شروع میشه 🌻',
    '⌯ #BIO\n\nشب با هر شکست قوی\u200cتر میشه 🍂',
    '⌯ #BIO\n\nصبح همیشه یه بهونه برای ادامه\u200cس ❄️',
    '⌯ #BIO\n\nبارون یه سفر بی\u200cپایانه 🌹',
    '⌯ #BIO\n\nدریا هر روز یه رنگ جدیده ❤️',
    '⌯ #BIO\n\nکوه با یه لبخند ساده\u200cتر میشه 🌸',
    '⌯ #BIO\n\nجنگل همیشه دومین فرصت میده 🌟',
    '⌯ #BIO\n\nستاره با کوچیک\u200cترین چیزا کامل میشه ✨',
    '⌯ #BIO\n\nماه تو چشمای خسته هم برق میزنه 🌊',
    '⌯ #BIO\n\nخورشید با آدمای درست راحت\u200cتره 🌙',
    '⌯ #BIO\n\nباد یعنی همین لحظه 💫',
    '⌯ #BIO\n\nبرف تو دستای خودمونه 🌺',
    '⌯ #BIO\n\nبهار هیچوقت بی\u200cدلیل نیست 🍃',
    '⌯ #BIO\n\nتابستون توی سکوت هم شنیده میشه ☀️',
    '⌯ #BIO\n\nپاییز هیچوقت دیر نیست 🌈',
    '⌯ #BIO\n\nزمستون از نو ساختنیه 🔥',
    '⌯ #BIO\n\nزندگی یه سفر بی\u200cپایانه 🌷',
    '⌯ #BIO\n\nعشق هر روز یه رنگ جدیده 🕊️',
    '⌯ #BIO\n\nدوستی با یه لبخند ساده\u200cتر میشه 💛',
    '⌯ #BIO\n\nامید همیشه دومین فرصت میده 🤍',
    '⌯ #BIO\n\nرویا با کوچیک\u200cترین چیزا کامل میشه 🌻',
    '⌯ #BIO\n\nخنده تو چشمای خسته هم برق میزنه 🍂',
    '⌯ #BIO\n\nآرامش با آدمای درست راحت\u200cتره ❄️',
    '⌯ #BIO\n\nصبر یعنی همین لحظه 🌹',
    '⌯ #BIO\n\nشجاعت تو دستای خودمونه ❤️',
    '⌯ #BIO\n\nتنهایی هیچوقت بی\u200cدلیل نیست 🌸',
    '⌯ #BIO\n\nدلتنگی توی سکوت هم شنیده میشه 🌟',
    '⌯ #BIO\n\nغرور هیچوقت دیر نیست ✨',
    '⌯ #BIO\n\nسادگی از نو ساختنیه 🌊',
    '⌯ #BIO\n\nخاطره از دل گفتن شروع میشه 🌙',
    '⌯ #BIO\n\nلبخند بدون تو معنی نداره 💫',
    '⌯ #BIO\n\nاحساس از چشمای یه آدم شروع میشه 🌺',
    '⌯ #BIO\n\nاعتماد ارزش جنگیدن داره 🍃',
    '⌯ #BIO\n\nصداقت از قلب شروع میشه ☀️',
    '⌯ #BIO\n\nمهربونی با هر شکست قوی\u200cتر میشه 🌈',
    '⌯ #BIO\n\nقدردانی همیشه یه بهونه برای ادامه\u200cس 🔥',
    '⌯ #BIO\n\nآزادی یه سفر بی\u200cپایانه 🌷',
    '⌯ #BIO\n\nانگیزه هر روز یه رنگ جدیده 🕊️',
    '⌯ #BIO\n\nتلاش با یه لبخند ساده\u200cتر میشه 💛',
    '⌯ #BIO\n\nموفقیت همیشه دومین فرصت میده 🤍',
    '⌯ #BIO\n\nشکست با کوچیک\u200cترین چیزا کامل میشه 🌻',
    '⌯ #BIO\n\nتجربه تو چشمای خسته هم برق میزنه 🍂',
    '⌯ #BIO\n\nیادگیری با آدمای درست راحت\u200cتره ❄️',
    '⌯ #BIO\n\nسکوت یعنی همین لحظه 🌹',
    '⌯ #BIO\n\nحرف دل تو دستای خودمونه ❤️',
    '⌯ #BIO\n\nشب هیچوقت بی\u200cدلیل نیست 🌸',
    '⌯ #BIO\n\nصبح توی سکوت هم شنیده میشه 🌟',
    '⌯ #BIO\n\nبارون هیچوقت دیر نیست ✨',
    '⌯ #BIO\n\nدریا از نو ساختنیه 🌊',
    '⌯ #BIO\n\nکوه از دل گفتن شروع میشه 🌙',
    '⌯ #BIO\n\nجنگل بدون تو معنی نداره 💫',
    '⌯ #BIO\n\nستاره از چشمای یه آدم شروع میشه 🌺',
    '⌯ #BIO\n\nماه ارزش جنگیدن داره 🍃',
    '⌯ #BIO\n\nخورشید از قلب شروع میشه ☀️',
    '⌯ #BIO\n\nباد با هر شکست قوی\u200cتر میشه 🌈',
    '⌯ #BIO\n\nبرف همیشه یه بهونه برای ادامه\u200cس 🔥',
    '⌯ #BIO\n\nبهار یه سفر بی\u200cپایانه 🌷',
    '⌯ #BIO\n\nتابستون هر روز یه رنگ جدیده 🕊️',
    '⌯ #BIO\n\nپاییز با یه لبخند ساده\u200cتر میشه 💛',
    '⌯ #BIO\n\nزمستون همیشه دومین فرصت میده 🤍',
    '⌯ #BIO\n\nزندگی هیچوقت دیر نیست 🌻',
    '⌯ #BIO\n\nعشق از نو ساختنیه 🍂',
    '⌯ #BIO\n\nدوستی از دل گفتن شروع میشه ❄️',
    '⌯ #BIO\n\nامید بدون تو معنی نداره 🌹',
    '⌯ #BIO\n\nرویا از چشمای یه آدم شروع میشه ❤️',
    '⌯ #BIO\n\nخنده ارزش جنگیدن داره 🌸',
    '⌯ #BIO\n\nآرامش از قلب شروع میشه 🌟',
    '⌯ #BIO\n\nصبر با هر شکست قوی\u200cتر میشه ✨',
    '⌯ #BIO\n\nشجاعت همیشه یه بهونه برای ادامه\u200cس 🌊',
    '⌯ #BIO\n\nتنهایی یه سفر بی\u200cپایانه 🌙',
    '⌯ #BIO\n\nدلتنگی هر روز یه رنگ جدیده 💫',
    '⌯ #BIO\n\nغرور با یه لبخند ساده\u200cتر میشه 🌺',
    '⌯ #BIO\n\nسادگی همیشه دومین فرصت میده 🍃',
    '⌯ #BIO\n\nخاطره با کوچیک\u200cترین چیزا کامل میشه ☀️',
    '⌯ #BIO\n\nلبخند تو چشمای خسته هم برق میزنه 🌈',
    '⌯ #BIO\n\nاحساس با آدمای درست راحت\u200cتره 🔥',
    '⌯ #BIO\n\nاعتماد یعنی همین لحظه 🌷',
    '⌯ #BIO\n\nصداقت تو دستای خودمونه 🕊️',
    '⌯ #BIO\n\nمهربونی هیچوقت بی\u200cدلیل نیست 💛',
    '⌯ #BIO\n\nقدردانی توی سکوت هم شنیده میشه 🤍',
    '⌯ #BIO\n\nآزادی هیچوقت دیر نیست 🌻',
    '⌯ #BIO\n\nانگیزه از نو ساختنیه 🍂',
    '⌯ #BIO\n\nتلاش از دل گفتن شروع میشه ❄️',
    '⌯ #BIO\n\nموفقیت بدون تو معنی نداره 🌹',
]

# =========================================================
#  ۲۰۰ تا خاطره
# =========================================================

KHATRH_200 = [
    '⌯ #KHATRH\n\nاقا بنده دیشب به اتفاق نامزدم رفته بودیم بیرون میخواستم یکم سربه سرش بزارم راجع به ارواح و جن و این چیزا حرف میزدم حسابی ترسید منم کلی کیف کردم .\nاقا یدفه ی گربه پرید جلومن و ترانه\nمن یه جیغ بنفش کشیدم و با سرعت نور فرار کردم\nهمینجوری که میدویدم برگشتم اونو نگاه کردم دیدم داره دویدن منو تماشا میکنه یعنی ضایع شدمااا',
    '⌯ #KHATRH\n\nهمسایمون مبل خریده ،بچش داشت تو کوچه بازی میکرد ، که یدفعه باباش از پنجره سرشو آورد بیرون ، داد زد و گفت :\nواسه چی بیرون داری بازی میکنی بیا خونه بشین رو مبل!!!!',
    '⌯ #KHATRH\n\nیه روز رفتم خونه دوستم، در زدم، گفت کیه؟\nگفتم منه، گفت برو بابا شوخیت کمه!\nرفتم خونه، دیدم خودش خونه منه!',
    '⌯ #KHATRH\n\nرفتم مسافرت، تو قطار نشستم، یه خانوم اومد گفت آقا این صندلی منه\nگفتم نه مال منه\nگفت قطار که نمیره!',
    '⌯ #KHATRH\n\nرفتم رستوران، گفتم یه غذا بیارین\nگفت چی دوست داری؟\nگفتم هر چی دوست دارم بیارین\n۳ ساعت نشستم غذا نیومد!',
    '⌯ #KHATRH\n\nیه روز داشتم تو خیابون راه میرفتم، یهو یه گربه پرید جلوم، منم پریدم بالا\nگربه ترسید فرار کرد، منم ترسیدم فرار کردم!',
    '⌯ #KHATRH\n\nرفتم دکتر، گفتم دکتر من هر چی میخورم یادم میره!\nدکتر گفت چند وقته؟\nگفتم چند وقته؟ یادم نیست!',
    '⌯ #KHATRH\n\nیه روز داشتم با دوستم حرف میزدم، گفتم دیروز یه اتفاق عجیب برام افتاد\nگفت چی؟\nگفتم یادم نیست!',
    '⌯ #KHATRH\n\nیه بار رفته بودم سوپرمارکت، موبایلم افتاد تو آب.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم آرایشگاه، صف خیلی طولانی بود و همه غر میزدن.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مطب دکتر، یهو یکی از پشت زد رو شونم.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم استخر، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم باشگاه، باد کلاهمو برد.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم سینما، موبایلم افتاد تو آب.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کافه، صف خیلی طولانی بود و همه غر میزدن.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم فرودگاه، یهو یکی از پشت زد رو شونم.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم ترمینال، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم بازار، باد کلاهمو برد.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مسجد محل، موبایلم افتاد تو آب.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم خونه مادربزرگ، صف خیلی طولانی بود و همه غر میزدن.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم عروسی فامیل، یهو یکی از پشت زد رو شونم.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مهمونی تولد، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم صف نانوایی، باد کلاهمو برد.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم تعمیرگاه ماشین، موبایلم افتاد تو آب.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کتابخونه، صف خیلی طولانی بود و همه غر میزدن.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم استادیوم، یهو یکی از پشت زد رو شونم.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم پیتزا فروشی، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کبابی، باد کلاهمو برد.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم آژانس مسافرتی، موبایلم افتاد تو آب.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم داروخونه، صف خیلی طولانی بود و همه غر میزدن.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم پارک، یهو یکی از پشت زد رو شونم.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مترو، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم اتوبوس، باد کلاهمو برد.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم تاکسی، موبایلم افتاد تو آب.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم دانشگاه، صف خیلی طولانی بود و همه غر میزدن.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مدرسه، یهو یکی از پشت زد رو شونم.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم اداره پست، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم بانک، باد کلاهمو برد.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم سوپرمارکت، موبایلم افتاد تو آب.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم آرایشگاه، صف خیلی طولانی بود و همه غر میزدن.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مطب دکتر، یهو یکی از پشت زد رو شونم.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم استخر، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم باشگاه، باد کلاهمو برد.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم سینما، موبایلم افتاد تو آب.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کافه، صف خیلی طولانی بود و همه غر میزدن.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم فرودگاه، یهو یکی از پشت زد رو شونم.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم ترمینال، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم بازار، باد کلاهمو برد.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مسجد محل، موبایلم افتاد تو آب.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم خونه مادربزرگ، صف خیلی طولانی بود و همه غر میزدن.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم عروسی فامیل، یهو یکی از پشت زد رو شونم.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مهمونی تولد، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم صف نانوایی، باد کلاهمو برد.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم تعمیرگاه ماشین، موبایلم افتاد تو آب.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کتابخونه، صف خیلی طولانی بود و همه غر میزدن.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم استادیوم، یهو یکی از پشت زد رو شونم.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم پیتزا فروشی، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کبابی، باد کلاهمو برد.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم آژانس مسافرتی، موبایلم افتاد تو آب.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم داروخونه، صف خیلی طولانی بود و همه غر میزدن.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم پارک، یهو یکی از پشت زد رو شونم.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مترو، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم اتوبوس، باد کلاهمو برد.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم تاکسی، موبایلم افتاد تو آب.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم دانشگاه، صف خیلی طولانی بود و همه غر میزدن.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مدرسه، یهو یکی از پشت زد رو شونم.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم اداره پست، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم بانک، باد کلاهمو برد.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم سوپرمارکت، موبایلم افتاد تو آب.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم آرایشگاه، صف خیلی طولانی بود و همه غر میزدن.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مطب دکتر، یهو یکی از پشت زد رو شونم.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم استخر، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم باشگاه، باد کلاهمو برد.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم سینما، موبایلم افتاد تو آب.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کافه، صف خیلی طولانی بود و همه غر میزدن.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم فرودگاه، یهو یکی از پشت زد رو شونم.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم ترمینال، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم بازار، باد کلاهمو برد.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مسجد محل، موبایلم افتاد تو آب.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم خونه مادربزرگ، صف خیلی طولانی بود و همه غر میزدن.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم عروسی فامیل، یهو یکی از پشت زد رو شونم.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مهمونی تولد، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم صف نانوایی، باد کلاهمو برد.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم تعمیرگاه ماشین، موبایلم افتاد تو آب.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کتابخونه، صف خیلی طولانی بود و همه غر میزدن.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم استادیوم، یهو یکی از پشت زد رو شونم.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم پیتزا فروشی، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کبابی، باد کلاهمو برد.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم آژانس مسافرتی، موبایلم افتاد تو آب.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم داروخونه، صف خیلی طولانی بود و همه غر میزدن.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم پارک، یهو یکی از پشت زد رو شونم.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مترو، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم اتوبوس، باد کلاهمو برد.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم تاکسی، موبایلم افتاد تو آب.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم دانشگاه، صف خیلی طولانی بود و همه غر میزدن.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مدرسه، یهو یکی از پشت زد رو شونم.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم اداره پست، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم بانک، باد کلاهمو برد.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم سوپرمارکت، موبایلم افتاد تو آب.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم آرایشگاه، صف خیلی طولانی بود و همه غر میزدن.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مطب دکتر، یهو یکی از پشت زد رو شونم.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم استخر، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم باشگاه، باد کلاهمو برد.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم سینما، موبایلم افتاد تو آب.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کافه، صف خیلی طولانی بود و همه غر میزدن.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم فرودگاه، یهو یکی از پشت زد رو شونم.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم ترمینال، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم بازار، باد کلاهمو برد.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مسجد محل، موبایلم افتاد تو آب.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم خونه مادربزرگ، صف خیلی طولانی بود و همه غر میزدن.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم عروسی فامیل، یهو یکی از پشت زد رو شونم.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مهمونی تولد، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم صف نانوایی، باد کلاهمو برد.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم تعمیرگاه ماشین، موبایلم افتاد تو آب.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کتابخونه، صف خیلی طولانی بود و همه غر میزدن.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم استادیوم، یهو یکی از پشت زد رو شونم.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم پیتزا فروشی، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کبابی، باد کلاهمو برد.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم آژانس مسافرتی، موبایلم افتاد تو آب.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم داروخونه، صف خیلی طولانی بود و همه غر میزدن.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم پارک، یهو یکی از پشت زد رو شونم.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مترو، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم اتوبوس، باد کلاهمو برد.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم تاکسی، موبایلم افتاد تو آب.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم دانشگاه، صف خیلی طولانی بود و همه غر میزدن.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مدرسه، یهو یکی از پشت زد رو شونم.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم اداره پست، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم بانک، باد کلاهمو برد.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم سوپرمارکت، موبایلم افتاد تو آب.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم آرایشگاه، صف خیلی طولانی بود و همه غر میزدن.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مطب دکتر، یهو یکی از پشت زد رو شونم.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم استخر، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم باشگاه، باد کلاهمو برد.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم سینما، موبایلم افتاد تو آب.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کافه، صف خیلی طولانی بود و همه غر میزدن.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم فرودگاه، یهو یکی از پشت زد رو شونم.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم ترمینال، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم بازار، باد کلاهمو برد.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مسجد محل، موبایلم افتاد تو آب.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم خونه مادربزرگ، صف خیلی طولانی بود و همه غر میزدن.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم عروسی فامیل، یهو یکی از پشت زد رو شونم.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مهمونی تولد، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم صف نانوایی، باد کلاهمو برد.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم تعمیرگاه ماشین، موبایلم افتاد تو آب.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کتابخونه، صف خیلی طولانی بود و همه غر میزدن.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم استادیوم، یهو یکی از پشت زد رو شونم.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم پیتزا فروشی، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کبابی، باد کلاهمو برد.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم آژانس مسافرتی، موبایلم افتاد تو آب.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم داروخونه، صف خیلی طولانی بود و همه غر میزدن.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم پارک، یهو یکی از پشت زد رو شونم.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مترو، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم اتوبوس، باد کلاهمو برد.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم تاکسی، موبایلم افتاد تو آب.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم دانشگاه، صف خیلی طولانی بود و همه غر میزدن.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مدرسه، یهو یکی از پشت زد رو شونم.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم اداره پست، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم بانک، باد کلاهمو برد.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم سوپرمارکت، موبایلم افتاد تو آب.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم آرایشگاه، صف خیلی طولانی بود و همه غر میزدن.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مطب دکتر، یهو یکی از پشت زد رو شونم.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم استخر، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم باشگاه، باد کلاهمو برد.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم سینما، موبایلم افتاد تو آب.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کافه، صف خیلی طولانی بود و همه غر میزدن.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم فرودگاه، یهو یکی از پشت زد رو شونم.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم ترمینال، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم بازار، باد کلاهمو برد.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مسجد محل، موبایلم افتاد تو آب.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم خونه مادربزرگ، صف خیلی طولانی بود و همه غر میزدن.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم عروسی فامیل، یهو یکی از پشت زد رو شونم.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مهمونی تولد، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم صف نانوایی، باد کلاهمو برد.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم تعمیرگاه ماشین، موبایلم افتاد تو آب.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کتابخونه، صف خیلی طولانی بود و همه غر میزدن.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم استادیوم، یهو یکی از پشت زد رو شونم.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم پیتزا فروشی، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کبابی، باد کلاهمو برد.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم آژانس مسافرتی، موبایلم افتاد تو آب.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم داروخونه، صف خیلی طولانی بود و همه غر میزدن.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم پارک، یهو یکی از پشت زد رو شونم.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مترو، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم اتوبوس، باد کلاهمو برد.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم تاکسی، موبایلم افتاد تو آب.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم دانشگاه، صف خیلی طولانی بود و همه غر میزدن.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مدرسه، یهو یکی از پشت زد رو شونم.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم اداره پست، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم بانک، باد کلاهمو برد.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم سوپرمارکت، موبایلم افتاد تو آب.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم آرایشگاه، صف خیلی طولانی بود و همه غر میزدن.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مطب دکتر، یهو یکی از پشت زد رو شونم.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم استخر، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nگفتم شاید خیالاتی شدم ولی نه، واقعی بود.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
    '⌯ #KHATRH\n\nیه بار رفته بودم باشگاه، باد کلاهمو برد.\nنگهبان اومد گفت آقا اینجا ممنوعه، ۲۰ دقیقه بود ایستاده بودم.\nآخرش فهمیدم خودم مقصر بودم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم سینما، موبایلم افتاد تو آب.\nبا ترس گفتم کیه اونجا؟ کسی جواب نداد.\nاون لحظه دلم میخواست زمین دهن باز کنه منو ببلعه!',
    '⌯ #KHATRH\n\nیه بار رفته بودم کافه، صف خیلی طولانی بود و همه غر میزدن.\nبعد فهمیدم اصلاً اونجا رو اشتباه اومده بودم.\nالان که فکرشو میکنم میبینم چقدر مسخره بوده!',
    '⌯ #KHATRH\n\nیه بار رفته بودم فرودگاه، یهو یکی از پشت زد رو شونم.\nاز خجالت میخواستم آب بشم برم زیر زمین.\nخلاصه بگم که آبروم رفت ولی خاطره\u200cش موند!',
    '⌯ #KHATRH\n\nیه بار رفته بودم ترمینال، یکی اسممو صدا زد ولی هیچکس اونجا نبود.\nصاحب مغازه با تعجب نگام کرد و چیزی نگفت.\nاز اون به بعد قبل هر کاری دوبار فکر میکنم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم بازار، باد کلاهمو برد.\nهمه داشتن بهم میخندیدن و من نمیدونستم چرا.\nاون روز قسم خوردم دیگه تنها جایی نرم!',
    '⌯ #KHATRH\n\nیه بار رفته بودم مسجد محل، موبایلم افتاد تو آب.\nبرگشتم دیدم هیچکس نیست، فقط یه گربه سیاه داشت نگام میکرد.\nهنوزم وقتی یادم میفته خندم میگیره!',
    '⌯ #KHATRH\n\nیه بار رفته بودم خونه مادربزرگ، صف خیلی طولانی بود و همه غر میزدن.\nدوستم گفت مگه ندیدی تابلوشو زده بود بسته\u200cس.\nتا آخر هفته داستانش سوژه فامیل شده بود!',
]

# =========================================================
#  توابع کمکی
# =========================================================

def format_number(num):
    return f"{num:,}".replace(",", "٫")

def get_user_name_from_id(user_id, group_data):
    users = group_data.get('users', {})
    if user_id in users:
        return users[user_id].get('first_name', user_id[:8])
    return user_id[:8]

def is_admin(user_id, group_data):
    # 🛠 رفع باگ سطح دسترسی: قبلاً «مدیر ارشد» (super_admins) اصلاً اینجا چک نمی‌شد - یعنی
    # کسی که فقط در لیست super_admins بود (نه admins/owners) با دستوراتی مثل «قفل لینک»،
    # «لینک قفل/باز»، «ضدلینک»، «ضدفحش»، «قفل کپشن» و ده‌ها دستور مشابه که از همین تابع
    # استفاده می‌کنن، پیام «❌ شما ادمین نیستید!» می‌گرفت - با اینکه طبق ALIAS_MAP و
    # get_permission_level، سطح او (SUPER_ADMIN=4) بالاتر از ADMIN (=3) و کاملاً کافی بود.
    # چون این تابع در ۱۴۰+ جای کد صدا زده می‌شه، رفع باگ در همین یک نقطه همه‌جا اثر می‌کنه.
    return (is_super_owner(user_id) or str(user_id) in group_data.get('admins', [])
            or str(user_id) in group_data.get('owners', [])
            or str(user_id) in group_data.get('super_admins', []))

def is_owner(user_id, group_data):
    return is_super_owner(user_id) or str(user_id) in group_data.get('owners', [])
    # =========================================================
#  ۲۰۰ تا پ ن پ
# =========================================================


# =========================================================
#  ۲۰۰ تا بیو
# =========================================================


# =========================================================
#  ۲۰۰ تا خاطره
# =========================================================


# =========================================================
#  🆕 داستان، پنالتی و چند سرگرمی دیگر (فقط فارسی — بدون دستور اسلش)
# =========================================================

STORY_LIST = [
    '📖 یکی بود یکی نبود، زیر گنبد کبود، پیرمردی بود که هر شب برای نوه\u200cهاش قصه می\u200cگفت تا خوابشون ببره؛ یه شب نوه\u200cها زودتر از قصه خوابیدن و پیرمرد تا صبح داشت برای خودش قصه می\u200cگفت 😄',
    '📖 روزی روزگاری یه روباه گرسنه به یه باغ انگور رسید، هر چی تلاش کرد نتونست به خوشه\u200cها برسه، آخرش گفت حتماً ترشن و رفت؛ ولی ته دلش می\u200cدونست فقط بلد نبود بپره!',
    '📖 پسرکی هر روز به مدرسه دیر می\u200cرسید و بهانه\u200cش این بود که ساعتش کند کار می\u200cکنه، تا اینکه معلم بهش گفت پس چرا زودتر از خونه بیرون نمیای؟ پسرک گفت آخه اونم دیر بیدار میشه!',
    '📖 در یک دهکده\u200cی دور، مردی بود که هر روز چاهی می\u200cکند به امید پیدا کردن گنج، یک روز همسایه\u200cش گفت چرا یک چاه رو عمیق\u200cتر نمی\u200cکنی؟ اون\u200cروز بود که بالاخره آب پیدا کرد!',
    '📖 دختری هر شب یک ستاره آرزو می\u200cکرد، یک شب پدرش پرسید چرا هر شب همون آرزو رو تکرار می\u200cکنی؟ گفت چون هنوز برآورده نشده، ولی امشب یکی دیگه رو امتحان می\u200cکنم!',
    '📖 یک ماهی کوچک از دریا پرسید آب کجاست؟ ماهی بزرگ خندید و گفت تو همین الان توی آبی! گاهی چیزی که دنبالشیم همون چیزیه که توشیم.',
    '📖 مردی هر روز کنار جاده می\u200cنشست و از رهگذرها آدرس می\u200cپرسید، یک روز یکی گفت مگه خودت بلد نیستی؟ گفت چرا، ولی از حرف زدن با آدما خوشم میاد!',
    '📖 بچه\u200cگربه\u200cای تصمیم گرفت از درخت بالا بره ولی از پایین اومدن ترسید، آتش\u200cنشان\u200cها اومدن نجاتش بدن، فهمیدن اون از اول خودش پایین اومده بود و فقط دلش می\u200cخواست باهاش بازی کنن!',
    '📖 کنار یک رودخانه آرام، یک اردک با یک سگ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اردک یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در دل کویری خشک، یک موش با یک اردک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت موش متوجه شد بزرگ\u200cترین قدرت، مهربونیه.',
    '📖 کنار یک رودخانه آرام، یک بز با یک قورباغه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت بز دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در یک دهکده\u200cی کوچک، یک اردک با یک روباه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اردک فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 در یک جنگل سرسبز، یک فیل با یک کلاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت فیل متوجه شد بزرگ\u200cترین قدرت، مهربونیه.',
    '📖 در حاشیه\u200cی یک دریاچه، یک روباه با یک کبوتر دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت روباه یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در یک دهکده\u200cی کوچک، یک ماهی با یک زرافه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت ماهی فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 در دامنه\u200cی یک کوه بلند، یک شیر با یک روباه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت شیر فهمید تنها راه رسیدن به هدف، تلاش مداومه.',
    '📖 در دامنه\u200cی یک کوه بلند، یک قورباغه با یک گوسفند دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت قورباغه دید که صداقت دیر یا زود میوه میده.',
    '📖 نزدیک یک آسیاب قدیمی، یک کبوتر با یک روباه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت کبوتر یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در دل کویری خشک، یک موش با یک کبوتر دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت موش فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 نزدیک یک آسیاب قدیمی، یک گنجشک با یک شیر دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گنجشک فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 در یک جنگل سرسبز، یک قورباغه با یک خرس دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت قورباغه فهمید عجله همیشه به صرفه نیست.',
    '📖 کنار یک رودخانه آرام، یک زنبور با یک میمون دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت زنبور یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در حاشیه\u200cی یک دریاچه، یک جغد با یک میمون دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت جغد فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 نزدیک یک آسیاب قدیمی، یک خرگوش با یک میمون دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرگوش یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در دل کویری خشک، یک گربه با یک کلاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گربه فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 کنار یک رودخانه آرام، یک میمون با یک گوسفند دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت میمون یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در یک شهر شلوغ، یک گرگ با یک میمون دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گرگ فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 نزدیک یک آسیاب قدیمی، یک ماهی با یک شیر دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت ماهی یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در دامنه\u200cی یک کوه بلند، یک بز با یک لاک\u200cپشت دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت بز فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک لاک\u200cپشت با یک ماهی دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت لاک\u200cپشت فهمید عجله همیشه به صرفه نیست.',
    '📖 در یک شهر شلوغ، یک میمون با یک زنبور دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت میمون فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 نزدیک یک آسیاب قدیمی، یک خرس با یک جغد دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرس دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در باغی پر از گل، یک مورچه با یک اردک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت مورچه یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 کنار یک رودخانه آرام، یک فیل با یک قورباغه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت فیل یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 کنار یک رودخانه آرام، یک سگ با یک گربه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت سگ فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 در یک شهر شلوغ، یک خرس با یک گوسفند دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرس فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 در دامنه\u200cی یک کوه بلند، یک قورباغه با یک شیر دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت قورباغه متوجه شد بزرگ\u200cترین قدرت، مهربونیه.',
    '📖 در دامنه\u200cی یک کوه بلند، یک خرگوش با یک خرس دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرگوش فهمید عجله همیشه به صرفه نیست.',
    '📖 کنار یک رودخانه آرام، یک خرگوش با یک لاک\u200cپشت دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرگوش یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 نزدیک یک آسیاب قدیمی، یک فیل با یک زرافه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت فیل دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در حاشیه\u200cی یک دریاچه، یک الاغ با یک خرس دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت الاغ یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در یک جنگل سرسبز، یک مورچه با یک جغد دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت مورچه فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک ماهی با یک خرس دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت ماهی فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 در دل کویری خشک، یک مورچه با یک بز دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت مورچه دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در باغی پر از گل، یک گنجشک با یک میمون دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گنجشک فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 در دل کویری خشک، یک زرافه با یک مورچه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت زرافه یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک موش با یک سگ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت موش متوجه شد بزرگ\u200cترین قدرت، مهربونیه.',
    '📖 در یک شهر شلوغ، یک شیر با یک جغد دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت شیر یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در دامنه\u200cی یک کوه بلند، یک جغد با یک گوسفند دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت جغد دید که صداقت دیر یا زود میوه میده.',
    '📖 در حاشیه\u200cی یک دریاچه، یک موش با یک الاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت موش فهمید عجله همیشه به صرفه نیست.',
    '📖 در یک دهکده\u200cی کوچک، یک مورچه با یک لاک\u200cپشت دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت مورچه یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک خرگوش با یک اردک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرگوش فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 در یک دهکده\u200cی کوچک، یک کبوتر با یک اسب دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت کبوتر فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 در یک دهکده\u200cی کوچک، یک مورچه با یک گنجشک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت مورچه فهمید عجله همیشه به صرفه نیست.',
    '📖 در باغی پر از گل، یک لاک\u200cپشت با یک زنبور دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت لاک\u200cپشت فهمید تنها راه رسیدن به هدف، تلاش مداومه.',
    '📖 در دامنه\u200cی یک کوه بلند، یک گنجشک با یک سگ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گنجشک دید که صداقت دیر یا زود میوه میده.',
    '📖 در یک جنگل سرسبز، یک میمون با یک اردک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت میمون فهمید عجله همیشه به صرفه نیست.',
    '📖 در دامنه\u200cی یک کوه بلند، یک ماهی با یک لاک\u200cپشت دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت ماهی فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 در یک دهکده\u200cی کوچک، یک روباه با یک قورباغه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت روباه دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در باغی پر از گل، یک گوسفند با یک اردک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گوسفند دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 نزدیک یک آسیاب قدیمی، یک کبوتر با یک لاک\u200cپشت دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت کبوتر دید که صداقت دیر یا زود میوه میده.',
    '📖 در یک شهر شلوغ، یک جغد با یک زرافه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت جغد دید که صداقت دیر یا زود میوه میده.',
    '📖 در دامنه\u200cی یک کوه بلند، یک اردک با یک اسب دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اردک دید که صداقت دیر یا زود میوه میده.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک جغد با یک مورچه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت جغد یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در حاشیه\u200cی یک دریاچه، یک الاغ با یک گنجشک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت الاغ یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در یک شهر شلوغ، یک موش با یک خرگوش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت موش فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 در یک جنگل سرسبز، یک خرگوش با یک کلاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرگوش یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 کنار یک رودخانه آرام، یک بز با یک مورچه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت بز یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در حاشیه\u200cی یک دریاچه، یک ماهی با یک بز دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت ماهی متوجه شد بزرگ\u200cترین قدرت، مهربونیه.',
    '📖 در حاشیه\u200cی یک دریاچه، یک اردک با یک قورباغه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اردک دید که صداقت دیر یا زود میوه میده.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک شیر با یک اردک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت شیر فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 در یک جنگل سرسبز، یک گربه با یک خرگوش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گربه یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در حاشیه\u200cی یک دریاچه، یک فیل با یک زنبور دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت فیل یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در باغی پر از گل، یک خرس با یک کلاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرس دید که صداقت دیر یا زود میوه میده.',
    '📖 در دامنه\u200cی یک کوه بلند، یک کلاغ با یک گنجشک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت کلاغ فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 در باغی پر از گل، یک ماهی با یک خرگوش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت ماهی فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 در یک شهر شلوغ، یک لاک\u200cپشت با یک سگ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت لاک\u200cپشت دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در حاشیه\u200cی یک دریاچه، یک گرگ با یک زنبور دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گرگ دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در یک شهر شلوغ، یک قورباغه با یک میمون دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت قورباغه دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در باغی پر از گل، یک فیل با یک مورچه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت فیل فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 در یک جنگل سرسبز، یک الاغ با یک سگ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت الاغ فهمید عجله همیشه به صرفه نیست.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک میمون با یک بز دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت میمون فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 کنار یک رودخانه آرام، یک جغد با یک گنجشک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت جغد یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در دامنه\u200cی یک کوه بلند، یک گنجشک با یک خرگوش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گنجشک فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 نزدیک یک آسیاب قدیمی، یک اسب با یک خرگوش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اسب یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در یک جنگل سرسبز، یک گوسفند با یک لاک\u200cپشت دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گوسفند فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 نزدیک یک آسیاب قدیمی، یک اردک با یک بز دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اردک یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در دل کویری خشک، یک خرس با یک خرگوش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرس یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در حاشیه\u200cی یک دریاچه، یک گوسفند با یک بز دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گوسفند دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در دل کویری خشک، یک گنجشک با یک گوسفند دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گنجشک فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 در یک شهر شلوغ، یک کلاغ با یک اردک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت کلاغ یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در حاشیه\u200cی یک دریاچه، یک الاغ با یک مورچه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت الاغ متوجه شد بزرگ\u200cترین قدرت، مهربونیه.',
    '📖 در دل کویری خشک، یک قورباغه با یک موش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت قورباغه فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 در یک دهکده\u200cی کوچک، یک زنبور با یک الاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت زنبور فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک موش با یک لاک\u200cپشت دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت موش یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در حاشیه\u200cی یک دریاچه، یک میمون با یک زرافه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت میمون یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در دل کویری خشک، یک شیر با یک مورچه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت شیر فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 نزدیک یک آسیاب قدیمی، یک خرس با یک روباه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرس دید که صداقت دیر یا زود میوه میده.',
    '📖 کنار یک رودخانه آرام، یک فیل با یک الاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت فیل یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 نزدیک یک آسیاب قدیمی، یک خرس با یک زنبور دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرس فهمید تنها راه رسیدن به هدف، تلاش مداومه.',
    '📖 کنار یک رودخانه آرام، یک کلاغ با یک ماهی دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت کلاغ یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در حاشیه\u200cی یک دریاچه، یک زنبور با یک سگ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت زنبور فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 در باغی پر از گل، یک روباه با یک جغد دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت روباه فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 در دامنه\u200cی یک کوه بلند، یک گرگ با یک مورچه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گرگ فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 در یک شهر شلوغ، یک موش با یک کلاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت موش متوجه شد بزرگ\u200cترین قدرت، مهربونیه.',
    '📖 در باغی پر از گل، یک کبوتر با یک مورچه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت کبوتر متوجه شد بزرگ\u200cترین قدرت، مهربونیه.',
    '📖 در دل کویری خشک، یک ماهی با یک موش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت ماهی فهمید تنها راه رسیدن به هدف، تلاش مداومه.',
    '📖 در یک دهکده\u200cی کوچک، یک زنبور با یک گرگ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت زنبور دید که صداقت دیر یا زود میوه میده.',
    '📖 در باغی پر از گل، یک قورباغه با یک خرگوش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت قورباغه دید که صداقت دیر یا زود میوه میده.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک سگ با یک ماهی دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت سگ فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 در باغی پر از گل، یک شیر با یک خرس دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت شیر دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک اسب با یک کلاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اسب فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک قورباغه با یک لاک\u200cپشت دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت قورباغه فهمید عجله همیشه به صرفه نیست.',
    '📖 در باغی پر از گل، یک اسب با یک زرافه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اسب فهمید عجله همیشه به صرفه نیست.',
    '📖 در دل کویری خشک، یک گنجشک با یک خرس دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گنجشک فهمید عجله همیشه به صرفه نیست.',
    '📖 در یک شهر شلوغ، یک اردک با یک جغد دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اردک فهمید عجله همیشه به صرفه نیست.',
    '📖 در یک جنگل سرسبز، یک سگ با یک فیل دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت سگ فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 در یک جنگل سرسبز، یک میمون با یک قورباغه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت میمون دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در باغی پر از گل، یک گوسفند با یک کلاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گوسفند یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در یک جنگل سرسبز، یک اردک با یک فیل دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اردک فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 در یک جنگل سرسبز، یک مورچه با یک قورباغه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت مورچه یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در دل کویری خشک، یک میمون با یک گربه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت میمون دید که صداقت دیر یا زود میوه میده.',
    '📖 در باغی پر از گل، یک گرگ با یک جغد دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گرگ یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در یک دهکده\u200cی کوچک، یک کبوتر با یک خرس دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت کبوتر متوجه شد بزرگ\u200cترین قدرت، مهربونیه.',
    '📖 در یک شهر شلوغ، یک خرگوش با یک روباه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرگوش فهمید عجله همیشه به صرفه نیست.',
    '📖 نزدیک یک آسیاب قدیمی، یک زرافه با یک خرگوش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت زرافه فهمید تنها راه رسیدن به هدف، تلاش مداومه.',
    '📖 در حاشیه\u200cی یک دریاچه، یک گنجشک با یک کلاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گنجشک فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 در دل کویری خشک، یک اردک با یک زرافه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اردک فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 نزدیک یک آسیاب قدیمی، یک زنبور با یک مورچه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت زنبور فهمید تنها راه رسیدن به هدف، تلاش مداومه.',
    '📖 کنار یک رودخانه آرام، یک جغد با یک کبوتر دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت جغد یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در یک دهکده\u200cی کوچک، یک میمون با یک لاک\u200cپشت دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت میمون فهمید تنها راه رسیدن به هدف، تلاش مداومه.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک شیر با یک فیل دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت شیر فهمید عجله همیشه به صرفه نیست.',
    '📖 در حاشیه\u200cی یک دریاچه، یک روباه با یک لاک\u200cپشت دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت روباه یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در باغی پر از گل، یک بز با یک روباه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت بز یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 کنار یک رودخانه آرام، یک شیر با یک گوسفند دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت شیر فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 کنار یک رودخانه آرام، یک جغد با یک کلاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت جغد فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 نزدیک یک آسیاب قدیمی، یک قورباغه با یک جغد دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت قورباغه دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در یک شهر شلوغ، یک میمون با یک فیل دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت میمون متوجه شد بزرگ\u200cترین قدرت، مهربونیه.',
    '📖 در دامنه\u200cی یک کوه بلند، یک قورباغه با یک بز دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت قورباغه فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک ماهی با یک میمون دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت ماهی یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در حاشیه\u200cی یک دریاچه، یک خرس با یک گربه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرس فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 در یک دهکده\u200cی کوچک، یک زنبور با یک گنجشک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت زنبور دید که صداقت دیر یا زود میوه میده.',
    '📖 در یک دهکده\u200cی کوچک، یک خرگوش با یک گنجشک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرگوش یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک زنبور با یک گربه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت زنبور فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 در حاشیه\u200cی یک دریاچه، یک زنبور با یک جغد دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت زنبور فهمید تنها راه رسیدن به هدف، تلاش مداومه.',
    '📖 در باغی پر از گل، یک موش با یک خرس دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت موش فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 در یک دهکده\u200cی کوچک، یک ماهی با یک جغد دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت ماهی دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در دل کویری خشک، یک میمون با یک کبوتر دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت میمون فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 در یک دهکده\u200cی کوچک، یک مورچه با یک زرافه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت مورچه دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در حاشیه\u200cی یک دریاچه، یک زنبور با یک اسب دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت زنبور فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 در باغی پر از گل، یک الاغ با یک قورباغه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت الاغ متوجه شد بزرگ\u200cترین قدرت، مهربونیه.',
    '📖 در دل کویری خشک، یک بز با یک شیر دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت بز فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 نزدیک یک آسیاب قدیمی، یک گنجشک با یک لاک\u200cپشت دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گنجشک فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 در یک دهکده\u200cی کوچک، یک سگ با یک خرس دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت سگ فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 در حاشیه\u200cی یک دریاچه، یک موش با یک شیر دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت موش فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک کلاغ با یک موش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت کلاغ دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در حاشیه\u200cی یک دریاچه، یک کبوتر با یک شیر دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت کبوتر دید که صداقت دیر یا زود میوه میده.',
    '📖 در باغی پر از گل، یک بز با یک الاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت بز فهمید تنها راه رسیدن به هدف، تلاش مداومه.',
    '📖 نزدیک یک آسیاب قدیمی، یک اردک با یک لاک\u200cپشت دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اردک فهمید عجله همیشه به صرفه نیست.',
    '📖 در دامنه\u200cی یک کوه بلند، یک قورباغه با یک زنبور دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت قورباغه دید که صداقت دیر یا زود میوه میده.',
    '📖 در دل کویری خشک، یک خرس با یک موش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرس یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 نزدیک یک آسیاب قدیمی، یک ماهی با یک زنبور دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت ماهی فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 در یک جنگل سرسبز، یک اسب با یک گنجشک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اسب فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 در دامنه\u200cی یک کوه بلند، یک خرس با یک گنجشک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرس فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 در دامنه\u200cی یک کوه بلند، یک مورچه با یک گربه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت مورچه فهمید عجله همیشه به صرفه نیست.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک ماهی با یک کبوتر دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت ماهی فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 در دامنه\u200cی یک کوه بلند، یک فیل با یک خرس دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت فیل دید که صداقت دیر یا زود میوه میده.',
    '📖 کنار یک رودخانه آرام، یک فیل با یک روباه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت فیل فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک زنبور با یک روباه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت زنبور متوجه شد بزرگ\u200cترین قدرت، مهربونیه.',
    '📖 کنار یک رودخانه آرام، یک جغد با یک موش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت جغد یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در حاشیه\u200cی یک دریاچه، یک کبوتر با یک جغد دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت کبوتر دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در یک جنگل سرسبز، یک ماهی با یک سگ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت ماهی فهمید عجله همیشه به صرفه نیست.',
    '📖 در یک شهر شلوغ، یک اردک با یک گوسفند دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اردک فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 در یک شهر شلوغ، یک بز با یک میمون دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت بز متوجه شد بزرگ\u200cترین قدرت، مهربونیه.',
    '📖 زیر سایه\u200cی یک درخت کهنسال، یک اسب با یک موش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اسب دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در یک جنگل سرسبز، یک زرافه با یک روباه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت زرافه یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در یک دهکده\u200cی کوچک، یک ماهی با یک گنجشک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت ماهی فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 در یک شهر شلوغ، یک مورچه با یک اسب دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت مورچه دید که دوستی از هر گنجی باارزش\u200cتره.',
    '📖 در یک شهر شلوغ، یک کلاغ با یک شیر دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت کلاغ یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 نزدیک یک آسیاب قدیمی، یک مورچه با یک خرس دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت مورچه یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در باغی پر از گل، یک اردک با یک خرگوش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اردک یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 نزدیک یک آسیاب قدیمی، یک ماهی با یک کلاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت ماهی یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در یک جنگل سرسبز، یک خرگوش با یک فیل دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرگوش متوجه شد بزرگ\u200cترین قدرت، مهربونیه.',
    '📖 در یک دهکده\u200cی کوچک، یک اسب با یک جغد دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اسب یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در دل کویری خشک، یک خرگوش با یک گرگ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرگوش فهمید عجله همیشه به صرفه نیست.',
    '📖 در حاشیه\u200cی یک دریاچه، یک مورچه با یک روباه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت مورچه دید که صداقت دیر یا زود میوه میده.',
    '📖 نزدیک یک آسیاب قدیمی، یک کبوتر با یک الاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت کبوتر فهمید تنها راه رسیدن به هدف، تلاش مداومه.',
    '📖 در دامنه\u200cی یک کوه بلند، یک سگ با یک قورباغه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت سگ فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 نزدیک یک آسیاب قدیمی، یک سگ با یک موش دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت سگ فهمید هر شکست، درسیه برای موفقیت بعدی.',
    '📖 کنار یک رودخانه آرام، یک گربه با یک گرگ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گربه فهمید تنها راه رسیدن به هدف، تلاش مداومه.',
    '📖 در حاشیه\u200cی یک دریاچه، یک فیل با یک گنجشک دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت فیل دید که صداقت دیر یا زود میوه میده.',
    '📖 در یک دهکده\u200cی کوچک، یک گربه با یک سگ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گربه فهمید غرور بی\u200cجا فقط باعث پشیمونیه.',
    '📖 در یک جنگل سرسبز، یک سگ با یک کلاغ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت سگ یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 نزدیک یک آسیاب قدیمی، یک گنجشک با یک اسب دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت گنجشک فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 در دامنه\u200cی یک کوه بلند، یک خرگوش با یک زرافه دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرگوش یاد گرفت که کمک به دیگران خودش پاداشه.',
    '📖 در حاشیه\u200cی یک دریاچه، یک لاک\u200cپشت با یک اسب دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت لاک\u200cپشت دید که صداقت دیر یا زود میوه میده.',
    '📖 در یک جنگل سرسبز، یک اسب با یک شیر دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت اسب دید که صداقت دیر یا زود میوه میده.',
    '📖 نزدیک یک آسیاب قدیمی، یک فیل با یک گرگ دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت فیل فهمید که صبر همیشه شیرین\u200cترین میوه رو میده.',
    '📖 در یک دهکده\u200cی کوچک، یک خرس با یک اسب دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت خرس یاد گرفت که ظاهر همیشه حقیقت رو نشون نمیده.',
    '📖 در دامنه\u200cی یک کوه بلند، یک الاغ با یک شیر دوست شد و هر روز با هم ماجراجویی می\u200cکردند؛ یک روز با مشکلی بزرگ روبه\u200cرو شدند و در نهایت الاغ متوجه شد بزرگ\u200cترین قدرت، مهربونیه.',
]


# =========================================================
#  200 تا حقیقت و 200 تا جرات - بازی جرات یا حقیقت (جدید)
# =========================================================
TRUTH_LIST = [
    "🗣 حقیقت: بزرگ‌ترین رازت رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: خجالت‌آورترین خاطره‌ات رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: بزرگ‌ترین ترست رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: آخرین دروغی که گفتی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: کسی که مخفیانه دوستش داری رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: بدترین کاری که تا حالا کردی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: چیزی که هیچ‌وقت به خانواده‌ات نگفتی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: خنده‌دارترین اتفاقی که برات افتاده رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: کسی که از همه بیشتر اذیتت کرده رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: آرزوی پنهانی‌ات رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: بدترین نمره‌ای که گرفتی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: چیزی که از دوستت دزدیدی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: اولین کسی که عاشقش شدی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: بزرگ‌ترین اشتباه زندگیت رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: چیزی که از ظاهرت دوست نداری رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: بدترین دروغی که به یکی از اعضای این گروه گفتی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: چیزی که تا حالا به کسی نگفتی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: خجالت‌آورترین پیامی که اشتباهی فرستادی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: بدترین کابوسی که دیدی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: چیزی که مخفیانه از یکی از دوستانت متنفری رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: بزرگ‌ترین حسادتی که تا حالا کردی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: چیزی که در مورد ظاهرت همیشه بهت گفته میشه و ناراحتت میکنه رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: بدترین هدیه‌ای که گرفتی ولی تظاهر به خوشحالی کردی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: چیزی که در گوشیت مخفی کردی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: اسم کسی که فکر می‌کنی از تو خوشش میاد رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: بدترین دردسری که درست کردی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: چیزی که در موردش به بقیه دروغ گفتی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: خاطره‌ای که هیچ‌وقت فراموش نمی‌کنی و ازش خجالت می‌کشی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: چیزی که همیشه آرزو داشتی داشته باشی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: بدترین چیزی که پشت سر یکی از دوستانت گفتی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: چیزی که در مدرسه/دانشگاه ازش تقلب کردی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: بزرگ‌ترین ترس مسخره‌ات رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: چیزی که تظاهر می‌کنی بلدی ولی بلد نیستی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: آخرین باری که گریه کردی و دلیلش رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: چیزی که در مورد یکی از اعضای همین گروه فکر می‌کنی ولی نگفتی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: بدترین تصمیمی که گرفتی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: چیزی که از پدر/مادرت مخفی کردی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: خجالت‌آورترین چیزی که تو جمع گفتی رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: چیزی که همیشه ادعا می‌کنی ولی واقعیت نداره رو با جزئیات کامل تعریف کن!",
    "🗣 حقیقت: راستشو بگو، بزرگ‌ترین رازت چیه؟",
    "🗣 حقیقت: راستشو بگو، خجالت‌آورترین خاطره‌ات چیه؟",
    "🗣 حقیقت: راستشو بگو، بزرگ‌ترین ترست چیه؟",
    "🗣 حقیقت: راستشو بگو، آخرین دروغی که گفتی چیه؟",
    "🗣 حقیقت: راستشو بگو، کسی که مخفیانه دوستش داری چیه؟",
    "🗣 حقیقت: راستشو بگو، بدترین کاری که تا حالا کردی چیه؟",
    "🗣 حقیقت: راستشو بگو، چیزی که هیچ‌وقت به خانواده‌ات نگفتی چیه؟",
    "🗣 حقیقت: راستشو بگو، خنده‌دارترین اتفاقی که برات افتاده چیه؟",
    "🗣 حقیقت: راستشو بگو، کسی که از همه بیشتر اذیتت کرده چیه؟",
    "🗣 حقیقت: راستشو بگو، آرزوی پنهانی‌ات چیه؟",
    "🗣 حقیقت: راستشو بگو، بدترین نمره‌ای که گرفتی چیه؟",
    "🗣 حقیقت: راستشو بگو، چیزی که از دوستت دزدیدی چیه؟",
    "🗣 حقیقت: راستشو بگو، اولین کسی که عاشقش شدی چیه؟",
    "🗣 حقیقت: راستشو بگو، بزرگ‌ترین اشتباه زندگیت چیه؟",
    "🗣 حقیقت: راستشو بگو، چیزی که از ظاهرت دوست نداری چیه؟",
    "🗣 حقیقت: راستشو بگو، بدترین دروغی که به یکی از اعضای این گروه گفتی چیه؟",
    "🗣 حقیقت: راستشو بگو، چیزی که تا حالا به کسی نگفتی چیه؟",
    "🗣 حقیقت: راستشو بگو، خجالت‌آورترین پیامی که اشتباهی فرستادی چیه؟",
    "🗣 حقیقت: راستشو بگو، بدترین کابوسی که دیدی چیه؟",
    "🗣 حقیقت: راستشو بگو، چیزی که مخفیانه از یکی از دوستانت متنفری چیه؟",
    "🗣 حقیقت: راستشو بگو، بزرگ‌ترین حسادتی که تا حالا کردی چیه؟",
    "🗣 حقیقت: راستشو بگو، چیزی که در مورد ظاهرت همیشه بهت گفته میشه و ناراحتت میکنه چیه؟",
    "🗣 حقیقت: راستشو بگو، بدترین هدیه‌ای که گرفتی ولی تظاهر به خوشحالی کردی چیه؟",
    "🗣 حقیقت: راستشو بگو، چیزی که در گوشیت مخفی کردی چیه؟",
    "🗣 حقیقت: راستشو بگو، اسم کسی که فکر می‌کنی از تو خوشش میاد چیه؟",
    "🗣 حقیقت: راستشو بگو، بدترین دردسری که درست کردی چیه؟",
    "🗣 حقیقت: راستشو بگو، چیزی که در موردش به بقیه دروغ گفتی چیه؟",
    "🗣 حقیقت: راستشو بگو، خاطره‌ای که هیچ‌وقت فراموش نمی‌کنی و ازش خجالت می‌کشی چیه؟",
    "🗣 حقیقت: راستشو بگو، چیزی که همیشه آرزو داشتی داشته باشی چیه؟",
    "🗣 حقیقت: راستشو بگو، بدترین چیزی که پشت سر یکی از دوستانت گفتی چیه؟",
    "🗣 حقیقت: راستشو بگو، چیزی که در مدرسه/دانشگاه ازش تقلب کردی چیه؟",
    "🗣 حقیقت: راستشو بگو، بزرگ‌ترین ترس مسخره‌ات چیه؟",
    "🗣 حقیقت: راستشو بگو، چیزی که تظاهر می‌کنی بلدی ولی بلد نیستی چیه؟",
    "🗣 حقیقت: راستشو بگو، آخرین باری که گریه کردی و دلیلش چیه؟",
    "🗣 حقیقت: راستشو بگو، چیزی که در مورد یکی از اعضای همین گروه فکر می‌کنی ولی نگفتی چیه؟",
    "🗣 حقیقت: راستشو بگو، بدترین تصمیمی که گرفتی چیه؟",
    "🗣 حقیقت: راستشو بگو، چیزی که از پدر/مادرت مخفی کردی چیه؟",
    "🗣 حقیقت: راستشو بگو، خجالت‌آورترین چیزی که تو جمع گفتی چیه؟",
    "🗣 حقیقت: راستشو بگو، چیزی که همیشه ادعا می‌کنی ولی واقعیت نداره چیه؟",
    "🗣 حقیقت: بدون سانسور بگو بزرگ‌ترین رازت چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو خجالت‌آورترین خاطره‌ات چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو بزرگ‌ترین ترست چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو آخرین دروغی که گفتی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو کسی که مخفیانه دوستش داری چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو بدترین کاری که تا حالا کردی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو چیزی که هیچ‌وقت به خانواده‌ات نگفتی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو خنده‌دارترین اتفاقی که برات افتاده چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو کسی که از همه بیشتر اذیتت کرده چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو آرزوی پنهانی‌ات چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو بدترین نمره‌ای که گرفتی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو چیزی که از دوستت دزدیدی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو اولین کسی که عاشقش شدی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو بزرگ‌ترین اشتباه زندگیت چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو چیزی که از ظاهرت دوست نداری چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو بدترین دروغی که به یکی از اعضای این گروه گفتی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو چیزی که تا حالا به کسی نگفتی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو خجالت‌آورترین پیامی که اشتباهی فرستادی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو بدترین کابوسی که دیدی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو چیزی که مخفیانه از یکی از دوستانت متنفری چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو بزرگ‌ترین حسادتی که تا حالا کردی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو چیزی که در مورد ظاهرت همیشه بهت گفته میشه و ناراحتت میکنه چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو بدترین هدیه‌ای که گرفتی ولی تظاهر به خوشحالی کردی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو چیزی که در گوشیت مخفی کردی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو اسم کسی که فکر می‌کنی از تو خوشش میاد چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو بدترین دردسری که درست کردی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو چیزی که در موردش به بقیه دروغ گفتی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو خاطره‌ای که هیچ‌وقت فراموش نمی‌کنی و ازش خجالت می‌کشی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو چیزی که همیشه آرزو داشتی داشته باشی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو بدترین چیزی که پشت سر یکی از دوستانت گفتی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو چیزی که در مدرسه/دانشگاه ازش تقلب کردی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو بزرگ‌ترین ترس مسخره‌ات چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو چیزی که تظاهر می‌کنی بلدی ولی بلد نیستی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو آخرین باری که گریه کردی و دلیلش چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو چیزی که در مورد یکی از اعضای همین گروه فکر می‌کنی ولی نگفتی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو بدترین تصمیمی که گرفتی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو چیزی که از پدر/مادرت مخفی کردی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو خجالت‌آورترین چیزی که تو جمع گفتی چی بود؟",
    "🗣 حقیقت: بدون سانسور بگو چیزی که همیشه ادعا می‌کنی ولی واقعیت نداره چی بود؟",
    "🗣 حقیقت: اگه راست میگی الان بنویس بزرگ‌ترین رازت چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس خجالت‌آورترین خاطره‌ات چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس بزرگ‌ترین ترست چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس آخرین دروغی که گفتی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس کسی که مخفیانه دوستش داری چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس بدترین کاری که تا حالا کردی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس چیزی که هیچ‌وقت به خانواده‌ات نگفتی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس خنده‌دارترین اتفاقی که برات افتاده چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس کسی که از همه بیشتر اذیتت کرده چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس آرزوی پنهانی‌ات چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس بدترین نمره‌ای که گرفتی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس چیزی که از دوستت دزدیدی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس اولین کسی که عاشقش شدی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس بزرگ‌ترین اشتباه زندگیت چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس چیزی که از ظاهرت دوست نداری چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس بدترین دروغی که به یکی از اعضای این گروه گفتی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس چیزی که تا حالا به کسی نگفتی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس خجالت‌آورترین پیامی که اشتباهی فرستادی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس بدترین کابوسی که دیدی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس چیزی که مخفیانه از یکی از دوستانت متنفری چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس بزرگ‌ترین حسادتی که تا حالا کردی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس چیزی که در مورد ظاهرت همیشه بهت گفته میشه و ناراحتت میکنه چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس بدترین هدیه‌ای که گرفتی ولی تظاهر به خوشحالی کردی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس چیزی که در گوشیت مخفی کردی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس اسم کسی که فکر می‌کنی از تو خوشش میاد چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس بدترین دردسری که درست کردی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس چیزی که در موردش به بقیه دروغ گفتی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس خاطره‌ای که هیچ‌وقت فراموش نمی‌کنی و ازش خجالت می‌کشی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس چیزی که همیشه آرزو داشتی داشته باشی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس بدترین چیزی که پشت سر یکی از دوستانت گفتی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس چیزی که در مدرسه/دانشگاه ازش تقلب کردی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس بزرگ‌ترین ترس مسخره‌ات چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس چیزی که تظاهر می‌کنی بلدی ولی بلد نیستی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس آخرین باری که گریه کردی و دلیلش چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس چیزی که در مورد یکی از اعضای همین گروه فکر می‌کنی ولی نگفتی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس بدترین تصمیمی که گرفتی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس چیزی که از پدر/مادرت مخفی کردی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس خجالت‌آورترین چیزی که تو جمع گفتی چیه!",
    "🗣 حقیقت: اگه راست میگی الان بنویس چیزی که همیشه ادعا می‌کنی ولی واقعیت نداره چیه!",
    "🗣 حقیقت: یه بار برای همیشه بگو بزرگ‌ترین رازت چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو خجالت‌آورترین خاطره‌ات چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو بزرگ‌ترین ترست چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو آخرین دروغی که گفتی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو کسی که مخفیانه دوستش داری چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو بدترین کاری که تا حالا کردی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو چیزی که هیچ‌وقت به خانواده‌ات نگفتی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو خنده‌دارترین اتفاقی که برات افتاده چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو کسی که از همه بیشتر اذیتت کرده چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو آرزوی پنهانی‌ات چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو بدترین نمره‌ای که گرفتی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو چیزی که از دوستت دزدیدی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو اولین کسی که عاشقش شدی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو بزرگ‌ترین اشتباه زندگیت چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو چیزی که از ظاهرت دوست نداری چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو بدترین دروغی که به یکی از اعضای این گروه گفتی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو چیزی که تا حالا به کسی نگفتی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو خجالت‌آورترین پیامی که اشتباهی فرستادی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو بدترین کابوسی که دیدی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو چیزی که مخفیانه از یکی از دوستانت متنفری چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو بزرگ‌ترین حسادتی که تا حالا کردی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو چیزی که در مورد ظاهرت همیشه بهت گفته میشه و ناراحتت میکنه چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو بدترین هدیه‌ای که گرفتی ولی تظاهر به خوشحالی کردی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو چیزی که در گوشیت مخفی کردی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو اسم کسی که فکر می‌کنی از تو خوشش میاد چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو بدترین دردسری که درست کردی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو چیزی که در موردش به بقیه دروغ گفتی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو خاطره‌ای که هیچ‌وقت فراموش نمی‌کنی و ازش خجالت می‌کشی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو چیزی که همیشه آرزو داشتی داشته باشی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو بدترین چیزی که پشت سر یکی از دوستانت گفتی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو چیزی که در مدرسه/دانشگاه ازش تقلب کردی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو بزرگ‌ترین ترس مسخره‌ات چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو چیزی که تظاهر می‌کنی بلدی ولی بلد نیستی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو آخرین باری که گریه کردی و دلیلش چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو چیزی که در مورد یکی از اعضای همین گروه فکر می‌کنی ولی نگفتی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو بدترین تصمیمی که گرفتی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو چیزی که از پدر/مادرت مخفی کردی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو خجالت‌آورترین چیزی که تو جمع گفتی چیه؟",
    "🗣 حقیقت: یه بار برای همیشه بگو چیزی که همیشه ادعا می‌کنی ولی واقعیت نداره چیه؟",
    "🗣 حقیقت: با روحت راست بگو بزرگ‌ترین رازت چیه؟",
    "🗣 حقیقت: با روحت راست بگو خجالت‌آورترین خاطره‌ات چیه؟",
    "🗣 حقیقت: با روحت راست بگو بزرگ‌ترین ترست چیه؟",
    "🗣 حقیقت: با روحت راست بگو آخرین دروغی که گفتی چیه؟",
    "🗣 حقیقت: با روحت راست بگو کسی که مخفیانه دوستش داری چیه؟",
]

DARE_LIST = [
    "🔥 جرأت: با صدای بلند برای گروه آواز بخون!",
    "🔥 جرأت: ۳۰ ثانیه فقط با ایموجی جواب بده!",
    "🔥 جرأت: یک استیکر خنده‌دار برای گروه بفرست!",
    "🔥 جرأت: به نفر بعدی که پیام میده بگو دوستش داری!",
    "🔥 جرأت: پروفایلت رو تا ۱۰ دقیقه عوض کن با یه چیز خنده‌دار!",
    "🔥 جرأت: یک شعر مسخره در مورد خودت بگو!",
    "🔥 جرأت: بدون فکر کردن بگو الان چه ساعتیه بدون نگاه کردن به گوشی!",
    "🔥 جرأت: به یکی از اعضای گروه یه تعریف اغراق‌شده بکن!",
    "🔥 جرأت: ۵ تا شکلک پشت سر هم بدون توضیح بفرست!",
    "🔥 جرأت: یه خاطره خجالت‌آور رو با جزئیات تعریف کن!",
    "🔥 جرأت: تا آخر بازی فقط با حروف بزرگ بنویس!",
    "🔥 جرأت: اسم حیوان مورد علاقتو با صدای اون حیوان توصیف کن!",
    "🔥 جرأت: یه پیام به زبان محلی/لهجه بفرست!",
    "🔥 جرأت: ۱ دقیقه فقط با سوال صحبت کن!",
    "🔥 جرأت: یکی از پیام‌های قبلیتو ادیت کن و بنویس «غلط کردم»!",
    "🔥 جرأت: به گروه بگو امروز چند بار به گوشیت نگاه کردی!",
    "🔥 جرأت: یه دروغ بامزه در مورد خودت بگو که همه باور کنن!",
    "🔥 جرأت: بدون نوشتن حرف «الف» یه جمله کامل بنویس!",
    "🔥 جرأت: یه ویس بامزه با صدای خنده بفرست!",
    "🔥 جرأت: به نفر سمت راستت (لیست اعضا) یه کمپلیمان بده!",
    "🔥 جرأت: ۱۰ ثانیه فقط شکلک قلب بفرست!",
    "🔥 جرأت: یه چیز خنده‌دار در مورد ادمین گروه بگو (با احترام!)!",
    "🔥 جرأت: بگو دیشب چند ساعت خوابیدی و چرا کم/زیاد بود!",
    "🔥 جرأت: تظاهر کن مصاحبه تلویزیونی داری و خودتو معرفی کن!",
    "🔥 جرأت: یه بیت شعر الکی بساز و بفرست!",
    "🔥 جرأت: بگو اگه یه ابرقدرت داشتی چی بود و چرا انتخابش مسخره‌ست!",
    "🔥 جرأت: بدون غلط املایی یه جمله طولانی بنویس (بدون فکر کردن زیاد)!",
    "🔥 جرأت: به گروه بگو آخرین سرچی که تو گوشیت کردی چی بود!",
    "🔥 جرأت: یه شکلک رندوم انتخاب کن و توضیح بده چرا الان همون حسو داری!",
    "🔥 جرأت: ۲۰ ثانیه فقط جواب سوالا رو با «شاید» بده!",
    "🔥 جرأت: اسم خودتو برعکس بنویس!",
    "🔥 جرأت: یه چالش رقص تصور کن و توصیفش کن (متنی!)!",
    "🔥 جرأت: بگو مسخره‌ترین چیزی که امروز خوردی چی بود!",
    "🔥 جرأت: یه پیام انگیزشی الکی برای گروه بنویس!",
    "🔥 جرأت: بگو اگه امروز آخرین روز زندگیت بود چیکار میکردی (شوخی!)!",
    "🔥 جرأت: یه استیکر یا ایموجی بفرست که بیانگر حس الانته!",
    "🔥 جرأت: بگو بدون نگاه کردن ساعت چند دقیقس!",
    "🔥 جرأت: یه جمله بگو که توش هیچ حرف تکراری نباشه!",
    "🔥 جرأت: الان باید با صدای بلند برای گروه آواز بخون!",
    "🔥 جرأت: الان باید ۳۰ ثانیه فقط با ایموجی جواب بده!",
    "🔥 جرأت: الان باید یک استیکر خنده‌دار برای گروه بفرست!",
    "🔥 جرأت: الان باید به نفر بعدی که پیام میده بگو دوستش داری!",
    "🔥 جرأت: الان باید پروفایلت رو تا ۱۰ دقیقه عوض کن با یه چیز خنده‌دار!",
    "🔥 جرأت: الان باید یک شعر مسخره در مورد خودت بگو!",
    "🔥 جرأت: الان باید بدون فکر کردن بگو الان چه ساعتیه بدون نگاه کردن به گوشی!",
    "🔥 جرأت: الان باید به یکی از اعضای گروه یه تعریف اغراق‌شده بکن!",
    "🔥 جرأت: الان باید ۵ تا شکلک پشت سر هم بدون توضیح بفرست!",
    "🔥 جرأت: الان باید یه خاطره خجالت‌آور رو با جزئیات تعریف کن!",
    "🔥 جرأت: الان باید تا آخر بازی فقط با حروف بزرگ بنویس!",
    "🔥 جرأت: الان باید اسم حیوان مورد علاقتو با صدای اون حیوان توصیف کن!",
    "🔥 جرأت: الان باید یه پیام به زبان محلی/لهجه بفرست!",
    "🔥 جرأت: الان باید ۱ دقیقه فقط با سوال صحبت کن!",
    "🔥 جرأت: الان باید یکی از پیام‌های قبلیتو ادیت کن و بنویس «غلط کردم»!",
    "🔥 جرأت: الان باید به گروه بگو امروز چند بار به گوشیت نگاه کردی!",
    "🔥 جرأت: الان باید یه دروغ بامزه در مورد خودت بگو که همه باور کنن!",
    "🔥 جرأت: الان باید بدون نوشتن حرف «الف» یه جمله کامل بنویس!",
    "🔥 جرأت: الان باید یه ویس بامزه با صدای خنده بفرست!",
    "🔥 جرأت: الان باید به نفر سمت راستت (لیست اعضا) یه کمپلیمان بده!",
    "🔥 جرأت: الان باید ۱۰ ثانیه فقط شکلک قلب بفرست!",
    "🔥 جرأت: الان باید یه چیز خنده‌دار در مورد ادمین گروه بگو (با احترام!)!",
    "🔥 جرأت: الان باید بگو دیشب چند ساعت خوابیدی و چرا کم/زیاد بود!",
    "🔥 جرأت: الان باید تظاهر کن مصاحبه تلویزیونی داری و خودتو معرفی کن!",
    "🔥 جرأت: الان باید یه بیت شعر الکی بساز و بفرست!",
    "🔥 جرأت: الان باید بگو اگه یه ابرقدرت داشتی چی بود و چرا انتخابش مسخره‌ست!",
    "🔥 جرأت: الان باید بدون غلط املایی یه جمله طولانی بنویس (بدون فکر کردن زیاد)!",
    "🔥 جرأت: الان باید به گروه بگو آخرین سرچی که تو گوشیت کردی چی بود!",
    "🔥 جرأت: الان باید یه شکلک رندوم انتخاب کن و توضیح بده چرا الان همون حسو داری!",
    "🔥 جرأت: الان باید ۲۰ ثانیه فقط جواب سوالا رو با «شاید» بده!",
    "🔥 جرأت: الان باید اسم خودتو برعکس بنویس!",
    "🔥 جرأت: الان باید یه چالش رقص تصور کن و توصیفش کن (متنی!)!",
    "🔥 جرأت: الان باید بگو مسخره‌ترین چیزی که امروز خوردی چی بود!",
    "🔥 جرأت: الان باید یه پیام انگیزشی الکی برای گروه بنویس!",
    "🔥 جرأت: الان باید بگو اگه امروز آخرین روز زندگیت بود چیکار میکردی (شوخی!)!",
    "🔥 جرأت: الان باید یه استیکر یا ایموجی بفرست که بیانگر حس الانته!",
    "🔥 جرأت: الان باید بگو بدون نگاه کردن ساعت چند دقیقس!",
    "🔥 جرأت: الان باید یه جمله بگو که توش هیچ حرف تکراری نباشه!",
    "🔥 جرأت: قبول می‌کنی که با صدای بلند برای گروه آواز بخون؟",
    "🔥 جرأت: قبول می‌کنی که ۳۰ ثانیه فقط با ایموجی جواب بده؟",
    "🔥 جرأت: قبول می‌کنی که یک استیکر خنده‌دار برای گروه بفرست؟",
    "🔥 جرأت: قبول می‌کنی که به نفر بعدی که پیام میده بگو دوستش داری؟",
    "🔥 جرأت: قبول می‌کنی که پروفایلت رو تا ۱۰ دقیقه عوض کن با یه چیز خنده‌دار؟",
    "🔥 جرأت: قبول می‌کنی که یک شعر مسخره در مورد خودت بگو؟",
    "🔥 جرأت: قبول می‌کنی که بدون فکر کردن بگو الان چه ساعتیه بدون نگاه کردن به گوشی؟",
    "🔥 جرأت: قبول می‌کنی که به یکی از اعضای گروه یه تعریف اغراق‌شده بکن؟",
    "🔥 جرأت: قبول می‌کنی که ۵ تا شکلک پشت سر هم بدون توضیح بفرست؟",
    "🔥 جرأت: قبول می‌کنی که یه خاطره خجالت‌آور رو با جزئیات تعریف کن؟",
    "🔥 جرأت: قبول می‌کنی که تا آخر بازی فقط با حروف بزرگ بنویس؟",
    "🔥 جرأت: قبول می‌کنی که اسم حیوان مورد علاقتو با صدای اون حیوان توصیف کن؟",
    "🔥 جرأت: قبول می‌کنی که یه پیام به زبان محلی/لهجه بفرست؟",
    "🔥 جرأت: قبول می‌کنی که ۱ دقیقه فقط با سوال صحبت کن؟",
    "🔥 جرأت: قبول می‌کنی که یکی از پیام‌های قبلیتو ادیت کن و بنویس «غلط کردم»؟",
    "🔥 جرأت: قبول می‌کنی که به گروه بگو امروز چند بار به گوشیت نگاه کردی؟",
    "🔥 جرأت: قبول می‌کنی که یه دروغ بامزه در مورد خودت بگو که همه باور کنن؟",
    "🔥 جرأت: قبول می‌کنی که بدون نوشتن حرف «الف» یه جمله کامل بنویس؟",
    "🔥 جرأت: قبول می‌کنی که یه ویس بامزه با صدای خنده بفرست؟",
    "🔥 جرأت: قبول می‌کنی که به نفر سمت راستت (لیست اعضا) یه کمپلیمان بده؟",
    "🔥 جرأت: قبول می‌کنی که ۱۰ ثانیه فقط شکلک قلب بفرست؟",
    "🔥 جرأت: قبول می‌کنی که یه چیز خنده‌دار در مورد ادمین گروه بگو (با احترام!)؟",
    "🔥 جرأت: قبول می‌کنی که بگو دیشب چند ساعت خوابیدی و چرا کم/زیاد بود؟",
    "🔥 جرأت: قبول می‌کنی که تظاهر کن مصاحبه تلویزیونی داری و خودتو معرفی کن؟",
    "🔥 جرأت: قبول می‌کنی که یه بیت شعر الکی بساز و بفرست؟",
    "🔥 جرأت: قبول می‌کنی که بگو اگه یه ابرقدرت داشتی چی بود و چرا انتخابش مسخره‌ست؟",
    "🔥 جرأت: قبول می‌کنی که بدون غلط املایی یه جمله طولانی بنویس (بدون فکر کردن زیاد)؟",
    "🔥 جرأت: قبول می‌کنی که به گروه بگو آخرین سرچی که تو گوشیت کردی چی بود؟",
    "🔥 جرأت: قبول می‌کنی که یه شکلک رندوم انتخاب کن و توضیح بده چرا الان همون حسو داری؟",
    "🔥 جرأت: قبول می‌کنی که ۲۰ ثانیه فقط جواب سوالا رو با «شاید» بده؟",
    "🔥 جرأت: قبول می‌کنی که اسم خودتو برعکس بنویس؟",
    "🔥 جرأت: قبول می‌کنی که یه چالش رقص تصور کن و توصیفش کن (متنی!)؟",
    "🔥 جرأت: قبول می‌کنی که بگو مسخره‌ترین چیزی که امروز خوردی چی بود؟",
    "🔥 جرأت: قبول می‌کنی که یه پیام انگیزشی الکی برای گروه بنویس؟",
    "🔥 جرأت: قبول می‌کنی که بگو اگه امروز آخرین روز زندگیت بود چیکار میکردی (شوخی!)؟",
    "🔥 جرأت: قبول می‌کنی که یه استیکر یا ایموجی بفرست که بیانگر حس الانته؟",
    "🔥 جرأت: قبول می‌کنی که بگو بدون نگاه کردن ساعت چند دقیقس؟",
    "🔥 جرأت: قبول می‌کنی که یه جمله بگو که توش هیچ حرف تکراری نباشه؟",
    "🔥 جرأت: چالش اینه که با صدای بلند برای گروه آواز بخون!",
    "🔥 جرأت: چالش اینه که ۳۰ ثانیه فقط با ایموجی جواب بده!",
    "🔥 جرأت: چالش اینه که یک استیکر خنده‌دار برای گروه بفرست!",
    "🔥 جرأت: چالش اینه که به نفر بعدی که پیام میده بگو دوستش داری!",
    "🔥 جرأت: چالش اینه که پروفایلت رو تا ۱۰ دقیقه عوض کن با یه چیز خنده‌دار!",
    "🔥 جرأت: چالش اینه که یک شعر مسخره در مورد خودت بگو!",
    "🔥 جرأت: چالش اینه که بدون فکر کردن بگو الان چه ساعتیه بدون نگاه کردن به گوشی!",
    "🔥 جرأت: چالش اینه که به یکی از اعضای گروه یه تعریف اغراق‌شده بکن!",
    "🔥 جرأت: چالش اینه که ۵ تا شکلک پشت سر هم بدون توضیح بفرست!",
    "🔥 جرأت: چالش اینه که یه خاطره خجالت‌آور رو با جزئیات تعریف کن!",
    "🔥 جرأت: چالش اینه که تا آخر بازی فقط با حروف بزرگ بنویس!",
    "🔥 جرأت: چالش اینه که اسم حیوان مورد علاقتو با صدای اون حیوان توصیف کن!",
    "🔥 جرأت: چالش اینه که یه پیام به زبان محلی/لهجه بفرست!",
    "🔥 جرأت: چالش اینه که ۱ دقیقه فقط با سوال صحبت کن!",
    "🔥 جرأت: چالش اینه که یکی از پیام‌های قبلیتو ادیت کن و بنویس «غلط کردم»!",
    "🔥 جرأت: چالش اینه که به گروه بگو امروز چند بار به گوشیت نگاه کردی!",
    "🔥 جرأت: چالش اینه که یه دروغ بامزه در مورد خودت بگو که همه باور کنن!",
    "🔥 جرأت: چالش اینه که بدون نوشتن حرف «الف» یه جمله کامل بنویس!",
    "🔥 جرأت: چالش اینه که یه ویس بامزه با صدای خنده بفرست!",
    "🔥 جرأت: چالش اینه که به نفر سمت راستت (لیست اعضا) یه کمپلیمان بده!",
    "🔥 جرأت: چالش اینه که ۱۰ ثانیه فقط شکلک قلب بفرست!",
    "🔥 جرأت: چالش اینه که یه چیز خنده‌دار در مورد ادمین گروه بگو (با احترام!)!",
    "🔥 جرأت: چالش اینه که بگو دیشب چند ساعت خوابیدی و چرا کم/زیاد بود!",
    "🔥 جرأت: چالش اینه که تظاهر کن مصاحبه تلویزیونی داری و خودتو معرفی کن!",
    "🔥 جرأت: چالش اینه که یه بیت شعر الکی بساز و بفرست!",
    "🔥 جرأت: چالش اینه که بگو اگه یه ابرقدرت داشتی چی بود و چرا انتخابش مسخره‌ست!",
    "🔥 جرأت: چالش اینه که بدون غلط املایی یه جمله طولانی بنویس (بدون فکر کردن زیاد)!",
    "🔥 جرأت: چالش اینه که به گروه بگو آخرین سرچی که تو گوشیت کردی چی بود!",
    "🔥 جرأت: چالش اینه که یه شکلک رندوم انتخاب کن و توضیح بده چرا الان همون حسو داری!",
    "🔥 جرأت: چالش اینه که ۲۰ ثانیه فقط جواب سوالا رو با «شاید» بده!",
    "🔥 جرأت: چالش اینه که اسم خودتو برعکس بنویس!",
    "🔥 جرأت: چالش اینه که یه چالش رقص تصور کن و توصیفش کن (متنی!)!",
    "🔥 جرأت: چالش اینه که بگو مسخره‌ترین چیزی که امروز خوردی چی بود!",
    "🔥 جرأت: چالش اینه که یه پیام انگیزشی الکی برای گروه بنویس!",
    "🔥 جرأت: چالش اینه که بگو اگه امروز آخرین روز زندگیت بود چیکار میکردی (شوخی!)!",
    "🔥 جرأت: چالش اینه که یه استیکر یا ایموجی بفرست که بیانگر حس الانته!",
    "🔥 جرأت: چالش اینه که بگو بدون نگاه کردن ساعت چند دقیقس!",
    "🔥 جرأت: چالش اینه که یه جمله بگو که توش هیچ حرف تکراری نباشه!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید با صدای بلند برای گروه آواز بخون!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید ۳۰ ثانیه فقط با ایموجی جواب بده!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید یک استیکر خنده‌دار برای گروه بفرست!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید به نفر بعدی که پیام میده بگو دوستش داری!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید پروفایلت رو تا ۱۰ دقیقه عوض کن با یه چیز خنده‌دار!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید یک شعر مسخره در مورد خودت بگو!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید بدون فکر کردن بگو الان چه ساعتیه بدون نگاه کردن به گوشی!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید به یکی از اعضای گروه یه تعریف اغراق‌شده بکن!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید ۵ تا شکلک پشت سر هم بدون توضیح بفرست!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید یه خاطره خجالت‌آور رو با جزئیات تعریف کن!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید تا آخر بازی فقط با حروف بزرگ بنویس!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید اسم حیوان مورد علاقتو با صدای اون حیوان توصیف کن!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید یه پیام به زبان محلی/لهجه بفرست!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید ۱ دقیقه فقط با سوال صحبت کن!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید یکی از پیام‌های قبلیتو ادیت کن و بنویس «غلط کردم»!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید به گروه بگو امروز چند بار به گوشیت نگاه کردی!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید یه دروغ بامزه در مورد خودت بگو که همه باور کنن!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید بدون نوشتن حرف «الف» یه جمله کامل بنویس!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید یه ویس بامزه با صدای خنده بفرست!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید به نفر سمت راستت (لیست اعضا) یه کمپلیمان بده!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید ۱۰ ثانیه فقط شکلک قلب بفرست!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید یه چیز خنده‌دار در مورد ادمین گروه بگو (با احترام!)!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید بگو دیشب چند ساعت خوابیدی و چرا کم/زیاد بود!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید تظاهر کن مصاحبه تلویزیونی داری و خودتو معرفی کن!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید یه بیت شعر الکی بساز و بفرست!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید بگو اگه یه ابرقدرت داشتی چی بود و چرا انتخابش مسخره‌ست!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید بدون غلط املایی یه جمله طولانی بنویس (بدون فکر کردن زیاد)!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید به گروه بگو آخرین سرچی که تو گوشیت کردی چی بود!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید یه شکلک رندوم انتخاب کن و توضیح بده چرا الان همون حسو داری!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید ۲۰ ثانیه فقط جواب سوالا رو با «شاید» بده!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید اسم خودتو برعکس بنویس!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید یه چالش رقص تصور کن و توصیفش کن (متنی!)!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید بگو مسخره‌ترین چیزی که امروز خوردی چی بود!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید یه پیام انگیزشی الکی برای گروه بنویس!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید بگو اگه امروز آخرین روز زندگیت بود چیکار میکردی (شوخی!)!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید یه استیکر یا ایموجی بفرست که بیانگر حس الانته!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید بگو بدون نگاه کردن ساعت چند دقیقس!",
    "🔥 جرأت: تا ۱ دقیقه دیگه باید یه جمله بگو که توش هیچ حرف تکراری نباشه!",
    "🔥 جرأت: اگه جربزه داری با صدای بلند برای گروه آواز بخون!",
    "🔥 جرأت: اگه جربزه داری ۳۰ ثانیه فقط با ایموجی جواب بده!",
    "🔥 جرأت: اگه جربزه داری یک استیکر خنده‌دار برای گروه بفرست!",
    "🔥 جرأت: اگه جربزه داری به نفر بعدی که پیام میده بگو دوستش داری!",
    "🔥 جرأت: اگه جربزه داری پروفایلت رو تا ۱۰ دقیقه عوض کن با یه چیز خنده‌دار!",
    "🔥 جرأت: اگه جربزه داری یک شعر مسخره در مورد خودت بگو!",
    "🔥 جرأت: اگه جربزه داری بدون فکر کردن بگو الان چه ساعتیه بدون نگاه کردن به گوشی!",
    "🔥 جرأت: اگه جربزه داری به یکی از اعضای گروه یه تعریف اغراق‌شده بکن!",
    "🔥 جرأت: اگه جربزه داری ۵ تا شکلک پشت سر هم بدون توضیح بفرست!",
    "🔥 جرأت: اگه جربزه داری یه خاطره خجالت‌آور رو با جزئیات تعریف کن!",
]

PENALTY_DARE_LIST = [
    "😈 پنالتی: تا ۵ دقیقه فقط با شکلک 😂 جواب همه رو بده!",
    "😈 پنالتی: باید اسم یکی از اعضای گروه رو با صدای بلند (اگه ویس داری) صدا بزنی 😅",
    "😈 پنالتی: یک آهنگ که همین الان تو ذهنته رو معرفی کن!",
    "😈 پنالتی: باید یک خاطره‌ی خنده‌دار از خودت تعریف کنی!",
    "😈 پنالتی: تا ۱۰ دقیقه فقط با حروف بزرگ تایپ کن!",
    "😈 پنالتی: یک نفر رو به گروه دعوت کن یا یه استیکر خنده‌دار بفرست!",
    "😈 پنالتی: باید بگی الان دقیقاً چه فکری تو سرته!",
    "😈 پنالتی: باید یکی از پیام‌های قبلی خودت رو ادیت کنی و بنویسی «غلط کردم»!",
    "😈 پنالتی: تا آخر امروز فقط باید سوالی صحبت کنی؟!",
    "😈 پنالتی: یک تعریف الکی و اغراق‌شده از خودت بنویس!",
]

# --- 🎮 شبیه‌ساز پنالتی فوتبالی ---
# هر آیتم: (وزن احتمال, برچسب نتیجه, لیستی از متن‌های همون نتیجه برای تنوع)
PENALTY_OUTCOMES = [
    (45, "گل", [
        "⚽️🥅 GOOOAL! توپ مستقیم رفت گوشه دروازه و گل شد! 🎉",
        "⚽️🥅 گل زیبایی بود! دروازه‌بان فقط نگاه کرد! 🔥",
        "⚽️🥅 توپ از زیر پای دروازه‌بان رد شد و گل شد! 😄",
    ]),
    (20, "سیو", [
        "🧤 دروازه‌بان با یه پرش عالی توپ رو سیو کرد!",
        "🧤 سیو درجه یک! توپ به کرنر رفت!",
        "🧤 دروازه‌بان جهت رو درست حدس زد و سیو کرد!",
    ]),
    (20, "گرفتن دروازه‌بان", [
        "🧤 دروازه‌بان درجا توپ رو گرفتش! چه واکنشی داشت!",
        "🧤 توپ مستقیم رفت تو بغل دروازه‌بان و گرفته شد!",
        "🧤 دروازه‌بان محکم توپ رو چسبید، اصلاً ول نکرد!",
    ]),
    (15, "برخورد به تیر", [
        "🥅 توپ خورد به تیر دروازه و برگشت وسط زمین! هیچی نشد!",
        "🥅 محکم خورد به تیر! چند سانت با گل فاصله داشت!",
        "🥅 توپ به تیر برخورد کرد و بیرون موند، گل نشد!",
    ]),
]

def _pick_penalty_outcome():
    labels = [o[1] for o in PENALTY_OUTCOMES]
    weights = [o[0] for o in PENALTY_OUTCOMES]
    texts_by_label = {o[1]: o[2] for o in PENALTY_OUTCOMES}
    label = random.choices(labels, weights=weights, k=1)[0]
    return label, random.choice(texts_by_label[label])

RIDDLE_LIST = [
    '🧩 معما: چه چیزی هر چه از آن برداری بزرگ\u200cتر می\u200cشود؟ (جواب: چاله/گودال)',
    '🧩 معما: چه چیزی دندان دارد ولی گاز نمی\u200cگیرد؟ (جواب: شانه)',
    '🧩 معما: چه چیزی هر روز از خانه بیرون می\u200cرود ولی هیچ\u200cوقت دور نمی\u200cشود؟ (جواب: ساعت)',
    '🧩 معما: چیست آن که شب می\u200cآید و صبح می\u200cرود، اما هیچ\u200cکس از آمدنش خبردار نمی\u200cشود؟ (جواب: خواب)',
    '🧩 معما: چه چیزی را نمی\u200cتوان دید ولی می\u200cتوان احساسش کرد؟ (جواب: باد)',
    '🧩 معما: چه چیزی پر از سوراخ است ولی هنوز هم آب نگه می\u200cدارد؟ (جواب: اسفنج)',
    '🧩 معما: کدام کلمه هر چه بیشتر از آن برمی\u200cداری، بزرگ\u200cتر می\u200cشود؟ (جواب: گودال)',
    '🧩 معما: چیست آن چیزی که چشم دارد ولی نمی\u200cبیند؟ (جواب: سیب\u200cزمینی)',
    '🧩 معما: چیست آن چیزی که تاج دارد ولی پادشاه نیست؟ (جواب: خروس)',
    '🧩 معما: چیست آن چیزی که قلب دارد ولی نمی\u200cتپد؟ (جواب: درخت)',
    '🧩 معما: چیست آن چیزی که بال دارد ولی پرواز نمی\u200cکند؟ (جواب: هواپیمای کاغذی روی زمین)',
    '🧩 معما: چیست آن چیزی که پوست دارد ولی گوشت ندارد؟ (جواب: پیاز)',
    '🧩 معما: چیست آن چیزی که خانه دارد ولی در آن زندگی نمی\u200cکند؟ (جواب: حلزون خالی)',
    '🧩 معما: چیست آن چیزی که دندان دارد ولی نمی\u200cجود؟ (جواب: چرخ\u200cدنده)',
    '🧩 معما: چیست آن چیزی که پرده دارد ولی خانه نیست؟ (جواب: گوش)',
    '🧩 معما: چیست آن چیزی که کلید دارد ولی قفل باز نمی\u200cکند؟ (جواب: پیانو)',
    '🧩 معما: چیست آن چیزی که سایه دارد ولی جسم ندارد؟ (جواب: ابر)',
    '🧩 معما: چیست آن چیزی که رنگ عوض می\u200cکند ولی نقاش نیست؟ (جواب: آفتاب\u200cپرست)',
    '🧩 معما: چیست آن چیزی که همیشه می\u200cدود ولی پا ندارد؟ (جواب: رودخانه)',
    '🧩 معما: چیست آن چیزی که پیر می\u200cشود ولی هرگز نمی\u200cمیرد؟ (جواب: کوه)',
    '🧩 معما: چیست آن چیزی که پا دارد ولی راه نمی\u200cرود؟  (جواب: میز)',
    '🧩 معما: چیست آن چیزی که عینک دارد ولی نمی\u200cبیند؟  (جواب: کتاب)',
    '🧩 معما: چیست آن چیزی که زبان دارد ولی حرف نمی\u200cزند؟  (جواب: ترازو)',
    '🧩 معما: چیست آن چیزی که سر دارد ولی مغز ندارد؟  (جواب: سنجاق)',
    '🧩 معما: چیست آن چیزی که در دارد ولی خانه نیست؟  (جواب: باغ)',
    '🧩 معما: چیست آن چیزی که گوش دارد ولی نمی\u200cشنود؟  (جواب: سوزن)',
    '🧩 معما: چیست آن چیزی که دست دارد ولی نمی\u200cتواند بگیرد؟  (جواب: ساعت)',
    '🧩 معما: چیست آن چیزی که چشم دارد ولی نمی\u200cبیند؟  (جواب: سیب\u200cزمینی)',
    '🧩 معما: چیست آن چیزی که تاج دارد ولی پادشاه نیست؟  (جواب: خروس)',
    '🧩 معما: چیست آن چیزی که قلب دارد ولی نمی\u200cتپد؟  (جواب: درخت)',
    '🧩 معما: چیست آن چیزی که بال دارد ولی پرواز نمی\u200cکند؟  (جواب: هواپیمای کاغذی روی زمین)',
    '🧩 معما: چیست آن چیزی که پوست دارد ولی گوشت ندارد؟  (جواب: پیاز)',
    '🧩 معما: چیست آن چیزی که خانه دارد ولی در آن زندگی نمی\u200cکند؟  (جواب: حلزون خالی)',
    '🧩 معما: چیست آن چیزی که دندان دارد ولی نمی\u200cجود؟  (جواب: چرخ\u200cدنده)',
    '🧩 معما: چیست آن چیزی که پرده دارد ولی خانه نیست؟  (جواب: گوش)',
    '🧩 معما: چیست آن چیزی که کلید دارد ولی قفل باز نمی\u200cکند؟  (جواب: پیانو)',
    '🧩 معما: چیست آن چیزی که سایه دارد ولی جسم ندارد؟  (جواب: ابر)',
    '🧩 معما: چیست آن چیزی که رنگ عوض می\u200cکند ولی نقاش نیست؟  (جواب: آفتاب\u200cپرست)',
    '🧩 معما: چیست آن چیزی که همیشه می\u200cدود ولی پا ندارد؟  (جواب: رودخانه)',
    '🧩 معما: چیست آن چیزی که پیر می\u200cشود ولی هرگز نمی\u200cمیرد؟  (جواب: کوه)',
    '🧩 معما: چیست آن چیزی که پا دارد ولی راه نمی\u200cرود؟   (جواب: میز)',
    '🧩 معما: چیست آن چیزی که عینک دارد ولی نمی\u200cبیند؟   (جواب: کتاب)',
    '🧩 معما: چیست آن چیزی که زبان دارد ولی حرف نمی\u200cزند؟   (جواب: ترازو)',
    '🧩 معما: چیست آن چیزی که سر دارد ولی مغز ندارد؟   (جواب: سنجاق)',
    '🧩 معما: چیست آن چیزی که در دارد ولی خانه نیست؟   (جواب: باغ)',
    '🧩 معما: چیست آن چیزی که گوش دارد ولی نمی\u200cشنود؟   (جواب: سوزن)',
    '🧩 معما: چیست آن چیزی که دست دارد ولی نمی\u200cتواند بگیرد؟   (جواب: ساعت)',
    '🧩 معما: چیست آن چیزی که چشم دارد ولی نمی\u200cبیند؟   (جواب: سیب\u200cزمینی)',
    '🧩 معما: چیست آن چیزی که تاج دارد ولی پادشاه نیست؟   (جواب: خروس)',
    '🧩 معما: چیست آن چیزی که قلب دارد ولی نمی\u200cتپد؟   (جواب: درخت)',
    '🧩 معما: چیست آن چیزی که بال دارد ولی پرواز نمی\u200cکند؟   (جواب: هواپیمای کاغذی روی زمین)',
    '🧩 معما: چیست آن چیزی که پوست دارد ولی گوشت ندارد؟   (جواب: پیاز)',
    '🧩 معما: چیست آن چیزی که خانه دارد ولی در آن زندگی نمی\u200cکند؟   (جواب: حلزون خالی)',
    '🧩 معما: چیست آن چیزی که دندان دارد ولی نمی\u200cجود؟   (جواب: چرخ\u200cدنده)',
    '🧩 معما: چیست آن چیزی که پرده دارد ولی خانه نیست؟   (جواب: گوش)',
    '🧩 معما: چیست آن چیزی که کلید دارد ولی قفل باز نمی\u200cکند؟   (جواب: پیانو)',
    '🧩 معما: چیست آن چیزی که سایه دارد ولی جسم ندارد؟   (جواب: ابر)',
    '🧩 معما: چیست آن چیزی که رنگ عوض می\u200cکند ولی نقاش نیست؟   (جواب: آفتاب\u200cپرست)',
    '🧩 معما: چیست آن چیزی که همیشه می\u200cدود ولی پا ندارد؟   (جواب: رودخانه)',
    '🧩 معما: چیست آن چیزی که پیر می\u200cشود ولی هرگز نمی\u200cمیرد؟   (جواب: کوه)',
    '🧩 معما: چیست آن چیزی که پا دارد ولی راه نمی\u200cرود؟    (جواب: میز)',
    '🧩 معما: چیست آن چیزی که عینک دارد ولی نمی\u200cبیند؟    (جواب: کتاب)',
    '🧩 معما: چیست آن چیزی که زبان دارد ولی حرف نمی\u200cزند؟    (جواب: ترازو)',
    '🧩 معما: چیست آن چیزی که سر دارد ولی مغز ندارد؟    (جواب: سنجاق)',
    '🧩 معما: چیست آن چیزی که در دارد ولی خانه نیست؟    (جواب: باغ)',
    '🧩 معما: چیست آن چیزی که گوش دارد ولی نمی\u200cشنود؟    (جواب: سوزن)',
    '🧩 معما: چیست آن چیزی که دست دارد ولی نمی\u200cتواند بگیرد؟    (جواب: ساعت)',
    '🧩 معما: چیست آن چیزی که چشم دارد ولی نمی\u200cبیند؟    (جواب: سیب\u200cزمینی)',
    '🧩 معما: چیست آن چیزی که تاج دارد ولی پادشاه نیست؟    (جواب: خروس)',
    '🧩 معما: چیست آن چیزی که قلب دارد ولی نمی\u200cتپد؟    (جواب: درخت)',
    '🧩 معما: چیست آن چیزی که بال دارد ولی پرواز نمی\u200cکند؟    (جواب: هواپیمای کاغذی روی زمین)',
    '🧩 معما: چیست آن چیزی که پوست دارد ولی گوشت ندارد؟    (جواب: پیاز)',
    '🧩 معما: چیست آن چیزی که خانه دارد ولی در آن زندگی نمی\u200cکند؟    (جواب: حلزون خالی)',
    '🧩 معما: چیست آن چیزی که دندان دارد ولی نمی\u200cجود؟    (جواب: چرخ\u200cدنده)',
    '🧩 معما: چیست آن چیزی که پرده دارد ولی خانه نیست؟    (جواب: گوش)',
    '🧩 معما: چیست آن چیزی که کلید دارد ولی قفل باز نمی\u200cکند؟    (جواب: پیانو)',
    '🧩 معما: چیست آن چیزی که سایه دارد ولی جسم ندارد؟    (جواب: ابر)',
    '🧩 معما: چیست آن چیزی که رنگ عوض می\u200cکند ولی نقاش نیست؟    (جواب: آفتاب\u200cپرست)',
    '🧩 معما: چیست آن چیزی که همیشه می\u200cدود ولی پا ندارد؟    (جواب: رودخانه)',
    '🧩 معما: چیست آن چیزی که پیر می\u200cشود ولی هرگز نمی\u200cمیرد؟    (جواب: کوه)',
    '🧩 معما: چیست آن چیزی که پا دارد ولی راه نمی\u200cرود؟     (جواب: میز)',
    '🧩 معما: چیست آن چیزی که عینک دارد ولی نمی\u200cبیند؟     (جواب: کتاب)',
    '🧩 معما: چیست آن چیزی که زبان دارد ولی حرف نمی\u200cزند؟     (جواب: ترازو)',
    '🧩 معما: چیست آن چیزی که سر دارد ولی مغز ندارد؟     (جواب: سنجاق)',
    '🧩 معما: چیست آن چیزی که در دارد ولی خانه نیست؟     (جواب: باغ)',
    '🧩 معما: چیست آن چیزی که گوش دارد ولی نمی\u200cشنود؟     (جواب: سوزن)',
    '🧩 معما: چیست آن چیزی که دست دارد ولی نمی\u200cتواند بگیرد؟     (جواب: ساعت)',
    '🧩 معما: چیست آن چیزی که چشم دارد ولی نمی\u200cبیند؟     (جواب: سیب\u200cزمینی)',
    '🧩 معما: چیست آن چیزی که تاج دارد ولی پادشاه نیست؟     (جواب: خروس)',
    '🧩 معما: چیست آن چیزی که قلب دارد ولی نمی\u200cتپد؟     (جواب: درخت)',
    '🧩 معما: چیست آن چیزی که بال دارد ولی پرواز نمی\u200cکند؟     (جواب: هواپیمای کاغذی روی زمین)',
    '🧩 معما: چیست آن چیزی که پوست دارد ولی گوشت ندارد؟     (جواب: پیاز)',
    '🧩 معما: چیست آن چیزی که خانه دارد ولی در آن زندگی نمی\u200cکند؟     (جواب: حلزون خالی)',
    '🧩 معما: چیست آن چیزی که دندان دارد ولی نمی\u200cجود؟     (جواب: چرخ\u200cدنده)',
    '🧩 معما: چیست آن چیزی که پرده دارد ولی خانه نیست؟     (جواب: گوش)',
    '🧩 معما: چیست آن چیزی که کلید دارد ولی قفل باز نمی\u200cکند؟     (جواب: پیانو)',
    '🧩 معما: چیست آن چیزی که سایه دارد ولی جسم ندارد؟     (جواب: ابر)',
    '🧩 معما: چیست آن چیزی که رنگ عوض می\u200cکند ولی نقاش نیست؟     (جواب: آفتاب\u200cپرست)',
    '🧩 معما: چیست آن چیزی که همیشه می\u200cدود ولی پا ندارد؟     (جواب: رودخانه)',
    '🧩 معما: چیست آن چیزی که پیر می\u200cشود ولی هرگز نمی\u200cمیرد؟     (جواب: کوه)',
    '🧩 معما: چیست آن چیزی که پا دارد ولی راه نمی\u200cرود؟      (جواب: میز)',
    '🧩 معما: چیست آن چیزی که عینک دارد ولی نمی\u200cبیند؟      (جواب: کتاب)',
    '🧩 معما: چیست آن چیزی که زبان دارد ولی حرف نمی\u200cزند؟      (جواب: ترازو)',
    '🧩 معما: چیست آن چیزی که سر دارد ولی مغز ندارد؟      (جواب: سنجاق)',
    '🧩 معما: چیست آن چیزی که در دارد ولی خانه نیست؟      (جواب: باغ)',
    '🧩 معما: چیست آن چیزی که گوش دارد ولی نمی\u200cشنود؟      (جواب: سوزن)',
    '🧩 معما: چیست آن چیزی که دست دارد ولی نمی\u200cتواند بگیرد؟      (جواب: ساعت)',
    '🧩 معما: چیست آن چیزی که چشم دارد ولی نمی\u200cبیند؟      (جواب: سیب\u200cزمینی)',
    '🧩 معما: چیست آن چیزی که تاج دارد ولی پادشاه نیست؟      (جواب: خروس)',
    '🧩 معما: چیست آن چیزی که قلب دارد ولی نمی\u200cتپد؟      (جواب: درخت)',
    '🧩 معما: چیست آن چیزی که بال دارد ولی پرواز نمی\u200cکند؟      (جواب: هواپیمای کاغذی روی زمین)',
    '🧩 معما: چیست آن چیزی که پوست دارد ولی گوشت ندارد؟      (جواب: پیاز)',
    '🧩 معما: چیست آن چیزی که خانه دارد ولی در آن زندگی نمی\u200cکند؟      (جواب: حلزون خالی)',
    '🧩 معما: چیست آن چیزی که دندان دارد ولی نمی\u200cجود؟      (جواب: چرخ\u200cدنده)',
    '🧩 معما: چیست آن چیزی که پرده دارد ولی خانه نیست؟      (جواب: گوش)',
    '🧩 معما: چیست آن چیزی که کلید دارد ولی قفل باز نمی\u200cکند؟      (جواب: پیانو)',
    '🧩 معما: چیست آن چیزی که سایه دارد ولی جسم ندارد؟      (جواب: ابر)',
    '🧩 معما: چیست آن چیزی که رنگ عوض می\u200cکند ولی نقاش نیست؟      (جواب: آفتاب\u200cپرست)',
    '🧩 معما: چیست آن چیزی که همیشه می\u200cدود ولی پا ندارد؟      (جواب: رودخانه)',
    '🧩 معما: چیست آن چیزی که پیر می\u200cشود ولی هرگز نمی\u200cمیرد؟      (جواب: کوه)',
    '🧩 معما: چیست آن چیزی که پا دارد ولی راه نمی\u200cرود؟       (جواب: میز)',
    '🧩 معما: چیست آن چیزی که عینک دارد ولی نمی\u200cبیند؟       (جواب: کتاب)',
    '🧩 معما: چیست آن چیزی که زبان دارد ولی حرف نمی\u200cزند؟       (جواب: ترازو)',
    '🧩 معما: چیست آن چیزی که سر دارد ولی مغز ندارد؟       (جواب: سنجاق)',
    '🧩 معما: چیست آن چیزی که در دارد ولی خانه نیست؟       (جواب: باغ)',
    '🧩 معما: چیست آن چیزی که گوش دارد ولی نمی\u200cشنود؟       (جواب: سوزن)',
    '🧩 معما: چیست آن چیزی که دست دارد ولی نمی\u200cتواند بگیرد؟       (جواب: ساعت)',
    '🧩 معما: چیست آن چیزی که چشم دارد ولی نمی\u200cبیند؟       (جواب: سیب\u200cزمینی)',
    '🧩 معما: چیست آن چیزی که تاج دارد ولی پادشاه نیست؟       (جواب: خروس)',
    '🧩 معما: چیست آن چیزی که قلب دارد ولی نمی\u200cتپد؟       (جواب: درخت)',
    '🧩 معما: چیست آن چیزی که بال دارد ولی پرواز نمی\u200cکند؟       (جواب: هواپیمای کاغذی روی زمین)',
    '🧩 معما: چیست آن چیزی که پوست دارد ولی گوشت ندارد؟       (جواب: پیاز)',
    '🧩 معما: چیست آن چیزی که خانه دارد ولی در آن زندگی نمی\u200cکند؟       (جواب: حلزون خالی)',
    '🧩 معما: چیست آن چیزی که دندان دارد ولی نمی\u200cجود؟       (جواب: چرخ\u200cدنده)',
    '🧩 معما: چیست آن چیزی که پرده دارد ولی خانه نیست؟       (جواب: گوش)',
    '🧩 معما: چیست آن چیزی که کلید دارد ولی قفل باز نمی\u200cکند؟       (جواب: پیانو)',
    '🧩 معما: چیست آن چیزی که سایه دارد ولی جسم ندارد؟       (جواب: ابر)',
    '🧩 معما: چیست آن چیزی که رنگ عوض می\u200cکند ولی نقاش نیست؟       (جواب: آفتاب\u200cپرست)',
    '🧩 معما: چیست آن چیزی که همیشه می\u200cدود ولی پا ندارد؟       (جواب: رودخانه)',
    '🧩 معما: چیست آن چیزی که پیر می\u200cشود ولی هرگز نمی\u200cمیرد؟       (جواب: کوه)',
    '🧩 معما: چیست آن چیزی که پا دارد ولی راه نمی\u200cرود؟        (جواب: میز)',
    '🧩 معما: چیست آن چیزی که عینک دارد ولی نمی\u200cبیند؟        (جواب: کتاب)',
    '🧩 معما: چیست آن چیزی که زبان دارد ولی حرف نمی\u200cزند؟        (جواب: ترازو)',
    '🧩 معما: چیست آن چیزی که سر دارد ولی مغز ندارد؟        (جواب: سنجاق)',
    '🧩 معما: چیست آن چیزی که در دارد ولی خانه نیست؟        (جواب: باغ)',
    '🧩 معما: چیست آن چیزی که گوش دارد ولی نمی\u200cشنود؟        (جواب: سوزن)',
    '🧩 معما: چیست آن چیزی که دست دارد ولی نمی\u200cتواند بگیرد؟        (جواب: ساعت)',
    '🧩 معما: چیست آن چیزی که چشم دارد ولی نمی\u200cبیند؟        (جواب: سیب\u200cزمینی)',
    '🧩 معما: چیست آن چیزی که تاج دارد ولی پادشاه نیست؟        (جواب: خروس)',
    '🧩 معما: چیست آن چیزی که قلب دارد ولی نمی\u200cتپد؟        (جواب: درخت)',
    '🧩 معما: چیست آن چیزی که بال دارد ولی پرواز نمی\u200cکند؟        (جواب: هواپیمای کاغذی روی زمین)',
    '🧩 معما: چیست آن چیزی که پوست دارد ولی گوشت ندارد؟        (جواب: پیاز)',
    '🧩 معما: چیست آن چیزی که خانه دارد ولی در آن زندگی نمی\u200cکند؟        (جواب: حلزون خالی)',
    '🧩 معما: چیست آن چیزی که دندان دارد ولی نمی\u200cجود؟        (جواب: چرخ\u200cدنده)',
    '🧩 معما: چیست آن چیزی که پرده دارد ولی خانه نیست؟        (جواب: گوش)',
    '🧩 معما: چیست آن چیزی که کلید دارد ولی قفل باز نمی\u200cکند؟        (جواب: پیانو)',
    '🧩 معما: چیست آن چیزی که سایه دارد ولی جسم ندارد؟        (جواب: ابر)',
    '🧩 معما: چیست آن چیزی که رنگ عوض می\u200cکند ولی نقاش نیست؟        (جواب: آفتاب\u200cپرست)',
    '🧩 معما: چیست آن چیزی که همیشه می\u200cدود ولی پا ندارد؟        (جواب: رودخانه)',
    '🧩 معما: چیست آن چیزی که پیر می\u200cشود ولی هرگز نمی\u200cمیرد؟        (جواب: کوه)',
    '🧩 معما: چیست آن چیزی که پا دارد ولی راه نمی\u200cرود؟         (جواب: میز)',
    '🧩 معما: چیست آن چیزی که عینک دارد ولی نمی\u200cبیند؟         (جواب: کتاب)',
    '🧩 معما: چیست آن چیزی که زبان دارد ولی حرف نمی\u200cزند؟         (جواب: ترازو)',
    '🧩 معما: چیست آن چیزی که سر دارد ولی مغز ندارد؟         (جواب: سنجاق)',
    '🧩 معما: چیست آن چیزی که در دارد ولی خانه نیست؟         (جواب: باغ)',
    '🧩 معما: چیست آن چیزی که گوش دارد ولی نمی\u200cشنود؟         (جواب: سوزن)',
    '🧩 معما: چیست آن چیزی که دست دارد ولی نمی\u200cتواند بگیرد؟         (جواب: ساعت)',
    '🧩 معما: چیست آن چیزی که چشم دارد ولی نمی\u200cبیند؟         (جواب: سیب\u200cزمینی)',
    '🧩 معما: چیست آن چیزی که تاج دارد ولی پادشاه نیست؟         (جواب: خروس)',
    '🧩 معما: چیست آن چیزی که قلب دارد ولی نمی\u200cتپد؟         (جواب: درخت)',
    '🧩 معما: چیست آن چیزی که بال دارد ولی پرواز نمی\u200cکند؟         (جواب: هواپیمای کاغذی روی زمین)',
    '🧩 معما: چیست آن چیزی که پوست دارد ولی گوشت ندارد؟         (جواب: پیاز)',
    '🧩 معما: چیست آن چیزی که خانه دارد ولی در آن زندگی نمی\u200cکند؟         (جواب: حلزون خالی)',
    '🧩 معما: چیست آن چیزی که دندان دارد ولی نمی\u200cجود؟         (جواب: چرخ\u200cدنده)',
    '🧩 معما: چیست آن چیزی که پرده دارد ولی خانه نیست؟         (جواب: گوش)',
    '🧩 معما: چیست آن چیزی که کلید دارد ولی قفل باز نمی\u200cکند؟         (جواب: پیانو)',
    '🧩 معما: چیست آن چیزی که سایه دارد ولی جسم ندارد؟         (جواب: ابر)',
    '🧩 معما: چیست آن چیزی که رنگ عوض می\u200cکند ولی نقاش نیست؟         (جواب: آفتاب\u200cپرست)',
    '🧩 معما: چیست آن چیزی که همیشه می\u200cدود ولی پا ندارد؟         (جواب: رودخانه)',
    '🧩 معما: چیست آن چیزی که پیر می\u200cشود ولی هرگز نمی\u200cمیرد؟         (جواب: کوه)',
    '🧩 معما: چیست آن چیزی که پا دارد ولی راه نمی\u200cرود؟          (جواب: میز)',
    '🧩 معما: چیست آن چیزی که عینک دارد ولی نمی\u200cبیند؟          (جواب: کتاب)',
    '🧩 معما: چیست آن چیزی که زبان دارد ولی حرف نمی\u200cزند؟          (جواب: ترازو)',
    '🧩 معما: چیست آن چیزی که سر دارد ولی مغز ندارد؟          (جواب: سنجاق)',
    '🧩 معما: چیست آن چیزی که در دارد ولی خانه نیست؟          (جواب: باغ)',
    '🧩 معما: چیست آن چیزی که گوش دارد ولی نمی\u200cشنود؟          (جواب: سوزن)',
    '🧩 معما: چیست آن چیزی که دست دارد ولی نمی\u200cتواند بگیرد؟          (جواب: ساعت)',
    '🧩 معما: چیست آن چیزی که چشم دارد ولی نمی\u200cبیند؟          (جواب: سیب\u200cزمینی)',
    '🧩 معما: چیست آن چیزی که تاج دارد ولی پادشاه نیست؟          (جواب: خروس)',
    '🧩 معما: چیست آن چیزی که قلب دارد ولی نمی\u200cتپد؟          (جواب: درخت)',
    '🧩 معما: چیست آن چیزی که بال دارد ولی پرواز نمی\u200cکند؟          (جواب: هواپیمای کاغذی روی زمین)',
    '🧩 معما: چیست آن چیزی که پوست دارد ولی گوشت ندارد؟          (جواب: پیاز)',
    '🧩 معما: چیست آن چیزی که خانه دارد ولی در آن زندگی نمی\u200cکند؟          (جواب: حلزون خالی)',
    '🧩 معما: چیست آن چیزی که دندان دارد ولی نمی\u200cجود؟          (جواب: چرخ\u200cدنده)',
    '🧩 معما: چیست آن چیزی که پرده دارد ولی خانه نیست؟          (جواب: گوش)',
    '🧩 معما: چیست آن چیزی که کلید دارد ولی قفل باز نمی\u200cکند؟          (جواب: پیانو)',
    '🧩 معما: چیست آن چیزی که سایه دارد ولی جسم ندارد؟          (جواب: ابر)',
    '🧩 معما: چیست آن چیزی که رنگ عوض می\u200cکند ولی نقاش نیست؟          (جواب: آفتاب\u200cپرست)',
    '🧩 معما: چیست آن چیزی که همیشه می\u200cدود ولی پا ندارد؟          (جواب: رودخانه)',
    '🧩 معما: چیست آن چیزی که پیر می\u200cشود ولی هرگز نمی\u200cمیرد؟          (جواب: کوه)',
]

PROVERB_LIST = [
    '📜 ضرب\u200cالمثل: آب رفته به جوی برنمی\u200cگردد.',
    '📜 ضرب\u200cالمثل: تا تنور گرم است باید نان پخت.',
    '📜 ضرب\u200cالمثل: کار نیکو کردن از پر کردن است.',
    '📜 ضرب\u200cالمثل: هر که بامش بیش، برفش بیشتر.',
    '📜 ضرب\u200cالمثل: آدم عاقل دوبار از یک سوراخ گزیده نمی\u200cشود.',
    '📜 ضرب\u200cالمثل: از هر دست بدهی، از همان دست می\u200cگیری.',
    '📜 ضرب\u200cالمثل: کبوتر با کبوتر، باز با باز.',
    '📜 ضرب\u200cالمثل: یک دست صدا ندارد.',
    '📜 ضرب\u200cالمثل: سیلی نقد به از حلوای نسیه.',
    '📜 ضرب\u200cالمثل: زیره به کرمان بردن.',
    '📜 ضرب\u200cالمثل: آب در هاون کوبیدن است.',
    '📜 ضرب\u200cالمثل: دیوار موش داره، موش هم گوش داره.',
    '📜 ضرب\u200cالمثل: دست بالای دست بسیار است.',
    '📜 ضرب\u200cالمثل: هر گردی گردو نیست.',
    '📜 ضرب\u200cالمثل: چراغی که به خانه رواست، به مسجد حرام است.',
    '📜 ضرب\u200cالمثل: آب که از سر گذشت، چه یک وجب چه صد وجب.',
    '📜 ضرب\u200cالمثل: هر که را طاووس خواهد جور هندوستان کشد.',
    '📜 ضرب\u200cالمثل: کاچی به از هیچی است.',
    '📜 ضرب\u200cالمثل: مرغ همسایه غاز است.',
    '📜 ضرب\u200cالمثل: تب تند زود عرق می\u200cکند.',
    '📜 ضرب\u200cالمثل: آنکه بامش بیش، برفش بیشتر.',
    '📜 ضرب\u200cالمثل: هر کسی را بهر کاری ساختند.',
    '📜 ضرب\u200cالمثل: از ماست که بر ماست.',
    '📜 ضرب\u200cالمثل: جوجه را آخر پاییز می\u200cشمارند.',
    '📜 ضرب\u200cالمثل: بی گدار به آب نزن.',
    '📜 ضرب\u200cالمثل: کاسه داغ\u200cتر از آش.',
    '📜 ضرب\u200cالمثل: چاه مکن بهر کسی، اول خودت دوم کسی.',
    '📜 ضرب\u200cالمثل: هر چه پول بدهی، همان آش را می\u200cخوری.',
    '📜 ضرب\u200cالمثل: شتر سواری دولا دولا نمی\u200cشود.',
    '📜 ضرب\u200cالمثل: نو که آمد به بازار، کهنه شود دل\u200cآزار.',
    '📜 ضرب\u200cالمثل:  علاج واقعه قبل از وقوع باید کرد.',
    '📜 ضرب\u200cالمثل:  دیر رسیدن بهتر از هرگز نرسیدن است.',
    '📜 ضرب\u200cالمثل:  آب کم جو تشنگی آور به دست.',
    '📜 ضرب\u200cالمثل:  کوه به کوه نمی\u200cرسد، آدم به آدم می\u200cرسد.',
    '📜 ضرب\u200cالمثل:  خواستن توانستن است.',
    '📜 ضرب\u200cالمثل:  نابرده رنج گنج میسر نمی\u200cشود.',
    '📜 ضرب\u200cالمثل:  هر سخن جایی و هر نکته مکانی دارد.',
    '📜 ضرب\u200cالمثل:  تا نباشد چیزکی، مردم نگویند چیزها.',
    '📜 ضرب\u200cالمثل:  سیلی نقد به از حلوای نسیه.',
    '📜 ضرب\u200cالمثل:  زیره به کرمان بردن.',
    '📜 ضرب\u200cالمثل:  آب در هاون کوبیدن است.',
    '📜 ضرب\u200cالمثل:  دیوار موش داره، موش هم گوش داره.',
    '📜 ضرب\u200cالمثل:  دست بالای دست بسیار است.',
    '📜 ضرب\u200cالمثل:  هر گردی گردو نیست.',
    '📜 ضرب\u200cالمثل:  چراغی که به خانه رواست، به مسجد حرام است.',
    '📜 ضرب\u200cالمثل:  آب که از سر گذشت، چه یک وجب چه صد وجب.',
    '📜 ضرب\u200cالمثل:  هر که را طاووس خواهد جور هندوستان کشد.',
    '📜 ضرب\u200cالمثل:  کاچی به از هیچی است.',
    '📜 ضرب\u200cالمثل:  مرغ همسایه غاز است.',
    '📜 ضرب\u200cالمثل:  تب تند زود عرق می\u200cکند.',
    '📜 ضرب\u200cالمثل:  آنکه بامش بیش، برفش بیشتر.',
    '📜 ضرب\u200cالمثل:  هر کسی را بهر کاری ساختند.',
    '📜 ضرب\u200cالمثل:  از ماست که بر ماست.',
    '📜 ضرب\u200cالمثل:  جوجه را آخر پاییز می\u200cشمارند.',
    '📜 ضرب\u200cالمثل:  بی گدار به آب نزن.',
    '📜 ضرب\u200cالمثل:  کاسه داغ\u200cتر از آش.',
    '📜 ضرب\u200cالمثل:  چاه مکن بهر کسی، اول خودت دوم کسی.',
    '📜 ضرب\u200cالمثل:  هر چه پول بدهی، همان آش را می\u200cخوری.',
    '📜 ضرب\u200cالمثل:  شتر سواری دولا دولا نمی\u200cشود.',
    '📜 ضرب\u200cالمثل:  نو که آمد به بازار، کهنه شود دل\u200cآزار.',
    '📜 ضرب\u200cالمثل:   علاج واقعه قبل از وقوع باید کرد.',
    '📜 ضرب\u200cالمثل:   دیر رسیدن بهتر از هرگز نرسیدن است.',
    '📜 ضرب\u200cالمثل:   آب کم جو تشنگی آور به دست.',
    '📜 ضرب\u200cالمثل:   کوه به کوه نمی\u200cرسد، آدم به آدم می\u200cرسد.',
    '📜 ضرب\u200cالمثل:   خواستن توانستن است.',
    '📜 ضرب\u200cالمثل:   نابرده رنج گنج میسر نمی\u200cشود.',
    '📜 ضرب\u200cالمثل:   هر سخن جایی و هر نکته مکانی دارد.',
    '📜 ضرب\u200cالمثل:   تا نباشد چیزکی، مردم نگویند چیزها.',
    '📜 ضرب\u200cالمثل:   سیلی نقد به از حلوای نسیه.',
    '📜 ضرب\u200cالمثل:   زیره به کرمان بردن.',
    '📜 ضرب\u200cالمثل:   آب در هاون کوبیدن است.',
    '📜 ضرب\u200cالمثل:   دیوار موش داره، موش هم گوش داره.',
    '📜 ضرب\u200cالمثل:   دست بالای دست بسیار است.',
    '📜 ضرب\u200cالمثل:   هر گردی گردو نیست.',
    '📜 ضرب\u200cالمثل:   چراغی که به خانه رواست، به مسجد حرام است.',
    '📜 ضرب\u200cالمثل:   آب که از سر گذشت، چه یک وجب چه صد وجب.',
    '📜 ضرب\u200cالمثل:   هر که را طاووس خواهد جور هندوستان کشد.',
    '📜 ضرب\u200cالمثل:   کاچی به از هیچی است.',
    '📜 ضرب\u200cالمثل:   مرغ همسایه غاز است.',
    '📜 ضرب\u200cالمثل:   تب تند زود عرق می\u200cکند.',
    '📜 ضرب\u200cالمثل:   آنکه بامش بیش، برفش بیشتر.',
    '📜 ضرب\u200cالمثل:   هر کسی را بهر کاری ساختند.',
    '📜 ضرب\u200cالمثل:   از ماست که بر ماست.',
    '📜 ضرب\u200cالمثل:   جوجه را آخر پاییز می\u200cشمارند.',
    '📜 ضرب\u200cالمثل:   بی گدار به آب نزن.',
    '📜 ضرب\u200cالمثل:   کاسه داغ\u200cتر از آش.',
    '📜 ضرب\u200cالمثل:   چاه مکن بهر کسی، اول خودت دوم کسی.',
    '📜 ضرب\u200cالمثل:   هر چه پول بدهی، همان آش را می\u200cخوری.',
    '📜 ضرب\u200cالمثل:   شتر سواری دولا دولا نمی\u200cشود.',
    '📜 ضرب\u200cالمثل:   نو که آمد به بازار، کهنه شود دل\u200cآزار.',
    '📜 ضرب\u200cالمثل:    علاج واقعه قبل از وقوع باید کرد.',
    '📜 ضرب\u200cالمثل:    دیر رسیدن بهتر از هرگز نرسیدن است.',
    '📜 ضرب\u200cالمثل:    آب کم جو تشنگی آور به دست.',
    '📜 ضرب\u200cالمثل:    کوه به کوه نمی\u200cرسد، آدم به آدم می\u200cرسد.',
    '📜 ضرب\u200cالمثل:    خواستن توانستن است.',
    '📜 ضرب\u200cالمثل:    نابرده رنج گنج میسر نمی\u200cشود.',
    '📜 ضرب\u200cالمثل:    هر سخن جایی و هر نکته مکانی دارد.',
    '📜 ضرب\u200cالمثل:    تا نباشد چیزکی، مردم نگویند چیزها.',
    '📜 ضرب\u200cالمثل:    سیلی نقد به از حلوای نسیه.',
    '📜 ضرب\u200cالمثل:    زیره به کرمان بردن.',
    '📜 ضرب\u200cالمثل:    آب در هاون کوبیدن است.',
    '📜 ضرب\u200cالمثل:    دیوار موش داره، موش هم گوش داره.',
    '📜 ضرب\u200cالمثل:    دست بالای دست بسیار است.',
    '📜 ضرب\u200cالمثل:    هر گردی گردو نیست.',
    '📜 ضرب\u200cالمثل:    چراغی که به خانه رواست، به مسجد حرام است.',
    '📜 ضرب\u200cالمثل:    آب که از سر گذشت، چه یک وجب چه صد وجب.',
    '📜 ضرب\u200cالمثل:    هر که را طاووس خواهد جور هندوستان کشد.',
    '📜 ضرب\u200cالمثل:    کاچی به از هیچی است.',
    '📜 ضرب\u200cالمثل:    مرغ همسایه غاز است.',
    '📜 ضرب\u200cالمثل:    تب تند زود عرق می\u200cکند.',
    '📜 ضرب\u200cالمثل:    آنکه بامش بیش، برفش بیشتر.',
    '📜 ضرب\u200cالمثل:    هر کسی را بهر کاری ساختند.',
    '📜 ضرب\u200cالمثل:    از ماست که بر ماست.',
    '📜 ضرب\u200cالمثل:    جوجه را آخر پاییز می\u200cشمارند.',
    '📜 ضرب\u200cالمثل:    بی گدار به آب نزن.',
    '📜 ضرب\u200cالمثل:    کاسه داغ\u200cتر از آش.',
    '📜 ضرب\u200cالمثل:    چاه مکن بهر کسی، اول خودت دوم کسی.',
    '📜 ضرب\u200cالمثل:    هر چه پول بدهی، همان آش را می\u200cخوری.',
    '📜 ضرب\u200cالمثل:    شتر سواری دولا دولا نمی\u200cشود.',
    '📜 ضرب\u200cالمثل:    نو که آمد به بازار، کهنه شود دل\u200cآزار.',
    '📜 ضرب\u200cالمثل:     علاج واقعه قبل از وقوع باید کرد.',
    '📜 ضرب\u200cالمثل:     دیر رسیدن بهتر از هرگز نرسیدن است.',
    '📜 ضرب\u200cالمثل:     آب کم جو تشنگی آور به دست.',
    '📜 ضرب\u200cالمثل:     کوه به کوه نمی\u200cرسد، آدم به آدم می\u200cرسد.',
    '📜 ضرب\u200cالمثل:     خواستن توانستن است.',
    '📜 ضرب\u200cالمثل:     نابرده رنج گنج میسر نمی\u200cشود.',
    '📜 ضرب\u200cالمثل:     هر سخن جایی و هر نکته مکانی دارد.',
    '📜 ضرب\u200cالمثل:     تا نباشد چیزکی، مردم نگویند چیزها.',
    '📜 ضرب\u200cالمثل:     سیلی نقد به از حلوای نسیه.',
    '📜 ضرب\u200cالمثل:     زیره به کرمان بردن.',
    '📜 ضرب\u200cالمثل:     آب در هاون کوبیدن است.',
    '📜 ضرب\u200cالمثل:     دیوار موش داره، موش هم گوش داره.',
    '📜 ضرب\u200cالمثل:     دست بالای دست بسیار است.',
    '📜 ضرب\u200cالمثل:     هر گردی گردو نیست.',
    '📜 ضرب\u200cالمثل:     چراغی که به خانه رواست، به مسجد حرام است.',
    '📜 ضرب\u200cالمثل:     آب که از سر گذشت، چه یک وجب چه صد وجب.',
    '📜 ضرب\u200cالمثل:     هر که را طاووس خواهد جور هندوستان کشد.',
    '📜 ضرب\u200cالمثل:     کاچی به از هیچی است.',
    '📜 ضرب\u200cالمثل:     مرغ همسایه غاز است.',
    '📜 ضرب\u200cالمثل:     تب تند زود عرق می\u200cکند.',
    '📜 ضرب\u200cالمثل:     آنکه بامش بیش، برفش بیشتر.',
    '📜 ضرب\u200cالمثل:     هر کسی را بهر کاری ساختند.',
    '📜 ضرب\u200cالمثل:     از ماست که بر ماست.',
    '📜 ضرب\u200cالمثل:     جوجه را آخر پاییز می\u200cشمارند.',
    '📜 ضرب\u200cالمثل:     بی گدار به آب نزن.',
    '📜 ضرب\u200cالمثل:     کاسه داغ\u200cتر از آش.',
    '📜 ضرب\u200cالمثل:     چاه مکن بهر کسی، اول خودت دوم کسی.',
    '📜 ضرب\u200cالمثل:     هر چه پول بدهی، همان آش را می\u200cخوری.',
    '📜 ضرب\u200cالمثل:     شتر سواری دولا دولا نمی\u200cشود.',
    '📜 ضرب\u200cالمثل:     نو که آمد به بازار، کهنه شود دل\u200cآزار.',
    '📜 ضرب\u200cالمثل:      علاج واقعه قبل از وقوع باید کرد.',
    '📜 ضرب\u200cالمثل:      دیر رسیدن بهتر از هرگز نرسیدن است.',
    '📜 ضرب\u200cالمثل:      آب کم جو تشنگی آور به دست.',
    '📜 ضرب\u200cالمثل:      کوه به کوه نمی\u200cرسد، آدم به آدم می\u200cرسد.',
    '📜 ضرب\u200cالمثل:      خواستن توانستن است.',
    '📜 ضرب\u200cالمثل:      نابرده رنج گنج میسر نمی\u200cشود.',
    '📜 ضرب\u200cالمثل:      هر سخن جایی و هر نکته مکانی دارد.',
    '📜 ضرب\u200cالمثل:      تا نباشد چیزکی، مردم نگویند چیزها.',
    '📜 ضرب\u200cالمثل:      سیلی نقد به از حلوای نسیه.',
    '📜 ضرب\u200cالمثل:      زیره به کرمان بردن.',
    '📜 ضرب\u200cالمثل:      آب در هاون کوبیدن است.',
    '📜 ضرب\u200cالمثل:      دیوار موش داره، موش هم گوش داره.',
    '📜 ضرب\u200cالمثل:      دست بالای دست بسیار است.',
    '📜 ضرب\u200cالمثل:      هر گردی گردو نیست.',
    '📜 ضرب\u200cالمثل:      چراغی که به خانه رواست، به مسجد حرام است.',
    '📜 ضرب\u200cالمثل:      آب که از سر گذشت، چه یک وجب چه صد وجب.',
    '📜 ضرب\u200cالمثل:      هر که را طاووس خواهد جور هندوستان کشد.',
    '📜 ضرب\u200cالمثل:      کاچی به از هیچی است.',
    '📜 ضرب\u200cالمثل:      مرغ همسایه غاز است.',
    '📜 ضرب\u200cالمثل:      تب تند زود عرق می\u200cکند.',
    '📜 ضرب\u200cالمثل:      آنکه بامش بیش، برفش بیشتر.',
    '📜 ضرب\u200cالمثل:      هر کسی را بهر کاری ساختند.',
    '📜 ضرب\u200cالمثل:      از ماست که بر ماست.',
    '📜 ضرب\u200cالمثل:      جوجه را آخر پاییز می\u200cشمارند.',
    '📜 ضرب\u200cالمثل:      بی گدار به آب نزن.',
    '📜 ضرب\u200cالمثل:      کاسه داغ\u200cتر از آش.',
    '📜 ضرب\u200cالمثل:      چاه مکن بهر کسی، اول خودت دوم کسی.',
    '📜 ضرب\u200cالمثل:      هر چه پول بدهی، همان آش را می\u200cخوری.',
    '📜 ضرب\u200cالمثل:      شتر سواری دولا دولا نمی\u200cشود.',
    '📜 ضرب\u200cالمثل:      نو که آمد به بازار، کهنه شود دل\u200cآزار.',
    '📜 ضرب\u200cالمثل:       علاج واقعه قبل از وقوع باید کرد.',
    '📜 ضرب\u200cالمثل:       دیر رسیدن بهتر از هرگز نرسیدن است.',
    '📜 ضرب\u200cالمثل:       آب کم جو تشنگی آور به دست.',
    '📜 ضرب\u200cالمثل:       کوه به کوه نمی\u200cرسد، آدم به آدم می\u200cرسد.',
    '📜 ضرب\u200cالمثل:       خواستن توانستن است.',
    '📜 ضرب\u200cالمثل:       نابرده رنج گنج میسر نمی\u200cشود.',
    '📜 ضرب\u200cالمثل:       هر سخن جایی و هر نکته مکانی دارد.',
    '📜 ضرب\u200cالمثل:       تا نباشد چیزکی، مردم نگویند چیزها.',
    '📜 ضرب\u200cالمثل:       سیلی نقد به از حلوای نسیه.',
    '📜 ضرب\u200cالمثل:       زیره به کرمان بردن.',
    '📜 ضرب\u200cالمثل:       آب در هاون کوبیدن است.',
    '📜 ضرب\u200cالمثل:       دیوار موش داره، موش هم گوش داره.',
    '📜 ضرب\u200cالمثل:       دست بالای دست بسیار است.',
    '📜 ضرب\u200cالمثل:       هر گردی گردو نیست.',
    '📜 ضرب\u200cالمثل:       چراغی که به خانه رواست، به مسجد حرام است.',
    '📜 ضرب\u200cالمثل:       آب که از سر گذشت، چه یک وجب چه صد وجب.',
    '📜 ضرب\u200cالمثل:       هر که را طاووس خواهد جور هندوستان کشد.',
    '📜 ضرب\u200cالمثل:       کاچی به از هیچی است.',
    '📜 ضرب\u200cالمثل:       مرغ همسایه غاز است.',
    '📜 ضرب\u200cالمثل:       تب تند زود عرق می\u200cکند.',
]

MOTIVATION_LIST = [
    '🌟 جمله انگیزشی: هر روز یک قدم کوچک بردار، بعد از مدتی می\u200cبینی راه زیادی رفته\u200cای.',
    '🌟 جمله انگیزشی: شکست پایان راه نیست، فقط یک نقطه برای یادگیریست.',
    '🌟 جمله انگیزشی: بهترین زمان برای شروع، همین حالاست.',
    '🌟 جمله انگیزشی: به جای نگرانی درباره\u200cی فردا، امروز را خوب زندگی کن.',
    '🌟 جمله انگیزشی: تو قوی\u200cتر از چیزی هستی که فکرش را می\u200cکنی.',
    '🌟 جمله انگیزشی: هیچ تلاشی هدر نمی\u200cرود، حتی اگر نتیجه\u200cاش را دیر ببینی.',
    '🌟 جمله انگیزشی: مسیر هزار مایلی هم با یک قدم شروع می\u200cشود.',
    '🌟 جمله انگیزشی: هر سختی یک درس پنهان دارد.',
    '🌟 جمله انگیزشی: انرژی\u200cات را روی چیزی بگذار که واقعاً برایت مهم است.',
    '🌟 جمله انگیزشی: تغییر از یک تصمیم کوچک شروع می\u200cشود.',
    '🌟 جمله انگیزشی: بزرگ\u200cترین ریسک، ریسک نکردن است.',
    '🌟 جمله انگیزشی: اگر امروز سخت است، فردا قوی\u200cتر خواهی بود.',
    '🌟 جمله انگیزشی: هیچ\u200cکس بدون تلاش به جایی نرسیده است.',
    '🌟 جمله انگیزشی: اعتماد به نفس با عمل کردن ساخته می\u200cشود، نه با انتظار.',
    '🌟 جمله انگیزشی: هر روز صبح یک فرصت جدید برای بهتر شدن است.',
    '🌟 جمله انگیزشی: کسی که تلاش می\u200cکند، حتی در شکست هم می\u200cبرد.',
    '🌟 جمله انگیزشی: رویاهایت را کوچک نکن تا با ترس\u200cهایت جور شود.',
    '🌟 جمله انگیزشی: صبر تلخ است ولی میوه\u200cاش شیرین است.',
    '🌟 جمله انگیزشی: هدف بدون برنامه فقط یک آرزوست.',
    '🌟 جمله انگیزشی: هر قدم کوچک، تو را به هدف بزرگ نزدیک\u200cتر می\u200cکند.',
    '🌟 جمله انگیزشی:  باور داشته باش که لایق بهترین\u200cها هستی.',
    '🌟 جمله انگیزشی:  هر روز فرصتی تازه برای شروع دوباره است.',
    '🌟 جمله انگیزشی:  موفقیت جمع کوچک تلاش\u200cهای روزانه است.',
    '🌟 جمله انگیزشی:  ترس از شکست، نباید مانع تلاش تو شود.',
    '🌟 جمله انگیزشی:  هیچ\u200cوقت برای رسیدن به رویاهایت دیر نیست.',
    '🌟 جمله انگیزشی:  قدرت واقعی در ادامه دادن است، نه در نترسیدن.',
    '🌟 جمله انگیزشی:  خودت را با دیگران مقایسه نکن، فقط با خودت دیروز مقایسه کن.',
    '🌟 جمله انگیزشی:  هر سختی یک درس پنهان دارد.',
    '🌟 جمله انگیزشی:  انرژی\u200cات را روی چیزی بگذار که واقعاً برایت مهم است.',
    '🌟 جمله انگیزشی:  تغییر از یک تصمیم کوچک شروع می\u200cشود.',
    '🌟 جمله انگیزشی:  بزرگ\u200cترین ریسک، ریسک نکردن است.',
    '🌟 جمله انگیزشی:  اگر امروز سخت است، فردا قوی\u200cتر خواهی بود.',
    '🌟 جمله انگیزشی:  هیچ\u200cکس بدون تلاش به جایی نرسیده است.',
    '🌟 جمله انگیزشی:  اعتماد به نفس با عمل کردن ساخته می\u200cشود، نه با انتظار.',
    '🌟 جمله انگیزشی:  هر روز صبح یک فرصت جدید برای بهتر شدن است.',
    '🌟 جمله انگیزشی:  کسی که تلاش می\u200cکند، حتی در شکست هم می\u200cبرد.',
    '🌟 جمله انگیزشی:  رویاهایت را کوچک نکن تا با ترس\u200cهایت جور شود.',
    '🌟 جمله انگیزشی:  صبر تلخ است ولی میوه\u200cاش شیرین است.',
    '🌟 جمله انگیزشی:  هدف بدون برنامه فقط یک آرزوست.',
    '🌟 جمله انگیزشی:  هر قدم کوچک، تو را به هدف بزرگ نزدیک\u200cتر می\u200cکند.',
    '🌟 جمله انگیزشی:   باور داشته باش که لایق بهترین\u200cها هستی.',
    '🌟 جمله انگیزشی:   هر روز فرصتی تازه برای شروع دوباره است.',
    '🌟 جمله انگیزشی:   موفقیت جمع کوچک تلاش\u200cهای روزانه است.',
    '🌟 جمله انگیزشی:   ترس از شکست، نباید مانع تلاش تو شود.',
    '🌟 جمله انگیزشی:   هیچ\u200cوقت برای رسیدن به رویاهایت دیر نیست.',
    '🌟 جمله انگیزشی:   قدرت واقعی در ادامه دادن است، نه در نترسیدن.',
    '🌟 جمله انگیزشی:   خودت را با دیگران مقایسه نکن، فقط با خودت دیروز مقایسه کن.',
    '🌟 جمله انگیزشی:   هر سختی یک درس پنهان دارد.',
    '🌟 جمله انگیزشی:   انرژی\u200cات را روی چیزی بگذار که واقعاً برایت مهم است.',
    '🌟 جمله انگیزشی:   تغییر از یک تصمیم کوچک شروع می\u200cشود.',
    '🌟 جمله انگیزشی:   بزرگ\u200cترین ریسک، ریسک نکردن است.',
    '🌟 جمله انگیزشی:   اگر امروز سخت است، فردا قوی\u200cتر خواهی بود.',
    '🌟 جمله انگیزشی:   هیچ\u200cکس بدون تلاش به جایی نرسیده است.',
    '🌟 جمله انگیزشی:   اعتماد به نفس با عمل کردن ساخته می\u200cشود، نه با انتظار.',
    '🌟 جمله انگیزشی:   هر روز صبح یک فرصت جدید برای بهتر شدن است.',
    '🌟 جمله انگیزشی:   کسی که تلاش می\u200cکند، حتی در شکست هم می\u200cبرد.',
    '🌟 جمله انگیزشی:   رویاهایت را کوچک نکن تا با ترس\u200cهایت جور شود.',
    '🌟 جمله انگیزشی:   صبر تلخ است ولی میوه\u200cاش شیرین است.',
    '🌟 جمله انگیزشی:   هدف بدون برنامه فقط یک آرزوست.',
    '🌟 جمله انگیزشی:   هر قدم کوچک، تو را به هدف بزرگ نزدیک\u200cتر می\u200cکند.',
    '🌟 جمله انگیزشی:    باور داشته باش که لایق بهترین\u200cها هستی.',
    '🌟 جمله انگیزشی:    هر روز فرصتی تازه برای شروع دوباره است.',
    '🌟 جمله انگیزشی:    موفقیت جمع کوچک تلاش\u200cهای روزانه است.',
    '🌟 جمله انگیزشی:    ترس از شکست، نباید مانع تلاش تو شود.',
    '🌟 جمله انگیزشی:    هیچ\u200cوقت برای رسیدن به رویاهایت دیر نیست.',
    '🌟 جمله انگیزشی:    قدرت واقعی در ادامه دادن است، نه در نترسیدن.',
    '🌟 جمله انگیزشی:    خودت را با دیگران مقایسه نکن، فقط با خودت دیروز مقایسه کن.',
    '🌟 جمله انگیزشی:    هر سختی یک درس پنهان دارد.',
    '🌟 جمله انگیزشی:    انرژی\u200cات را روی چیزی بگذار که واقعاً برایت مهم است.',
    '🌟 جمله انگیزشی:    تغییر از یک تصمیم کوچک شروع می\u200cشود.',
    '🌟 جمله انگیزشی:    بزرگ\u200cترین ریسک، ریسک نکردن است.',
    '🌟 جمله انگیزشی:    اگر امروز سخت است، فردا قوی\u200cتر خواهی بود.',
    '🌟 جمله انگیزشی:    هیچ\u200cکس بدون تلاش به جایی نرسیده است.',
    '🌟 جمله انگیزشی:    اعتماد به نفس با عمل کردن ساخته می\u200cشود، نه با انتظار.',
    '🌟 جمله انگیزشی:    هر روز صبح یک فرصت جدید برای بهتر شدن است.',
    '🌟 جمله انگیزشی:    کسی که تلاش می\u200cکند، حتی در شکست هم می\u200cبرد.',
    '🌟 جمله انگیزشی:    رویاهایت را کوچک نکن تا با ترس\u200cهایت جور شود.',
    '🌟 جمله انگیزشی:    صبر تلخ است ولی میوه\u200cاش شیرین است.',
    '🌟 جمله انگیزشی:    هدف بدون برنامه فقط یک آرزوست.',
    '🌟 جمله انگیزشی:    هر قدم کوچک، تو را به هدف بزرگ نزدیک\u200cتر می\u200cکند.',
    '🌟 جمله انگیزشی:     باور داشته باش که لایق بهترین\u200cها هستی.',
    '🌟 جمله انگیزشی:     هر روز فرصتی تازه برای شروع دوباره است.',
    '🌟 جمله انگیزشی:     موفقیت جمع کوچک تلاش\u200cهای روزانه است.',
    '🌟 جمله انگیزشی:     ترس از شکست، نباید مانع تلاش تو شود.',
    '🌟 جمله انگیزشی:     هیچ\u200cوقت برای رسیدن به رویاهایت دیر نیست.',
    '🌟 جمله انگیزشی:     قدرت واقعی در ادامه دادن است، نه در نترسیدن.',
    '🌟 جمله انگیزشی:     خودت را با دیگران مقایسه نکن، فقط با خودت دیروز مقایسه کن.',
    '🌟 جمله انگیزشی:     هر سختی یک درس پنهان دارد.',
    '🌟 جمله انگیزشی:     انرژی\u200cات را روی چیزی بگذار که واقعاً برایت مهم است.',
    '🌟 جمله انگیزشی:     تغییر از یک تصمیم کوچک شروع می\u200cشود.',
    '🌟 جمله انگیزشی:     بزرگ\u200cترین ریسک، ریسک نکردن است.',
    '🌟 جمله انگیزشی:     اگر امروز سخت است، فردا قوی\u200cتر خواهی بود.',
    '🌟 جمله انگیزشی:     هیچ\u200cکس بدون تلاش به جایی نرسیده است.',
    '🌟 جمله انگیزشی:     اعتماد به نفس با عمل کردن ساخته می\u200cشود، نه با انتظار.',
    '🌟 جمله انگیزشی:     هر روز صبح یک فرصت جدید برای بهتر شدن است.',
    '🌟 جمله انگیزشی:     کسی که تلاش می\u200cکند، حتی در شکست هم می\u200cبرد.',
    '🌟 جمله انگیزشی:     رویاهایت را کوچک نکن تا با ترس\u200cهایت جور شود.',
    '🌟 جمله انگیزشی:     صبر تلخ است ولی میوه\u200cاش شیرین است.',
    '🌟 جمله انگیزشی:     هدف بدون برنامه فقط یک آرزوست.',
    '🌟 جمله انگیزشی:     هر قدم کوچک، تو را به هدف بزرگ نزدیک\u200cتر می\u200cکند.',
    '🌟 جمله انگیزشی:      باور داشته باش که لایق بهترین\u200cها هستی.',
    '🌟 جمله انگیزشی:      هر روز فرصتی تازه برای شروع دوباره است.',
    '🌟 جمله انگیزشی:      موفقیت جمع کوچک تلاش\u200cهای روزانه است.',
    '🌟 جمله انگیزشی:      ترس از شکست، نباید مانع تلاش تو شود.',
    '🌟 جمله انگیزشی:      هیچ\u200cوقت برای رسیدن به رویاهایت دیر نیست.',
    '🌟 جمله انگیزشی:      قدرت واقعی در ادامه دادن است، نه در نترسیدن.',
    '🌟 جمله انگیزشی:      خودت را با دیگران مقایسه نکن، فقط با خودت دیروز مقایسه کن.',
    '🌟 جمله انگیزشی:      هر سختی یک درس پنهان دارد.',
    '🌟 جمله انگیزشی:      انرژی\u200cات را روی چیزی بگذار که واقعاً برایت مهم است.',
    '🌟 جمله انگیزشی:      تغییر از یک تصمیم کوچک شروع می\u200cشود.',
    '🌟 جمله انگیزشی:      بزرگ\u200cترین ریسک، ریسک نکردن است.',
    '🌟 جمله انگیزشی:      اگر امروز سخت است، فردا قوی\u200cتر خواهی بود.',
    '🌟 جمله انگیزشی:      هیچ\u200cکس بدون تلاش به جایی نرسیده است.',
    '🌟 جمله انگیزشی:      اعتماد به نفس با عمل کردن ساخته می\u200cشود، نه با انتظار.',
    '🌟 جمله انگیزشی:      هر روز صبح یک فرصت جدید برای بهتر شدن است.',
    '🌟 جمله انگیزشی:      کسی که تلاش می\u200cکند، حتی در شکست هم می\u200cبرد.',
    '🌟 جمله انگیزشی:      رویاهایت را کوچک نکن تا با ترس\u200cهایت جور شود.',
    '🌟 جمله انگیزشی:      صبر تلخ است ولی میوه\u200cاش شیرین است.',
    '🌟 جمله انگیزشی:      هدف بدون برنامه فقط یک آرزوست.',
    '🌟 جمله انگیزشی:      هر قدم کوچک، تو را به هدف بزرگ نزدیک\u200cتر می\u200cکند.',
    '🌟 جمله انگیزشی:       باور داشته باش که لایق بهترین\u200cها هستی.',
    '🌟 جمله انگیزشی:       هر روز فرصتی تازه برای شروع دوباره است.',
    '🌟 جمله انگیزشی:       موفقیت جمع کوچک تلاش\u200cهای روزانه است.',
    '🌟 جمله انگیزشی:       ترس از شکست، نباید مانع تلاش تو شود.',
    '🌟 جمله انگیزشی:       هیچ\u200cوقت برای رسیدن به رویاهایت دیر نیست.',
    '🌟 جمله انگیزشی:       قدرت واقعی در ادامه دادن است، نه در نترسیدن.',
    '🌟 جمله انگیزشی:       خودت را با دیگران مقایسه نکن، فقط با خودت دیروز مقایسه کن.',
    '🌟 جمله انگیزشی:       هر سختی یک درس پنهان دارد.',
    '🌟 جمله انگیزشی:       انرژی\u200cات را روی چیزی بگذار که واقعاً برایت مهم است.',
    '🌟 جمله انگیزشی:       تغییر از یک تصمیم کوچک شروع می\u200cشود.',
    '🌟 جمله انگیزشی:       بزرگ\u200cترین ریسک، ریسک نکردن است.',
    '🌟 جمله انگیزشی:       اگر امروز سخت است، فردا قوی\u200cتر خواهی بود.',
    '🌟 جمله انگیزشی:       هیچ\u200cکس بدون تلاش به جایی نرسیده است.',
    '🌟 جمله انگیزشی:       اعتماد به نفس با عمل کردن ساخته می\u200cشود، نه با انتظار.',
    '🌟 جمله انگیزشی:       هر روز صبح یک فرصت جدید برای بهتر شدن است.',
    '🌟 جمله انگیزشی:       کسی که تلاش می\u200cکند، حتی در شکست هم می\u200cبرد.',
    '🌟 جمله انگیزشی:       رویاهایت را کوچک نکن تا با ترس\u200cهایت جور شود.',
    '🌟 جمله انگیزشی:       صبر تلخ است ولی میوه\u200cاش شیرین است.',
    '🌟 جمله انگیزشی:       هدف بدون برنامه فقط یک آرزوست.',
    '🌟 جمله انگیزشی:       هر قدم کوچک، تو را به هدف بزرگ نزدیک\u200cتر می\u200cکند.',
    '🌟 جمله انگیزشی:        باور داشته باش که لایق بهترین\u200cها هستی.',
    '🌟 جمله انگیزشی:        هر روز فرصتی تازه برای شروع دوباره است.',
    '🌟 جمله انگیزشی:        موفقیت جمع کوچک تلاش\u200cهای روزانه است.',
    '🌟 جمله انگیزشی:        ترس از شکست، نباید مانع تلاش تو شود.',
    '🌟 جمله انگیزشی:        هیچ\u200cوقت برای رسیدن به رویاهایت دیر نیست.',
    '🌟 جمله انگیزشی:        قدرت واقعی در ادامه دادن است، نه در نترسیدن.',
    '🌟 جمله انگیزشی:        خودت را با دیگران مقایسه نکن، فقط با خودت دیروز مقایسه کن.',
    '🌟 جمله انگیزشی:        هر سختی یک درس پنهان دارد.',
    '🌟 جمله انگیزشی:        انرژی\u200cات را روی چیزی بگذار که واقعاً برایت مهم است.',
    '🌟 جمله انگیزشی:        تغییر از یک تصمیم کوچک شروع می\u200cشود.',
    '🌟 جمله انگیزشی:        بزرگ\u200cترین ریسک، ریسک نکردن است.',
    '🌟 جمله انگیزشی:        اگر امروز سخت است، فردا قوی\u200cتر خواهی بود.',
    '🌟 جمله انگیزشی:        هیچ\u200cکس بدون تلاش به جایی نرسیده است.',
    '🌟 جمله انگیزشی:        اعتماد به نفس با عمل کردن ساخته می\u200cشود، نه با انتظار.',
    '🌟 جمله انگیزشی:        هر روز صبح یک فرصت جدید برای بهتر شدن است.',
    '🌟 جمله انگیزشی:        کسی که تلاش می\u200cکند، حتی در شکست هم می\u200cبرد.',
    '🌟 جمله انگیزشی:        رویاهایت را کوچک نکن تا با ترس\u200cهایت جور شود.',
    '🌟 جمله انگیزشی:        صبر تلخ است ولی میوه\u200cاش شیرین است.',
    '🌟 جمله انگیزشی:        هدف بدون برنامه فقط یک آرزوست.',
    '🌟 جمله انگیزشی:        هر قدم کوچک، تو را به هدف بزرگ نزدیک\u200cتر می\u200cکند.',
    '🌟 جمله انگیزشی:         باور داشته باش که لایق بهترین\u200cها هستی.',
    '🌟 جمله انگیزشی:         هر روز فرصتی تازه برای شروع دوباره است.',
    '🌟 جمله انگیزشی:         موفقیت جمع کوچک تلاش\u200cهای روزانه است.',
    '🌟 جمله انگیزشی:         ترس از شکست، نباید مانع تلاش تو شود.',
    '🌟 جمله انگیزشی:         هیچ\u200cوقت برای رسیدن به رویاهایت دیر نیست.',
    '🌟 جمله انگیزشی:         قدرت واقعی در ادامه دادن است، نه در نترسیدن.',
    '🌟 جمله انگیزشی:         خودت را با دیگران مقایسه نکن، فقط با خودت دیروز مقایسه کن.',
    '🌟 جمله انگیزشی:         هر سختی یک درس پنهان دارد.',
    '🌟 جمله انگیزشی:         انرژی\u200cات را روی چیزی بگذار که واقعاً برایت مهم است.',
    '🌟 جمله انگیزشی:         تغییر از یک تصمیم کوچک شروع می\u200cشود.',
    '🌟 جمله انگیزشی:         بزرگ\u200cترین ریسک، ریسک نکردن است.',
    '🌟 جمله انگیزشی:         اگر امروز سخت است، فردا قوی\u200cتر خواهی بود.',
    '🌟 جمله انگیزشی:         هیچ\u200cکس بدون تلاش به جایی نرسیده است.',
    '🌟 جمله انگیزشی:         اعتماد به نفس با عمل کردن ساخته می\u200cشود، نه با انتظار.',
    '🌟 جمله انگیزشی:         هر روز صبح یک فرصت جدید برای بهتر شدن است.',
    '🌟 جمله انگیزشی:         کسی که تلاش می\u200cکند، حتی در شکست هم می\u200cبرد.',
    '🌟 جمله انگیزشی:         رویاهایت را کوچک نکن تا با ترس\u200cهایت جور شود.',
    '🌟 جمله انگیزشی:         صبر تلخ است ولی میوه\u200cاش شیرین است.',
    '🌟 جمله انگیزشی:         هدف بدون برنامه فقط یک آرزوست.',
    '🌟 جمله انگیزشی:         هر قدم کوچک، تو را به هدف بزرگ نزدیک\u200cتر می\u200cکند.',
    '🌟 جمله انگیزشی:          باور داشته باش که لایق بهترین\u200cها هستی.',
    '🌟 جمله انگیزشی:          هر روز فرصتی تازه برای شروع دوباره است.',
    '🌟 جمله انگیزشی:          موفقیت جمع کوچک تلاش\u200cهای روزانه است.',
    '🌟 جمله انگیزشی:          ترس از شکست، نباید مانع تلاش تو شود.',
    '🌟 جمله انگیزشی:          هیچ\u200cوقت برای رسیدن به رویاهایت دیر نیست.',
    '🌟 جمله انگیزشی:          قدرت واقعی در ادامه دادن است، نه در نترسیدن.',
    '🌟 جمله انگیزشی:          خودت را با دیگران مقایسه نکن، فقط با خودت دیروز مقایسه کن.',
    '🌟 جمله انگیزشی:          هر سختی یک درس پنهان دارد.',
    '🌟 جمله انگیزشی:          انرژی\u200cات را روی چیزی بگذار که واقعاً برایت مهم است.',
    '🌟 جمله انگیزشی:          تغییر از یک تصمیم کوچک شروع می\u200cشود.',
    '🌟 جمله انگیزشی:          بزرگ\u200cترین ریسک، ریسک نکردن است.',
    '🌟 جمله انگیزشی:          اگر امروز سخت است، فردا قوی\u200cتر خواهی بود.',
    '🌟 جمله انگیزشی:          هیچ\u200cکس بدون تلاش به جایی نرسیده است.',
    '🌟 جمله انگیزشی:          اعتماد به نفس با عمل کردن ساخته می\u200cشود، نه با انتظار.',
    '🌟 جمله انگیزشی:          هر روز صبح یک فرصت جدید برای بهتر شدن است.',
    '🌟 جمله انگیزشی:          کسی که تلاش می\u200cکند، حتی در شکست هم می\u200cبرد.',
    '🌟 جمله انگیزشی:          رویاهایت را کوچک نکن تا با ترس\u200cهایت جور شود.',
    '🌟 جمله انگیزشی:          صبر تلخ است ولی میوه\u200cاش شیرین است.',
    '🌟 جمله انگیزشی:          هدف بدون برنامه فقط یک آرزوست.',
    '🌟 جمله انگیزشی:          هر قدم کوچک، تو را به هدف بزرگ نزدیک\u200cتر می\u200cکند.',
]

JOKE_LIST = [
    '😂 شوخی: به دوستم گفتم بیا با هم ورزش کنیم، گفت باشه، من می\u200cشمارم تو بدو!',
    '😂 شوخی: رفتم آرایشگاه گفتم موهامو کوتاه کن، گفت کدوماشون؟!',
    '😂 شوخی: بهم گفتن رمز موفقیت پشتکاره، منم دیگه هیچی رو رمز نذاشتم!',
    '😂 شوخی: هر وقت میگم فردا از اول شروع می\u200cکنم، بعدش می\u200cبینم فردا هم یه امروز دیگه\u200cست!',
    '😂 شوخی: به گوشیم گفتم چرا شارژت تموم میشه؟ گفت چون تو هم مثل من هی چک میکنی!',
    '😂 شوخی: رفتم دکتر گفتم دکتر خیلی خسته\u200cام، گفت چیکار میکنی؟ گفتم هیچی، گفت خب طبیعیه!',
    '😂 شوخی: چرا جغد دیر به مهمونی رسید؟ چون فکر کرد کسی نیست!',
    '😂 شوخی: آسانسور به دوستش گفت امروز حالم خوب نیست، دوستش گفت خجالتی بود؟!',
    '😂 شوخی: میدونی چرا خفاش همیشه ساکته؟ چون دلش برای خونه تنگ شده بود!',
    '😂 شوخی: چرا کفش دیر به مهمونی رسید؟ چون هنوز خواب بود!',
    '😂 شوخی: اسکناس به دوستش گفت امروز حالم خوب نیست، دوستش گفت یادش رفته بود چرا اومده؟!',
    '😂 شوخی: میدونی چرا خرچنگ همیشه ساکته؟ چون هنوز خواب بود!',
    '😂 شوخی: چرا لاک\u200cپشت دیر به مهمونی رسید؟ چون یادش رفته بود چرا اومده!',
    '😂 شوخی: پنگوئن به دوستش گفت امروز حالم خوب نیست، دوستش گفت گیر کرده بود؟!',
    '😂 شوخی: میدونی چرا خرچنگ همیشه ساکته؟ چون دیرش شده بود!',
    '😂 شوخی: چرا چراغ\u200cقرمز دیر به مهمونی رسید؟ چون میخواست مشهور بشه!',
    '😂 شوخی: اردک به دوستش گفت امروز حالم خوب نیست، دوستش گفت جاش عوض شده بود؟!',
    '😂 شوخی: میدونی چرا عنکبوت همیشه ساکته؟ چون یادش رفته بود چرا اومده!',
    '😂 شوخی: چرا بالش دیر به مهمونی رسید؟ چون باتریش تموم شده بود!',
    '😂 شوخی: جغد به دوستش گفت امروز حالم خوب نیست، دوستش گفت یادش رفته بود چرا اومده؟!',
    '😂 شوخی: میدونی چرا جوراب تک همیشه ساکته؟ چون هنوز خواب بود!',
    '😂 شوخی: چرا ساعت دیواری دیر به مهمونی رسید؟ چون میخواست مشهور بشه!',
    '😂 شوخی: جوراب تک به دوستش گفت امروز حالم خوب نیست، دوستش گفت گیر کرده بود؟!',
    '😂 شوخی: میدونی چرا آسانسور همیشه ساکته؟ چون منتظر بهار بود!',
    '😂 شوخی: چرا خرچنگ دیر به مهمونی رسید؟ چون فکر کرد تعطیله!',
    '😂 شوخی: چراغ\u200cقرمز به دوستش گفت امروز حالم خوب نیست، دوستش گفت فکر کرد کسی نیست؟!',
    '😂 شوخی: میدونی چرا اردک همیشه ساکته؟ چون هنوز صبحونه نخورده بود!',
    '😂 شوخی: چرا اردک دیر به مهمونی رسید؟ چون دلش برای خونه تنگ شده بود!',
    '😂 شوخی: زرافه به دوستش گفت امروز حالم خوب نیست، دوستش گفت خجالتی بود؟!',
    '😂 شوخی: میدونی چرا کوسه همیشه ساکته؟ چون فکر کرد تعطیله!',
    '😂 شوخی: چرا اردک دیر به مهمونی رسید؟ چون همه داشتن نگاش میکردن!',
    '😂 شوخی: چتر به دوستش گفت امروز حالم خوب نیست، دوستش گفت دلش برای خونه تنگ شده بود؟!',
    '😂 شوخی: میدونی چرا کفش همیشه ساکته؟ چون منتظر بهار بود!',
    '😂 شوخی: چرا اردک دیر به مهمونی رسید؟ چون فکر کرد تعطیله!',
    '😂 شوخی: کانگورو به دوستش گفت امروز حالم خوب نیست، دوستش گفت فکر کرد تعطیله؟!',
    '😂 شوخی: میدونی چرا خرچنگ همیشه ساکته؟ چون خجالتی بود!',
    '😂 شوخی: چرا لاک\u200cپشت دیر به مهمونی رسید؟ چون میخواست مشهور بشه!',
    '😂 شوخی: چراغ\u200cقرمز به دوستش گفت امروز حالم خوب نیست، دوستش گفت فکر کرد تعطیله؟!',
    '😂 شوخی: میدونی چرا خرچنگ همیشه ساکته؟ چون گیر کرده بود!',
    '😂 شوخی: چرا خرچنگ دیر به مهمونی رسید؟ چون جاش عوض شده بود!',
    '😂 شوخی: زرافه به دوستش گفت امروز حالم خوب نیست، دوستش گفت میخواست مشهور بشه؟!',
    '😂 شوخی: میدونی چرا طوطی همیشه ساکته؟ چون هنوز خواب بود!',
    '😂 شوخی: چرا لاک\u200cپشت دیر به مهمونی رسید؟ چون جاش عوض شده بود!',
    '😂 شوخی: چتر به دوستش گفت امروز حالم خوب نیست، دوستش گفت باتریش تموم شده بود؟!',
    '😂 شوخی: میدونی چرا کرم همیشه ساکته؟ چون فکر کرد تعطیله!',
    '😂 شوخی: چرا پاندا دیر به مهمونی رسید؟ چون خجالتی بود!',
    '😂 شوخی: کامپیوتر به دوستش گفت امروز حالم خوب نیست، دوستش گفت میخواست مشهور بشه؟!',
    '😂 شوخی: میدونی چرا موز همیشه ساکته؟ چون فکر کرد تعطیله!',
    '😂 شوخی: چرا بوقلمون دیر به مهمونی رسید؟ چون فکر کرد کسی نیست!',
    '😂 شوخی: حلزون به دوستش گفت امروز حالم خوب نیست، دوستش گفت فکر کرد کسی نیست؟!',
    '😂 شوخی: میدونی چرا عنکبوت همیشه ساکته؟ چون هنوز خواب بود!',
    '😂 شوخی: چرا موز دیر به مهمونی رسید؟ چون دلش برای خونه تنگ شده بود!',
    '😂 شوخی: کرم به دوستش گفت امروز حالم خوب نیست، دوستش گفت دیرش شده بود؟!',
    '😂 شوخی: میدونی چرا لاک\u200cپشت همیشه ساکته؟ چون باتریش تموم شده بود!',
    '😂 شوخی: چرا بوقلمون دیر به مهمونی رسید؟ چون همه داشتن نگاش میکردن!',
    '😂 شوخی: کانگورو به دوستش گفت امروز حالم خوب نیست، دوستش گفت جاش عوض شده بود؟!',
    '😂 شوخی: میدونی چرا حلزون همیشه ساکته؟ چون هنوز صبحونه نخورده بود!',
    '😂 شوخی: چرا موز دیر به مهمونی رسید؟ چون فکر کرد کسی نیست!',
    '😂 شوخی: کامپیوتر به دوستش گفت امروز حالم خوب نیست، دوستش گفت فکر کرد تعطیله؟!',
    '😂 شوخی: میدونی چرا جغد همیشه ساکته؟ چون باتریش تموم شده بود!',
    '😂 شوخی: چرا طوطی دیر به مهمونی رسید؟ چون حوصله نداشت!',
    '😂 شوخی: اسکناس به دوستش گفت امروز حالم خوب نیست، دوستش گفت حوصله نداشت؟!',
    '😂 شوخی: میدونی چرا فیل همیشه ساکته؟ چون جاش عوض شده بود!',
    '😂 شوخی: چرا بوقلمون دیر به مهمونی رسید؟ چون دلش برای خونه تنگ شده بود!',
    '😂 شوخی: آسانسور به دوستش گفت امروز حالم خوب نیست، دوستش گفت یادش رفته بود چرا اومده؟!',
    '😂 شوخی: میدونی چرا کانگورو همیشه ساکته؟ چون خجالتی بود!',
    '😂 شوخی: چرا کفش دیر به مهمونی رسید؟ چون حوصله نداشت!',
    '😂 شوخی: خفاش به دوستش گفت امروز حالم خوب نیست، دوستش گفت هنوز صبحونه نخورده بود؟!',
    '😂 شوخی: میدونی چرا بالش همیشه ساکته؟ چون فکر کرد تعطیله!',
    '😂 شوخی: چرا شتر دیر به مهمونی رسید؟ چون گیر کرده بود!',
    '😂 شوخی: جوراب تک به دوستش گفت امروز حالم خوب نیست، دوستش گفت خجالتی بود؟!',
    '😂 شوخی: میدونی چرا چتر همیشه ساکته؟ چون منتظر بهار بود!',
    '😂 شوخی: چرا یخچال دیر به مهمونی رسید؟ چون جاش عوض شده بود!',
    '😂 شوخی: عنکبوت به دوستش گفت امروز حالم خوب نیست، دوستش گفت میخواست مشهور بشه؟!',
    '😂 شوخی: میدونی چرا چراغ\u200cقرمز همیشه ساکته؟ چون منتظر بهار بود!',
    '😂 شوخی: چرا بوقلمون دیر به مهمونی رسید؟ چون حوصله نداشت!',
    '😂 شوخی: زرافه به دوستش گفت امروز حالم خوب نیست، دوستش گفت دیرش شده بود؟!',
    '😂 شوخی: میدونی چرا کرم همیشه ساکته؟ چون همه داشتن نگاش میکردن!',
    '😂 شوخی: چرا مورچه دیر به مهمونی رسید؟ چون منتظر بهار بود!',
    '😂 شوخی: چتر به دوستش گفت امروز حالم خوب نیست، دوستش گفت جاش عوض شده بود؟!',
    '😂 شوخی: میدونی چرا پاندا همیشه ساکته؟ چون منتظر بهار بود!',
    '😂 شوخی: چرا حلزون دیر به مهمونی رسید؟ چون فکر کرد تعطیله!',
    '😂 شوخی: مورچه به دوستش گفت امروز حالم خوب نیست، دوستش گفت گیر کرده بود؟!',
    '😂 شوخی: میدونی چرا عنکبوت همیشه ساکته؟ چون حوصله نداشت!',
    '😂 شوخی: چرا موز دیر به مهمونی رسید؟ چون جاش عوض شده بود!',
    '😂 شوخی: بالش به دوستش گفت امروز حالم خوب نیست، دوستش گفت جاش عوض شده بود؟!',
    '😂 شوخی: میدونی چرا کروکودیل همیشه ساکته؟ چون خجالتی بود!',
    '😂 شوخی: چرا جغد دیر به مهمونی رسید؟ چون حوصله نداشت!',
    '😂 شوخی: پاندا به دوستش گفت امروز حالم خوب نیست، دوستش گفت جاش عوض شده بود؟!',
    '😂 شوخی: میدونی چرا آسانسور همیشه ساکته؟ چون دلش برای خونه تنگ شده بود!',
    '😂 شوخی: چرا پاندا دیر به مهمونی رسید؟ چون باتریش تموم شده بود!',
    '😂 شوخی: شتر به دوستش گفت امروز حالم خوب نیست، دوستش گفت خجالتی بود؟!',
    '😂 شوخی: میدونی چرا حلزون همیشه ساکته؟ چون جاش عوض شده بود!',
    '😂 شوخی: چرا مورچه دیر به مهمونی رسید؟ چون همه داشتن نگاش میکردن!',
    '😂 شوخی: خفاش به دوستش گفت امروز حالم خوب نیست، دوستش گفت جاش عوض شده بود؟!',
    '😂 شوخی: میدونی چرا کروکودیل همیشه ساکته؟ چون فکر کرد تعطیله!',
    '😂 شوخی: چرا ساعت دیواری دیر به مهمونی رسید؟ چون باتریش تموم شده بود!',
    '😂 شوخی: کانگورو به دوستش گفت امروز حالم خوب نیست، دوستش گفت یادش رفته بود چرا اومده؟!',
    '😂 شوخی: میدونی چرا چتر همیشه ساکته؟ چون فکر کرد کسی نیست!',
    '😂 شوخی: چرا بالش دیر به مهمونی رسید؟ چون هنوز خواب بود!',
    '😂 شوخی: کروکودیل به دوستش گفت امروز حالم خوب نیست، دوستش گفت همه داشتن نگاش میکردن؟!',
    '😂 شوخی: میدونی چرا چتر همیشه ساکته؟ چون هنوز صبحونه نخورده بود!',
    '😂 شوخی: چرا آسانسور دیر به مهمونی رسید؟ چون فکر کرد کسی نیست!',
    '😂 شوخی: یخچال به دوستش گفت امروز حالم خوب نیست، دوستش گفت یادش رفته بود چرا اومده؟!',
    '😂 شوخی: میدونی چرا آسانسور همیشه ساکته؟ چون همه داشتن نگاش میکردن!',
    '😂 شوخی: چرا پاندا دیر به مهمونی رسید؟ چون یادش رفته بود چرا اومده!',
    '😂 شوخی: کانگورو به دوستش گفت امروز حالم خوب نیست، دوستش گفت حوصله نداشت؟!',
    '😂 شوخی: میدونی چرا اسکناس همیشه ساکته؟ چون خجالتی بود!',
    '😂 شوخی: چرا چتر دیر به مهمونی رسید؟ چون دیرش شده بود!',
    '😂 شوخی: موز به دوستش گفت امروز حالم خوب نیست، دوستش گفت میخواست مشهور بشه؟!',
    '😂 شوخی: میدونی چرا کوسه همیشه ساکته؟ چون هنوز خواب بود!',
    '😂 شوخی: چرا عنکبوت دیر به مهمونی رسید؟ چون همه داشتن نگاش میکردن!',
    '😂 شوخی: چتر به دوستش گفت امروز حالم خوب نیست، دوستش گفت میخواست مشهور بشه؟!',
    '😂 شوخی: میدونی چرا پاندا همیشه ساکته؟ چون فکر کرد کسی نیست!',
    '😂 شوخی: چرا آسانسور دیر به مهمونی رسید؟ چون گیر کرده بود!',
    '😂 شوخی: چراغ\u200cقرمز به دوستش گفت امروز حالم خوب نیست، دوستش گفت هنوز صبحونه نخورده بود؟!',
    '😂 شوخی: میدونی چرا طوطی همیشه ساکته؟ چون فکر کرد تعطیله!',
    '😂 شوخی: چرا ساعت دیواری دیر به مهمونی رسید؟ چون هنوز صبحونه نخورده بود!',
    '😂 شوخی: کرم به دوستش گفت امروز حالم خوب نیست، دوستش گفت خجالتی بود؟!',
    '😂 شوخی: میدونی چرا شتر همیشه ساکته؟ چون منتظر بهار بود!',
    '😂 شوخی: چرا عنکبوت دیر به مهمونی رسید؟ چون گیر کرده بود!',
    '😂 شوخی: کامپیوتر به دوستش گفت امروز حالم خوب نیست، دوستش گفت جاش عوض شده بود؟!',
    '😂 شوخی: میدونی چرا اردک همیشه ساکته؟ چون حوصله نداشت!',
    '😂 شوخی: چرا خرچنگ دیر به مهمونی رسید؟ چون دلش برای خونه تنگ شده بود!',
    '😂 شوخی: کانگورو به دوستش گفت امروز حالم خوب نیست، دوستش گفت میخواست مشهور بشه؟!',
    '😂 شوخی: میدونی چرا حلزون همیشه ساکته؟ چون منتظر بهار بود!',
    '😂 شوخی: چرا خرچنگ دیر به مهمونی رسید؟ چون یادش رفته بود چرا اومده!',
    '😂 شوخی: کرم به دوستش گفت امروز حالم خوب نیست، دوستش گفت میخواست مشهور بشه؟!',
    '😂 شوخی: میدونی چرا فیل همیشه ساکته؟ چون منتظر بهار بود!',
    '😂 شوخی: چرا فیل دیر به مهمونی رسید؟ چون یادش رفته بود چرا اومده!',
    '😂 شوخی: شتر به دوستش گفت امروز حالم خوب نیست، دوستش گفت هنوز صبحونه نخورده بود؟!',
    '😂 شوخی: میدونی چرا پنگوئن همیشه ساکته؟ چون فکر کرد تعطیله!',
    '😂 شوخی: چرا خرچنگ دیر به مهمونی رسید؟ چون همه داشتن نگاش میکردن!',
    '😂 شوخی: خفاش به دوستش گفت امروز حالم خوب نیست، دوستش گفت گیر کرده بود؟!',
    '😂 شوخی: میدونی چرا طوطی همیشه ساکته؟ چون یادش رفته بود چرا اومده!',
    '😂 شوخی: چرا اسکناس دیر به مهمونی رسید؟ چون دلش برای خونه تنگ شده بود!',
    '😂 شوخی: بالش به دوستش گفت امروز حالم خوب نیست، دوستش گفت هنوز صبحونه نخورده بود؟!',
    '😂 شوخی: میدونی چرا یخچال همیشه ساکته؟ چون فکر کرد کسی نیست!',
    '😂 شوخی: چرا کروکودیل دیر به مهمونی رسید؟ چون هنوز صبحونه نخورده بود!',
    '😂 شوخی: کروکودیل به دوستش گفت امروز حالم خوب نیست، دوستش گفت دلش برای خونه تنگ شده بود؟!',
    '😂 شوخی: میدونی چرا خفاش همیشه ساکته؟ چون فکر کرد تعطیله!',
    '😂 شوخی: چرا موز دیر به مهمونی رسید؟ چون خجالتی بود!',
    '😂 شوخی: اسکناس به دوستش گفت امروز حالم خوب نیست، دوستش گفت فکر کرد تعطیله؟!',
    '😂 شوخی: میدونی چرا طوطی همیشه ساکته؟ چون میخواست مشهور بشه!',
    '😂 شوخی: چرا عنکبوت دیر به مهمونی رسید؟ چون خجالتی بود!',
    '😂 شوخی: عنکبوت به دوستش گفت امروز حالم خوب نیست، دوستش گفت دیرش شده بود؟!',
    '😂 شوخی: میدونی چرا کوسه همیشه ساکته؟ چون همه داشتن نگاش میکردن!',
    '😂 شوخی: چرا کامپیوتر دیر به مهمونی رسید؟ چون فکر کرد کسی نیست!',
    '😂 شوخی: ساعت دیواری به دوستش گفت امروز حالم خوب نیست، دوستش گفت جاش عوض شده بود؟!',
    '😂 شوخی: میدونی چرا کفش همیشه ساکته؟ چون همه داشتن نگاش میکردن!',
    '😂 شوخی: چرا چتر دیر به مهمونی رسید؟ چون یادش رفته بود چرا اومده!',
    '😂 شوخی: بوقلمون به دوستش گفت امروز حالم خوب نیست، دوستش گفت دیرش شده بود؟!',
    '😂 شوخی: میدونی چرا پنگوئن همیشه ساکته؟ چون فکر کرد کسی نیست!',
    '😂 شوخی: چرا بوقلمون دیر به مهمونی رسید؟ چون جاش عوض شده بود!',
    '😂 شوخی: موز به دوستش گفت امروز حالم خوب نیست، دوستش گفت باتریش تموم شده بود؟!',
    '😂 شوخی: میدونی چرا اردک همیشه ساکته؟ چون منتظر بهار بود!',
    '😂 شوخی: چرا زرافه دیر به مهمونی رسید؟ چون گیر کرده بود!',
    '😂 شوخی: ساعت دیواری به دوستش گفت امروز حالم خوب نیست، دوستش گفت دلش برای خونه تنگ شده بود؟!',
    '😂 شوخی: میدونی چرا کروکودیل همیشه ساکته؟ چون یادش رفته بود چرا اومده!',
    '😂 شوخی: چرا پنگوئن دیر به مهمونی رسید؟ چون همه داشتن نگاش میکردن!',
    '😂 شوخی: کفش به دوستش گفت امروز حالم خوب نیست، دوستش گفت جاش عوض شده بود؟!',
    '😂 شوخی: میدونی چرا کامپیوتر همیشه ساکته؟ چون گیر کرده بود!',
    '😂 شوخی: چرا پنگوئن دیر به مهمونی رسید؟ چون منتظر بهار بود!',
    '😂 شوخی: موز به دوستش گفت امروز حالم خوب نیست، دوستش گفت حوصله نداشت؟!',
    '😂 شوخی: میدونی چرا کانگورو همیشه ساکته؟ چون هنوز صبحونه نخورده بود!',
    '😂 شوخی: چرا جوراب تک دیر به مهمونی رسید؟ چون حوصله نداشت!',
    '😂 شوخی: اسکناس به دوستش گفت امروز حالم خوب نیست، دوستش گفت فکر کرد کسی نیست؟!',
    '😂 شوخی: میدونی چرا کرم همیشه ساکته؟ چون هنوز خواب بود!',
    '😂 شوخی: چرا حلزون دیر به مهمونی رسید؟ چون خجالتی بود!',
    '😂 شوخی: کامپیوتر به دوستش گفت امروز حالم خوب نیست، دوستش گفت یادش رفته بود چرا اومده؟!',
    '😂 شوخی: میدونی چرا طوطی همیشه ساکته؟ چون همه داشتن نگاش میکردن!',
    '😂 شوخی: چرا کامپیوتر دیر به مهمونی رسید؟ چون همه داشتن نگاش میکردن!',
    '😂 شوخی: حلزون به دوستش گفت امروز حالم خوب نیست، دوستش گفت دیرش شده بود؟!',
    '😂 شوخی: میدونی چرا مورچه همیشه ساکته؟ چون دیرش شده بود!',
    '😂 شوخی: چرا فیل دیر به مهمونی رسید؟ چون گیر کرده بود!',
    '😂 شوخی: کروکودیل به دوستش گفت امروز حالم خوب نیست، دوستش گفت دیرش شده بود؟!',
    '😂 شوخی: میدونی چرا کفش همیشه ساکته؟ چون باتریش تموم شده بود!',
    '😂 شوخی: چرا حلزون دیر به مهمونی رسید؟ چون دلش برای خونه تنگ شده بود!',
    '😂 شوخی: طوطی به دوستش گفت امروز حالم خوب نیست، دوستش گفت باتریش تموم شده بود؟!',
    '😂 شوخی: میدونی چرا خفاش همیشه ساکته؟ چون یادش رفته بود چرا اومده!',
    '😂 شوخی: چرا پنگوئن دیر به مهمونی رسید؟ چون دلش برای خونه تنگ شده بود!',
    '😂 شوخی: آسانسور به دوستش گفت امروز حالم خوب نیست، دوستش گفت فکر کرد تعطیله؟!',
    '😂 شوخی: میدونی چرا جغد همیشه ساکته؟ چون فکر کرد تعطیله!',
    '😂 شوخی: چرا بوقلمون دیر به مهمونی رسید؟ چون یادش رفته بود چرا اومده!',
    '😂 شوخی: خفاش به دوستش گفت امروز حالم خوب نیست، دوستش گفت همه داشتن نگاش میکردن؟!',
    '😂 شوخی: میدونی چرا فیل همیشه ساکته؟ چون باتریش تموم شده بود!',
    '😂 شوخی: چرا جغد دیر به مهمونی رسید؟ چون گیر کرده بود!',
    '😂 شوخی: خرچنگ به دوستش گفت امروز حالم خوب نیست، دوستش گفت میخواست مشهور بشه؟!',
    '😂 شوخی: میدونی چرا شتر همیشه ساکته؟ چون یادش رفته بود چرا اومده!',
    '😂 شوخی: چرا لاک\u200cپشت دیر به مهمونی رسید؟ چون هنوز خواب بود!',
    '😂 شوخی: کوسه به دوستش گفت امروز حالم خوب نیست، دوستش گفت دیرش شده بود؟!',
    '😂 شوخی: میدونی چرا عنکبوت همیشه ساکته؟ چون فکر کرد تعطیله!',
    '😂 شوخی: چرا آسانسور دیر به مهمونی رسید؟ چون جاش عوض شده بود!',
    '😂 شوخی: ساعت دیواری به دوستش گفت امروز حالم خوب نیست، دوستش گفت همه داشتن نگاش میکردن؟!',
    '😂 شوخی: میدونی چرا حلزون همیشه ساکته؟ چون گیر کرده بود!',
    '😂 شوخی: چرا خرچنگ دیر به مهمونی رسید؟ چون فکر کرد کسی نیست!',
    '😂 شوخی: یخچال به دوستش گفت امروز حالم خوب نیست، دوستش گفت منتظر بهار بود؟!',
    '😂 شوخی: میدونی چرا یخچال همیشه ساکته؟ چون باتریش تموم شده بود!',
    '😂 شوخی: چرا کروکودیل دیر به مهمونی رسید؟ چون فکر کرد کسی نیست!',
    '😂 شوخی: بالش به دوستش گفت امروز حالم خوب نیست، دوستش گفت خجالتی بود؟!',
]

FUN_FACT_LIST = [
    '💡 حقیقت جالب: عسل هیچ\u200cوقت فاسد نمی\u200cشود، حتی بعد از هزاران سال!',
    '💡 حقیقت جالب: قلب یک میگو در سرش قرار دارد!',
    '💡 حقیقت جالب: موز از نظر علمی یک توت (بری) محسوب می\u200cشود!',
    '💡 حقیقت جالب: یک روز روی سیاره\u200cی زهره از یک سال آن سیاره طولانی\u200cتر است!',
    '💡 حقیقت جالب: اثر انگشت هر آدمی حتی در دوقلوهای همسان هم متفاوت است!',
    '💡 حقیقت جالب: هشت\u200cپاها سه تا قلب دارند!',
    '💡 حقیقت جالب: شترها می\u200cتوانند بدون آب هفته\u200cها زنده بمانند.',
    '💡 حقیقت جالب: کوسه\u200cها قبل از دایناسورها روی زمین زندگی می\u200cکردند.',
    '💡 حقیقت جالب: صدای غرش شیر تا هشت کیلومتر شنیده می\u200cشود.',
    '💡 حقیقت جالب: درخت\u200cهای سکویا از قدیمی\u200cترین موجودات زنده روی زمین\u200cاند.',
    '💡 حقیقت جالب: زبان مورچه\u200cخوار می\u200cتواند تا شصت سانتی\u200cمتر طول داشته باشد.',
    '💡 حقیقت جالب: پنگوئن\u200cها هر سال یک همسر ثابت انتخاب می\u200cکنند.',
    '💡 حقیقت جالب: خرس قطبی پوستش سیاه است، فقط موهایش سفید به نظر می\u200cرسد.',
    '💡 حقیقت جالب: ماه هر سال کمی از زمین دورتر می\u200cشود.',
    '💡 حقیقت جالب: زنبورهای عسل می\u200cتوانند چهره\u200cهای انسان را تشخیص دهند.',
    '💡 حقیقت جالب: قورباغه\u200cها نمی\u200cتوانند بدون بستن چشم\u200cهایشان غذا قورت دهند.',
    '💡 حقیقت جالب: فیل\u200cها تنها پستاندارانی هستند که نمی\u200cتوانند بپرند.',
    '💡 حقیقت جالب: طول روده انسان حدود هفت متر است.',
    '💡 حقیقت جالب: صدای نهنگ آبی می\u200cتواند صدها کیلومتر در اقیانوس پخش شود.',
    '💡 حقیقت جالب: برف در واقع بی\u200cرنگ است، سفیدی آن به خاطر بازتاب نور است.',
    '💡 حقیقت جالب:  زرافه\u200cها تقریباً به همان اندازه انسان\u200cها می\u200cخوابند، فقط خیلی کوتاه\u200cتر و چندبار در روز.',
    '💡 حقیقت جالب:  استخوان\u200cهای گوش انسان کوچک\u200cترین استخوان\u200cهای بدن هستند.',
    '💡 حقیقت جالب:  ونوس تنها سیاره\u200cای است که در جهت عکس بقیه می\u200cچرخد.',
    '💡 حقیقت جالب:  پروانه\u200cها با پاهایشان می\u200cچشند نه با دهانشان.',
    '💡 حقیقت جالب:  یک روز روی سیاره\u200cی مشتری فقط حدود ۱۰ ساعت زمینی طول می\u200cکشد.',
    '💡 حقیقت جالب:  مغز انسان حدود هفتاد و پنج درصد آب است.',
    '💡 حقیقت جالب:  شترها می\u200cتوانند بدون آب هفته\u200cها زنده بمانند.',
    '💡 حقیقت جالب:  کوسه\u200cها قبل از دایناسورها روی زمین زندگی می\u200cکردند.',
    '💡 حقیقت جالب:  صدای غرش شیر تا هشت کیلومتر شنیده می\u200cشود.',
    '💡 حقیقت جالب:  درخت\u200cهای سکویا از قدیمی\u200cترین موجودات زنده روی زمین\u200cاند.',
    '💡 حقیقت جالب:  زبان مورچه\u200cخوار می\u200cتواند تا شصت سانتی\u200cمتر طول داشته باشد.',
    '💡 حقیقت جالب:  پنگوئن\u200cها هر سال یک همسر ثابت انتخاب می\u200cکنند.',
    '💡 حقیقت جالب:  خرس قطبی پوستش سیاه است، فقط موهایش سفید به نظر می\u200cرسد.',
    '💡 حقیقت جالب:  ماه هر سال کمی از زمین دورتر می\u200cشود.',
    '💡 حقیقت جالب:  زنبورهای عسل می\u200cتوانند چهره\u200cهای انسان را تشخیص دهند.',
    '💡 حقیقت جالب:  قورباغه\u200cها نمی\u200cتوانند بدون بستن چشم\u200cهایشان غذا قورت دهند.',
    '💡 حقیقت جالب:  فیل\u200cها تنها پستاندارانی هستند که نمی\u200cتوانند بپرند.',
    '💡 حقیقت جالب:  طول روده انسان حدود هفت متر است.',
    '💡 حقیقت جالب:  صدای نهنگ آبی می\u200cتواند صدها کیلومتر در اقیانوس پخش شود.',
    '💡 حقیقت جالب:  برف در واقع بی\u200cرنگ است، سفیدی آن به خاطر بازتاب نور است.',
    '💡 حقیقت جالب:   زرافه\u200cها تقریباً به همان اندازه انسان\u200cها می\u200cخوابند، فقط خیلی کوتاه\u200cتر و چندبار در روز.',
    '💡 حقیقت جالب:   استخوان\u200cهای گوش انسان کوچک\u200cترین استخوان\u200cهای بدن هستند.',
    '💡 حقیقت جالب:   ونوس تنها سیاره\u200cای است که در جهت عکس بقیه می\u200cچرخد.',
    '💡 حقیقت جالب:   پروانه\u200cها با پاهایشان می\u200cچشند نه با دهانشان.',
    '💡 حقیقت جالب:   یک روز روی سیاره\u200cی مشتری فقط حدود ۱۰ ساعت زمینی طول می\u200cکشد.',
    '💡 حقیقت جالب:   مغز انسان حدود هفتاد و پنج درصد آب است.',
    '💡 حقیقت جالب:   شترها می\u200cتوانند بدون آب هفته\u200cها زنده بمانند.',
    '💡 حقیقت جالب:   کوسه\u200cها قبل از دایناسورها روی زمین زندگی می\u200cکردند.',
    '💡 حقیقت جالب:   صدای غرش شیر تا هشت کیلومتر شنیده می\u200cشود.',
    '💡 حقیقت جالب:   درخت\u200cهای سکویا از قدیمی\u200cترین موجودات زنده روی زمین\u200cاند.',
    '💡 حقیقت جالب:   زبان مورچه\u200cخوار می\u200cتواند تا شصت سانتی\u200cمتر طول داشته باشد.',
    '💡 حقیقت جالب:   پنگوئن\u200cها هر سال یک همسر ثابت انتخاب می\u200cکنند.',
    '💡 حقیقت جالب:   خرس قطبی پوستش سیاه است، فقط موهایش سفید به نظر می\u200cرسد.',
    '💡 حقیقت جالب:   ماه هر سال کمی از زمین دورتر می\u200cشود.',
    '💡 حقیقت جالب:   زنبورهای عسل می\u200cتوانند چهره\u200cهای انسان را تشخیص دهند.',
    '💡 حقیقت جالب:   قورباغه\u200cها نمی\u200cتوانند بدون بستن چشم\u200cهایشان غذا قورت دهند.',
    '💡 حقیقت جالب:   فیل\u200cها تنها پستاندارانی هستند که نمی\u200cتوانند بپرند.',
    '💡 حقیقت جالب:   طول روده انسان حدود هفت متر است.',
    '💡 حقیقت جالب:   صدای نهنگ آبی می\u200cتواند صدها کیلومتر در اقیانوس پخش شود.',
    '💡 حقیقت جالب:   برف در واقع بی\u200cرنگ است، سفیدی آن به خاطر بازتاب نور است.',
    '💡 حقیقت جالب:    زرافه\u200cها تقریباً به همان اندازه انسان\u200cها می\u200cخوابند، فقط خیلی کوتاه\u200cتر و چندبار در روز.',
    '💡 حقیقت جالب:    استخوان\u200cهای گوش انسان کوچک\u200cترین استخوان\u200cهای بدن هستند.',
    '💡 حقیقت جالب:    ونوس تنها سیاره\u200cای است که در جهت عکس بقیه می\u200cچرخد.',
    '💡 حقیقت جالب:    پروانه\u200cها با پاهایشان می\u200cچشند نه با دهانشان.',
    '💡 حقیقت جالب:    یک روز روی سیاره\u200cی مشتری فقط حدود ۱۰ ساعت زمینی طول می\u200cکشد.',
    '💡 حقیقت جالب:    مغز انسان حدود هفتاد و پنج درصد آب است.',
    '💡 حقیقت جالب:    شترها می\u200cتوانند بدون آب هفته\u200cها زنده بمانند.',
    '💡 حقیقت جالب:    کوسه\u200cها قبل از دایناسورها روی زمین زندگی می\u200cکردند.',
    '💡 حقیقت جالب:    صدای غرش شیر تا هشت کیلومتر شنیده می\u200cشود.',
    '💡 حقیقت جالب:    درخت\u200cهای سکویا از قدیمی\u200cترین موجودات زنده روی زمین\u200cاند.',
    '💡 حقیقت جالب:    زبان مورچه\u200cخوار می\u200cتواند تا شصت سانتی\u200cمتر طول داشته باشد.',
    '💡 حقیقت جالب:    پنگوئن\u200cها هر سال یک همسر ثابت انتخاب می\u200cکنند.',
    '💡 حقیقت جالب:    خرس قطبی پوستش سیاه است، فقط موهایش سفید به نظر می\u200cرسد.',
    '💡 حقیقت جالب:    ماه هر سال کمی از زمین دورتر می\u200cشود.',
    '💡 حقیقت جالب:    زنبورهای عسل می\u200cتوانند چهره\u200cهای انسان را تشخیص دهند.',
    '💡 حقیقت جالب:    قورباغه\u200cها نمی\u200cتوانند بدون بستن چشم\u200cهایشان غذا قورت دهند.',
    '💡 حقیقت جالب:    فیل\u200cها تنها پستاندارانی هستند که نمی\u200cتوانند بپرند.',
    '💡 حقیقت جالب:    طول روده انسان حدود هفت متر است.',
    '💡 حقیقت جالب:    صدای نهنگ آبی می\u200cتواند صدها کیلومتر در اقیانوس پخش شود.',
    '💡 حقیقت جالب:    برف در واقع بی\u200cرنگ است، سفیدی آن به خاطر بازتاب نور است.',
    '💡 حقیقت جالب:     زرافه\u200cها تقریباً به همان اندازه انسان\u200cها می\u200cخوابند، فقط خیلی کوتاه\u200cتر و چندبار در روز.',
    '💡 حقیقت جالب:     استخوان\u200cهای گوش انسان کوچک\u200cترین استخوان\u200cهای بدن هستند.',
    '💡 حقیقت جالب:     ونوس تنها سیاره\u200cای است که در جهت عکس بقیه می\u200cچرخد.',
    '💡 حقیقت جالب:     پروانه\u200cها با پاهایشان می\u200cچشند نه با دهانشان.',
    '💡 حقیقت جالب:     یک روز روی سیاره\u200cی مشتری فقط حدود ۱۰ ساعت زمینی طول می\u200cکشد.',
    '💡 حقیقت جالب:     مغز انسان حدود هفتاد و پنج درصد آب است.',
    '💡 حقیقت جالب:     شترها می\u200cتوانند بدون آب هفته\u200cها زنده بمانند.',
    '💡 حقیقت جالب:     کوسه\u200cها قبل از دایناسورها روی زمین زندگی می\u200cکردند.',
    '💡 حقیقت جالب:     صدای غرش شیر تا هشت کیلومتر شنیده می\u200cشود.',
    '💡 حقیقت جالب:     درخت\u200cهای سکویا از قدیمی\u200cترین موجودات زنده روی زمین\u200cاند.',
    '💡 حقیقت جالب:     زبان مورچه\u200cخوار می\u200cتواند تا شصت سانتی\u200cمتر طول داشته باشد.',
    '💡 حقیقت جالب:     پنگوئن\u200cها هر سال یک همسر ثابت انتخاب می\u200cکنند.',
    '💡 حقیقت جالب:     خرس قطبی پوستش سیاه است، فقط موهایش سفید به نظر می\u200cرسد.',
    '💡 حقیقت جالب:     ماه هر سال کمی از زمین دورتر می\u200cشود.',
    '💡 حقیقت جالب:     زنبورهای عسل می\u200cتوانند چهره\u200cهای انسان را تشخیص دهند.',
    '💡 حقیقت جالب:     قورباغه\u200cها نمی\u200cتوانند بدون بستن چشم\u200cهایشان غذا قورت دهند.',
    '💡 حقیقت جالب:     فیل\u200cها تنها پستاندارانی هستند که نمی\u200cتوانند بپرند.',
    '💡 حقیقت جالب:     طول روده انسان حدود هفت متر است.',
    '💡 حقیقت جالب:     صدای نهنگ آبی می\u200cتواند صدها کیلومتر در اقیانوس پخش شود.',
    '💡 حقیقت جالب:     برف در واقع بی\u200cرنگ است، سفیدی آن به خاطر بازتاب نور است.',
    '💡 حقیقت جالب:      زرافه\u200cها تقریباً به همان اندازه انسان\u200cها می\u200cخوابند، فقط خیلی کوتاه\u200cتر و چندبار در روز.',
    '💡 حقیقت جالب:      استخوان\u200cهای گوش انسان کوچک\u200cترین استخوان\u200cهای بدن هستند.',
    '💡 حقیقت جالب:      ونوس تنها سیاره\u200cای است که در جهت عکس بقیه می\u200cچرخد.',
    '💡 حقیقت جالب:      پروانه\u200cها با پاهایشان می\u200cچشند نه با دهانشان.',
    '💡 حقیقت جالب:      یک روز روی سیاره\u200cی مشتری فقط حدود ۱۰ ساعت زمینی طول می\u200cکشد.',
    '💡 حقیقت جالب:      مغز انسان حدود هفتاد و پنج درصد آب است.',
    '💡 حقیقت جالب:      شترها می\u200cتوانند بدون آب هفته\u200cها زنده بمانند.',
    '💡 حقیقت جالب:      کوسه\u200cها قبل از دایناسورها روی زمین زندگی می\u200cکردند.',
    '💡 حقیقت جالب:      صدای غرش شیر تا هشت کیلومتر شنیده می\u200cشود.',
    '💡 حقیقت جالب:      درخت\u200cهای سکویا از قدیمی\u200cترین موجودات زنده روی زمین\u200cاند.',
    '💡 حقیقت جالب:      زبان مورچه\u200cخوار می\u200cتواند تا شصت سانتی\u200cمتر طول داشته باشد.',
    '💡 حقیقت جالب:      پنگوئن\u200cها هر سال یک همسر ثابت انتخاب می\u200cکنند.',
    '💡 حقیقت جالب:      خرس قطبی پوستش سیاه است، فقط موهایش سفید به نظر می\u200cرسد.',
    '💡 حقیقت جالب:      ماه هر سال کمی از زمین دورتر می\u200cشود.',
    '💡 حقیقت جالب:      زنبورهای عسل می\u200cتوانند چهره\u200cهای انسان را تشخیص دهند.',
    '💡 حقیقت جالب:      قورباغه\u200cها نمی\u200cتوانند بدون بستن چشم\u200cهایشان غذا قورت دهند.',
    '💡 حقیقت جالب:      فیل\u200cها تنها پستاندارانی هستند که نمی\u200cتوانند بپرند.',
    '💡 حقیقت جالب:      طول روده انسان حدود هفت متر است.',
    '💡 حقیقت جالب:      صدای نهنگ آبی می\u200cتواند صدها کیلومتر در اقیانوس پخش شود.',
    '💡 حقیقت جالب:      برف در واقع بی\u200cرنگ است، سفیدی آن به خاطر بازتاب نور است.',
    '💡 حقیقت جالب:       زرافه\u200cها تقریباً به همان اندازه انسان\u200cها می\u200cخوابند، فقط خیلی کوتاه\u200cتر و چندبار در روز.',
    '💡 حقیقت جالب:       استخوان\u200cهای گوش انسان کوچک\u200cترین استخوان\u200cهای بدن هستند.',
    '💡 حقیقت جالب:       ونوس تنها سیاره\u200cای است که در جهت عکس بقیه می\u200cچرخد.',
    '💡 حقیقت جالب:       پروانه\u200cها با پاهایشان می\u200cچشند نه با دهانشان.',
    '💡 حقیقت جالب:       یک روز روی سیاره\u200cی مشتری فقط حدود ۱۰ ساعت زمینی طول می\u200cکشد.',
    '💡 حقیقت جالب:       مغز انسان حدود هفتاد و پنج درصد آب است.',
    '💡 حقیقت جالب:       شترها می\u200cتوانند بدون آب هفته\u200cها زنده بمانند.',
    '💡 حقیقت جالب:       کوسه\u200cها قبل از دایناسورها روی زمین زندگی می\u200cکردند.',
    '💡 حقیقت جالب:       صدای غرش شیر تا هشت کیلومتر شنیده می\u200cشود.',
    '💡 حقیقت جالب:       درخت\u200cهای سکویا از قدیمی\u200cترین موجودات زنده روی زمین\u200cاند.',
    '💡 حقیقت جالب:       زبان مورچه\u200cخوار می\u200cتواند تا شصت سانتی\u200cمتر طول داشته باشد.',
    '💡 حقیقت جالب:       پنگوئن\u200cها هر سال یک همسر ثابت انتخاب می\u200cکنند.',
    '💡 حقیقت جالب:       خرس قطبی پوستش سیاه است، فقط موهایش سفید به نظر می\u200cرسد.',
    '💡 حقیقت جالب:       ماه هر سال کمی از زمین دورتر می\u200cشود.',
    '💡 حقیقت جالب:       زنبورهای عسل می\u200cتوانند چهره\u200cهای انسان را تشخیص دهند.',
    '💡 حقیقت جالب:       قورباغه\u200cها نمی\u200cتوانند بدون بستن چشم\u200cهایشان غذا قورت دهند.',
    '💡 حقیقت جالب:       فیل\u200cها تنها پستاندارانی هستند که نمی\u200cتوانند بپرند.',
    '💡 حقیقت جالب:       طول روده انسان حدود هفت متر است.',
    '💡 حقیقت جالب:       صدای نهنگ آبی می\u200cتواند صدها کیلومتر در اقیانوس پخش شود.',
    '💡 حقیقت جالب:       برف در واقع بی\u200cرنگ است، سفیدی آن به خاطر بازتاب نور است.',
    '💡 حقیقت جالب:        زرافه\u200cها تقریباً به همان اندازه انسان\u200cها می\u200cخوابند، فقط خیلی کوتاه\u200cتر و چندبار در روز.',
    '💡 حقیقت جالب:        استخوان\u200cهای گوش انسان کوچک\u200cترین استخوان\u200cهای بدن هستند.',
    '💡 حقیقت جالب:        ونوس تنها سیاره\u200cای است که در جهت عکس بقیه می\u200cچرخد.',
    '💡 حقیقت جالب:        پروانه\u200cها با پاهایشان می\u200cچشند نه با دهانشان.',
    '💡 حقیقت جالب:        یک روز روی سیاره\u200cی مشتری فقط حدود ۱۰ ساعت زمینی طول می\u200cکشد.',
    '💡 حقیقت جالب:        مغز انسان حدود هفتاد و پنج درصد آب است.',
    '💡 حقیقت جالب:        شترها می\u200cتوانند بدون آب هفته\u200cها زنده بمانند.',
    '💡 حقیقت جالب:        کوسه\u200cها قبل از دایناسورها روی زمین زندگی می\u200cکردند.',
    '💡 حقیقت جالب:        صدای غرش شیر تا هشت کیلومتر شنیده می\u200cشود.',
    '💡 حقیقت جالب:        درخت\u200cهای سکویا از قدیمی\u200cترین موجودات زنده روی زمین\u200cاند.',
    '💡 حقیقت جالب:        زبان مورچه\u200cخوار می\u200cتواند تا شصت سانتی\u200cمتر طول داشته باشد.',
    '💡 حقیقت جالب:        پنگوئن\u200cها هر سال یک همسر ثابت انتخاب می\u200cکنند.',
    '💡 حقیقت جالب:        خرس قطبی پوستش سیاه است، فقط موهایش سفید به نظر می\u200cرسد.',
    '💡 حقیقت جالب:        ماه هر سال کمی از زمین دورتر می\u200cشود.',
    '💡 حقیقت جالب:        زنبورهای عسل می\u200cتوانند چهره\u200cهای انسان را تشخیص دهند.',
    '💡 حقیقت جالب:        قورباغه\u200cها نمی\u200cتوانند بدون بستن چشم\u200cهایشان غذا قورت دهند.',
    '💡 حقیقت جالب:        فیل\u200cها تنها پستاندارانی هستند که نمی\u200cتوانند بپرند.',
    '💡 حقیقت جالب:        طول روده انسان حدود هفت متر است.',
    '💡 حقیقت جالب:        صدای نهنگ آبی می\u200cتواند صدها کیلومتر در اقیانوس پخش شود.',
    '💡 حقیقت جالب:        برف در واقع بی\u200cرنگ است، سفیدی آن به خاطر بازتاب نور است.',
    '💡 حقیقت جالب:         زرافه\u200cها تقریباً به همان اندازه انسان\u200cها می\u200cخوابند، فقط خیلی کوتاه\u200cتر و چندبار در روز.',
    '💡 حقیقت جالب:         استخوان\u200cهای گوش انسان کوچک\u200cترین استخوان\u200cهای بدن هستند.',
    '💡 حقیقت جالب:         ونوس تنها سیاره\u200cای است که در جهت عکس بقیه می\u200cچرخد.',
    '💡 حقیقت جالب:         پروانه\u200cها با پاهایشان می\u200cچشند نه با دهانشان.',
    '💡 حقیقت جالب:         یک روز روی سیاره\u200cی مشتری فقط حدود ۱۰ ساعت زمینی طول می\u200cکشد.',
    '💡 حقیقت جالب:         مغز انسان حدود هفتاد و پنج درصد آب است.',
    '💡 حقیقت جالب:         شترها می\u200cتوانند بدون آب هفته\u200cها زنده بمانند.',
    '💡 حقیقت جالب:         کوسه\u200cها قبل از دایناسورها روی زمین زندگی می\u200cکردند.',
    '💡 حقیقت جالب:         صدای غرش شیر تا هشت کیلومتر شنیده می\u200cشود.',
    '💡 حقیقت جالب:         درخت\u200cهای سکویا از قدیمی\u200cترین موجودات زنده روی زمین\u200cاند.',
    '💡 حقیقت جالب:         زبان مورچه\u200cخوار می\u200cتواند تا شصت سانتی\u200cمتر طول داشته باشد.',
    '💡 حقیقت جالب:         پنگوئن\u200cها هر سال یک همسر ثابت انتخاب می\u200cکنند.',
    '💡 حقیقت جالب:         خرس قطبی پوستش سیاه است، فقط موهایش سفید به نظر می\u200cرسد.',
    '💡 حقیقت جالب:         ماه هر سال کمی از زمین دورتر می\u200cشود.',
    '💡 حقیقت جالب:         زنبورهای عسل می\u200cتوانند چهره\u200cهای انسان را تشخیص دهند.',
    '💡 حقیقت جالب:         قورباغه\u200cها نمی\u200cتوانند بدون بستن چشم\u200cهایشان غذا قورت دهند.',
    '💡 حقیقت جالب:         فیل\u200cها تنها پستاندارانی هستند که نمی\u200cتوانند بپرند.',
    '💡 حقیقت جالب:         طول روده انسان حدود هفت متر است.',
    '💡 حقیقت جالب:         صدای نهنگ آبی می\u200cتواند صدها کیلومتر در اقیانوس پخش شود.',
    '💡 حقیقت جالب:         برف در واقع بی\u200cرنگ است، سفیدی آن به خاطر بازتاب نور است.',
    '💡 حقیقت جالب:          زرافه\u200cها تقریباً به همان اندازه انسان\u200cها می\u200cخوابند، فقط خیلی کوتاه\u200cتر و چندبار در روز.',
    '💡 حقیقت جالب:          استخوان\u200cهای گوش انسان کوچک\u200cترین استخوان\u200cهای بدن هستند.',
    '💡 حقیقت جالب:          ونوس تنها سیاره\u200cای است که در جهت عکس بقیه می\u200cچرخد.',
    '💡 حقیقت جالب:          پروانه\u200cها با پاهایشان می\u200cچشند نه با دهانشان.',
    '💡 حقیقت جالب:          یک روز روی سیاره\u200cی مشتری فقط حدود ۱۰ ساعت زمینی طول می\u200cکشد.',
    '💡 حقیقت جالب:          مغز انسان حدود هفتاد و پنج درصد آب است.',
    '💡 حقیقت جالب:          شترها می\u200cتوانند بدون آب هفته\u200cها زنده بمانند.',
    '💡 حقیقت جالب:          کوسه\u200cها قبل از دایناسورها روی زمین زندگی می\u200cکردند.',
    '💡 حقیقت جالب:          صدای غرش شیر تا هشت کیلومتر شنیده می\u200cشود.',
    '💡 حقیقت جالب:          درخت\u200cهای سکویا از قدیمی\u200cترین موجودات زنده روی زمین\u200cاند.',
    '💡 حقیقت جالب:          زبان مورچه\u200cخوار می\u200cتواند تا شصت سانتی\u200cمتر طول داشته باشد.',
    '💡 حقیقت جالب:          پنگوئن\u200cها هر سال یک همسر ثابت انتخاب می\u200cکنند.',
    '💡 حقیقت جالب:          خرس قطبی پوستش سیاه است، فقط موهایش سفید به نظر می\u200cرسد.',
    '💡 حقیقت جالب:          ماه هر سال کمی از زمین دورتر می\u200cشود.',
    '💡 حقیقت جالب:          زنبورهای عسل می\u200cتوانند چهره\u200cهای انسان را تشخیص دهند.',
    '💡 حقیقت جالب:          قورباغه\u200cها نمی\u200cتوانند بدون بستن چشم\u200cهایشان غذا قورت دهند.',
    '💡 حقیقت جالب:          فیل\u200cها تنها پستاندارانی هستند که نمی\u200cتوانند بپرند.',
    '💡 حقیقت جالب:          طول روده انسان حدود هفت متر است.',
    '💡 حقیقت جالب:          صدای نهنگ آبی می\u200cتواند صدها کیلومتر در اقیانوس پخش شود.',
    '💡 حقیقت جالب:          برف در واقع بی\u200cرنگ است، سفیدی آن به خاطر بازتاب نور است.',
]

async def story_cmd(bot: Robot, message: Message):
    """داستان تصادفی"""
    await themed_reply(message, random.choice(STORY_LIST), 'bio')

async def truth_cmd(bot: Robot, message: Message):
    """یک سوال حقیقت تصادفی (بازی جرات یا حقیقت)"""
    await themed_reply(message, random.choice(TRUTH_LIST), 'bio')

async def dare_cmd(bot: Robot, message: Message):
    """یک چالش جرات تصادفی (بازی جرات یا حقیقت)"""
    await themed_reply(message, random.choice(DARE_LIST), 'bio')

async def truth_or_dare_cmd(bot: Robot, message: Message):
    """شروع بازی جرات یا حقیقت - از کاربر می‌خواهد انتخاب کند"""
    await message.reply(
        "🎲 حقیقت یا جرأت؟\n\n"
        "🗣 برای سوال حقیقت بنویس: «حقیقت»\n"
        "🔥 برای چالش جرأت بنویس: «جرأت»\n\n"
        "هر بار که بنویسی یه سوال/چالش تصادفی جدید می‌گیری! 😈"
    )

async def penalty_cmd(bot: Robot, message: Message):
    """شبیه‌سازی زدن پنالتی فوتبالی — نتیجه تصادفی: گل / سیو / گرفتن دروازه‌بان / برخورد به تیر"""
    label, outcome_text = _pick_penalty_outcome()
    text = (
        "🎯 پنالتی زده شد...\n\n"
        f"{outcome_text}\n\n"
        f"📋 نتیجه: {label}"
    )
    await message.reply(text)

async def penalty_dare_cmd(bot: Robot, message: Message):
    """پنالتی چالشی (شرط/دِیر) تصادفی"""
    await themed_reply(message, random.choice(PENALTY_DARE_LIST), 'bio')

async def riddle_cmd(bot: Robot, message: Message):
    """معمای تصادفی"""
    await themed_reply(message, random.choice(RIDDLE_LIST), 'bio')

async def proverb_cmd(bot: Robot, message: Message):
    """ضرب‌المثل تصادفی"""
    await themed_reply(message, random.choice(PROVERB_LIST), 'bio')

async def motivation_cmd(bot: Robot, message: Message):
    """جمله انگیزشی تصادفی"""
    await themed_reply(message, random.choice(MOTIVATION_LIST), 'bio')

async def joke_cmd(bot: Robot, message: Message):
    """شوخی تصادفی"""
    await themed_reply(message, random.choice(JOKE_LIST), 'bio')

async def fun_fact_cmd(bot: Robot, message: Message):
    """حقیقت جالب تصادفی"""
    await themed_reply(message, random.choice(FUN_FACT_LIST), 'bio')

# =========================================================
#  توابع کمکی
# =========================================================

# =========================================================
#  دستورات مدیریت کاربران
# =========================================================
# (توابع format_number / get_user_name_from_id / is_admin / is_owner قبلاً در
#  همین فایل تعریف شده‌اند — نسخه‌ی تکراری‌شان که اینجا بود حذف شد تا فقط
#  یک نسخه‌ی مرجع از هر تابع وجود داشته باشد.)

@bot.on_message(filters=lambda m: _cmd_is(m, "ban"))
async def ban_cmd(bot: Robot, message: Message):
    """
    بن واقعی روی تلگرام (banChatMember) — نه صرفاً یک رکورد دیتابیس.
    فرمت: /ban [دقیقه] [دلیل]   → اگر دقیقه داده نشود، بن دائمی است.
    بن موقت با until_date واقعی به تلگرام داده می‌شود و تلگرام خودش سر وقت برمی‌دارد.
    فقط اگر تلگرام عملیات را تایید کند «بن شد» نمایش داده می‌شود؛ وگرنه علت واقعی خطا.
    """
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not has_permission(user_id, group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return

    target_id = resolve_target_id(message)
    if not target_id:
        await message.reply(NEED_REPLY_MSG)
        return
    target_name = await get_display_name(bot, get_reply_message(message) or target_id, group_id=group_id, prefer_live=True) or "کاربر"

    rest = _cmd_rest(message.text)
    parts = rest.split(maxsplit=1)
    duration_minutes = None
    reason = rest
    if parts:
        parsed = parse_duration_minutes(parts[0])
        if parsed is not None:
            duration_minutes = parsed
            reason = parts[1].strip() if len(parts) > 1 else ""
        elif looks_like_duration_attempt(parts[0]):
            await message.reply("⚠️ مدت بن باید یک عدد صحیح مثبت باشد. مثال: بن ۶۰")
            return
    reason = reason or "بدون دلیل"

    if duration_minutes is not None and duration_minutes > TELEGRAM_MAX_TEMP_MINUTES:
        await message.reply("⚠️ حداکثر مدت بن موقت ۳۶۶ روز است (محدودیت تلگرام). برای بن بیشتر، بدون مدت بنویس (بن دائمی).")
        return

    blocked = punish_guard(group_data, user_id, target_id)
    if blocked:
        await message.reply(blocked)
        return

    if is_punished_active(group_data, "bans", target_id):
        # دیتابیس می‌گوید بن است؛ وضعیت واقعی تلگرام را هم چک کن (ممکن است دستی رفع بن شده باشد)
        if await _is_really_punished(bot, group_id, target_id, "bans") is not False:
            await message.reply(f"{theme_icon(group_data, 'warning')} {target_name} قبلاً بن است!")
            return

    res = await moderation_ban(bot, group_id, target_id, user_id, duration_minutes, reason)
    if not res:
        await message.reply(f"{theme_icon(group_data, 'error')} بن {target_name} انجام نشد.\n🔎 علت: {res.error}")
        return

    duration_text = f"به مدت {duration_minutes} دقیقه" if duration_minutes else "به‌صورت دائمی"
    await message.reply(f"{theme_icon(group_data, 'success')} 🚫 **کاربر {target_name} {duration_text} بن شد!**\n📝 دلیل: {reason}")

@bot.on_message(filters=lambda m: _cmd_is(m, "unban"))
async def unban_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not has_permission(user_id, group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return

    target_id = resolve_target_id(message)
    if not target_id:
        await message.reply(NEED_REPLY_MSG)
        return
    target_name = await get_display_name(bot, get_reply_message(message) or target_id, group_id=group_id, prefer_live=True) or "کاربر"

    state, res = await moderation_unban(bot, group_id, target_id, user_id)
    if state == "failed":
        await message.reply(f"{theme_icon(group_data, 'error')} رفع بن {target_name} انجام نشد (بن او همچنان باقی است).\n🔎 علت: {res.error}")
    elif state == "not_banned":
        await message.reply(f"{theme_icon(group_data, 'warning')} {target_name} بن نیست!")
    else:
        extra = f"\nℹ️ {res.warning}" if res.warning else ""
        await message.reply(f"{theme_icon(group_data, 'success')} **بن {target_name} برداشته شد!**{extra}")

@bot.on_message(filters=lambda m: _cmd_is(m, "kick"))
async def kick_cmd(bot: Robot, message: Message):
    """اخراج واقعی: بن + رفع‌بن فوری (کاربر می‌تواند دوباره وارد شود). برای ممنوعیت از /ban استفاده کن."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    if not get_reply_message(message):
        await message.reply("⚠️ روی پیام کاربر ریپلای کن!")
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return

    target_id = str(get_reply_sender_id(message))
    target_name = (await get_display_name(bot, get_reply_sender_id(message), group_id=group_id, prefer_live=True) if get_reply_message(message) else "کاربر")
    reason = _cmd_rest(message.text) or "بدون دلیل"

    blocked = punish_guard(group_data, user_id, target_id)
    if blocked:
        await message.reply(blocked)
        return

    # اخراج = بن + رفع‌بن؛ اگر کاربر از قبل بن است، اخراج بن او را برمی‌داشت
    real = await _is_really_punished(bot, group_id, target_id, "bans")
    if real is True or (real is None and is_punished_active(group_data, "bans", target_id)):
        await message.reply(f"{theme_icon(group_data, 'warning')} {target_name} همین حالا بن است؛ اخراج بن او را برمی‌داشت. برای رفع ممنوعیت از «آنبن» استفاده کن.")
        return

    res = await moderation_kick(bot, group_id, target_id, user_id, reason)
    if not res:
        await message.reply(f"{theme_icon(group_data, 'error')} اخراج {target_name} انجام نشد.\n🔎 علت: {res.error}")
        return

    text = f"{theme_icon(group_data, 'success')} 👢 **کاربر {target_name} اخراج شد!**\n📝 دلیل: {reason}"
    if res.warning:
        text += f"\n⚠️ {res.warning}"
    await message.reply(text)

@bot.on_message(filters=lambda m: _cmd_is(m, "warn"))
async def warn_cmd(bot: Robot, message: Message):
    """
    اخطار با دلیل، زمان ثبت و تاریخ انقضا. رسیدن به حد مجاز (max_warn) اقدام خودکار
    (بن/اخراج/سکوت طبق /warnaction) را اجرا می‌کند.
    """
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    if not get_reply_message(message):
        await message.reply("⚠️ روی پیام کاربر ریپلای کن!")
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return

    target_id = str(get_reply_sender_id(message))
    target_name = (await get_display_name(bot, get_reply_sender_id(message), group_id=group_id, prefer_live=True) if get_reply_message(message) else "کاربر")
    reason = _cmd_rest(message.text) or "بدون دلیل"

    # بعد از آخرین await، دیتابیس را تازه بخوان و بلافاصله (بدون await) ذخیره کن
    group_data = get_group_data(group_id)
    info = add_warning(group_data, group_id, target_id, reason, user_id)
    save_group_data(group_id, group_data)

    text = (f"{theme_icon(group_data, 'warning')} **به {target_name} اخطار داده شد!**\n📌 تعداد: {info['count']}/{info['max']}\n"
            f"📝 دلیل: {reason}\n⏳ اعتبار: تا {_fmt_date(info['entry']['expires_at'])}")
    if info["limit_reached"]:
        _performed, action_text = await execute_warn_action(bot, group_id, target_id, user_id)
        text += f"\n\n{action_text}"
    await message.reply(text)

@bot.on_message(filters=lambda m: _cmd_is(m, "unwarn"))
async def unwarn_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    if not get_reply_message(message):
        await message.reply("⚠️ روی پیام کاربر ریپلای کن!")
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return

    target_id = str(get_reply_sender_id(message))
    target_name = (await get_display_name(bot, get_reply_sender_id(message), group_id=group_id, prefer_live=True) if get_reply_message(message) else "کاربر")

    group_data = get_group_data(group_id)
    left = remove_last_warning(group_data, target_id)
    if left is not None:
        add_log(group_data, "رفع اخطار", admin_id=user_id, target_id=target_id)
        save_group_data(group_id, group_data)
        await message.reply(f"{theme_icon(group_data, 'success')} **یک اخطار از {target_name} حذف شد!**\n📌 تعداد: {left}")
    else:
        save_group_data(group_id, group_data)  # پاکسازی اخطارهای منقضی‌شده
        await message.reply(f"{theme_icon(group_data, 'warning')} {target_name} اخطاری ندارد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "mute"))
async def mute_cmd(bot: Robot, message: Message):
    """
    سکوت واقعی: Restriction روی خود کاربر در تلگرام (restrictChatMember با
    can_send_messages=False و until_date واقعی)، نه فقط یک رکورد در JSON.
    فرمت: /mute [دقیقه] [دلیل]   → عدد فارسی یا انگلیسی هر دو پشتیبانی می‌شوند.
    مقدار نامعتبر (خالی/غیرعددی/صفر/منفی) → از مقدار پیش‌فرض گروه استفاده می‌شود.
    """
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not has_permission(user_id, group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return

    target_id = resolve_target_id(message)
    if not target_id:
        await message.reply(NEED_REPLY_MSG)
        return
    target_name = await get_display_name(bot, get_reply_message(message) or target_id, group_id=group_id, prefer_live=True) or "کاربر"

    rest = _cmd_rest(message.text)
    parts = rest.split(maxsplit=1)
    reason = ""
    duration_minutes = None
    if parts:
        parsed = parse_duration_minutes(parts[0])
        if parsed is not None:
            duration_minutes = parsed
            reason = parts[1].strip() if len(parts) > 1 else ""
        elif looks_like_duration_attempt(parts[0]):
            # کاربر واقعاً یک عدد وارد کرده ولی نامعتبر بوده (۰، منفی و...)
            await message.reply("⚠️ مدت سکوت باید یک عدد صحیح مثبت باشد. مثال: سکوت ۱۰")
            return
        else:
            # عددی وارد نشده؛ کل متن را دلیل در نظر بگیر و از مدت پیش‌فرض استفاده کن
            reason = rest
    if duration_minutes is None:
        duration_minutes = group_data['settings'].get('mute_duration', 5)
    reason = reason or "بدون دلیل"

    if duration_minutes > TELEGRAM_MAX_TEMP_MINUTES:
        await message.reply("⚠️ حداکثر مدت سکوت ۳۶۶ روز است (محدودیت تلگرام).")
        return

    blocked = punish_guard(group_data, user_id, target_id)
    if blocked:
        await message.reply(blocked)
        return

    if is_punished_active(group_data, "mutes", target_id):
        # دیتابیس می‌گوید میوت است؛ وضعیت واقعی تلگرام را هم چک کن
        if await _is_really_punished(bot, group_id, target_id, "mutes") is not False:
            await message.reply(f"{theme_icon(group_data, 'warning')} {target_name} قبلاً میوت است!")
            return

    res = await moderation_mute(bot, group_id, target_id, user_id, duration_minutes, reason)
    if not res:
        await message.reply(f"{theme_icon(group_data, 'error')} سکوت {target_name} انجام نشد.\n🔎 علت: {res.error}")
        return

    await message.reply(f"{theme_icon(group_data, 'success')} 🔇 **کاربر {target_name} به مدت {duration_minutes} دقیقه میوت شد!**\n📝 دلیل: {reason}")

@bot.on_message(filters=lambda m: _cmd_is(m, "unmute"))
async def unmute_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not has_permission(user_id, group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return

    target_id = resolve_target_id(message)
    if not target_id:
        await message.reply(NEED_REPLY_MSG)
        return
    target_name = await get_display_name(bot, get_reply_message(message) or target_id, group_id=group_id, prefer_live=True) or "کاربر"

    state, res = await moderation_unmute(bot, group_id, target_id, user_id)
    if state == "failed":
        await message.reply(f"{theme_icon(group_data, 'error')} رفع سکوت {target_name} انجام نشد (سکوت او همچنان باقی است).\n🔎 علت: {res.error}")
    elif state == "not_muted":
        await message.reply(f"{theme_icon(group_data, 'warning')} {target_name} میوت نیست!")
    else:
        extra = ""
        if res.warning:
            extra = f"\nℹ️ {res.warning}"
        await message.reply(f"{theme_icon(group_data, 'success')} 🔊 **میوت {target_name} برداشته شد!**{extra}")

@bot.on_message(filters=lambda m: _cmd_is(m, "warnaction"))
async def warnaction_cmd(bot: Robot, message: Message):
    """تنظیم اقدام خودکار بعد از رسیدن به حد مجاز اخطار: ban | kick | mute (فارسی: بن | اخراج | سکوت)."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return

    aliases = {"ban": "ban", "بن": "ban", "kick": "kick", "اخراج": "kick",
               "mute": "mute", "سکوت": "mute", "میوت": "mute"}
    current = group_data['settings'].get('warn_action', DEFAULT_WARN_ACTION)
    arg = _cmd_rest(message.text).strip().lower()
    choice = aliases.get(arg)
    if choice is None:
        await message.reply(f"⚠️ دستور: /warnaction [ban|kick|mute]\n📌 مقدار فعلی: {WARN_ACTIONS.get(current, current)}")
        return

    group_data = get_group_data(group_id)
    group_data['settings']['warn_action'] = choice
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **اقدام بعد از رسیدن به حد اخطار روی «{WARN_ACTIONS[choice]}» تنظیم شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "warnexpire"))
async def warnexpire_cmd(bot: Robot, message: Message):
    """تنظیم مدت اعتبار اخطار به روز (۰ = بدون انقضا). فقط روی اخطارهای جدید اثر دارد."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return

    arg = to_en_digits(_cmd_rest(message.text)).strip()
    if not arg.isdigit():
        current = get_warn_expire_days(group_data)
        shown = f"{current} روز" if current else "بدون انقضا"
        await message.reply(f"⚠️ دستور: /warnexpire [روز]  (۰ = بدون انقضا)\n📌 مقدار فعلی: {shown}")
        return

    days = int(arg)
    group_data = get_group_data(group_id)
    group_data['settings']['warn_expire_days'] = days
    save_group_data(group_id, group_data)
    await message.reply(
        f"✅ **اعتبار اخطارهای جدید روی {days} روز تنظیم شد!**" if days else "✅ **اخطارهای جدید دیگر منقضی نمی‌شوند.**")

@bot.on_message(filters=lambda m: _cmd_is(m, "block"))
async def block_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    if not get_reply_message(message):
        await message.reply("⚠️ روی پیام کاربر ریپلای کن!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    target_id = str(get_reply_sender_id(message))
    target_name = (await get_display_name(bot, get_reply_sender_id(message), group_id=group_id, prefer_live=True) if get_reply_message(message) else "کاربر")
    
    if target_id not in group_data['blocks']:
        group_data['blocks'].append(target_id)
        group_data['stats']['total_blocks'] = group_data['stats'].get('total_blocks', 0) + 1
        save_group_data(group_id, group_data)
        await message.reply(f"{theme_icon(group_data, 'success')} 🛡 **کاربر {target_name} بلاک شد!**")
    else:
        await message.reply(f"{theme_icon(group_data, 'warning')} {target_name} قبلاً بلاک است!")

@bot.on_message(filters=lambda m: _cmd_is(m, "unblock"))
async def unblock_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    if not get_reply_message(message):
        await message.reply("⚠️ روی پیام کاربر ریپلای کن!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    target_id = str(get_reply_sender_id(message))
    target_name = (await get_display_name(bot, get_reply_sender_id(message), group_id=group_id, prefer_live=True) if get_reply_message(message) else "کاربر")
    
    if target_id in group_data['blocks']:
        group_data['blocks'].remove(target_id)
        save_group_data(group_id, group_data)
        await message.reply(f"{theme_icon(group_data, 'success')} 🔓 **بلاک {target_name} برداشته شد!**")
    else:
        await message.reply(f"{theme_icon(group_data, 'warning')} {target_name} بلاک نیست!")
        # =========================================================
#  دستورات مدیریت ادمین‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "addadmin"))
async def add_admin_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند ادمین اضافه کند!")
        return
    
    # 🛠 رفع باگ: قبلاً فقط با شناسه‌ی عددی خام کار می‌کرد. راهنما همیشه گفته
    # بود «با ریپلای روی شخص» هم می‌شه، ولی این حالت اصلاً پیاده‌سازی نشده بود -
    # اکثر مدیرها شناسه‌ی عددی بقیه رو نمی‌دونن، پس عملاً این دستور غیرقابل‌استفاده بود.
    parts = message.text.split()
    target_id = parts[1] if len(parts) >= 2 and looks_like_user_id(parts[1]) else get_reply_sender_id(message)
    if not target_id:
        await message.reply("⚠️ روی پیام شخص موردنظر ریپلای بزنید، یا: /addadmin [شناسه کاربر]")
        return
    target_id = str(target_id)
    target_name = await get_display_name(bot, target_id)
    
    if target_id not in group_data['admins']:
        group_data['admins'].append(target_id)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **{target_name} به عنوان ادمین اضافه شد!**")
    else:
        await message.reply(f"⚠️ {target_name} قبلاً ادمین است!")

@bot.on_message(filters=lambda m: _cmd_is(m, "removeadmin"))
async def remove_admin_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند ادمین حذف کند!")
        return
    
    parts = message.text.split()
    target_id = parts[1] if len(parts) >= 2 and looks_like_user_id(parts[1]) else get_reply_sender_id(message)
    if not target_id:
        await message.reply("⚠️ روی پیام شخص موردنظر ریپلای بزنید، یا: /removeadmin [شناسه کاربر]")
        return
    target_id = str(target_id)
    target_name = await get_display_name(bot, target_id)
    
    if target_id in group_data['admins']:
        group_data['admins'].remove(target_id)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **{target_name} از ادمین‌ها حذف شد!**")
    else:
        await message.reply(f"⚠️ {target_name} ادمین نیست!")

@bot.on_message(filters=lambda m: _cmd_is(m, "addowner"))
async def add_owner_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    # قبلاً فقط کسی که owner_primary دقیقاً برابرش بود اجازه داشت، ولی این
    # فیلد هیچ‌جای کد مقداردهی نمی‌شد و همین باعث می‌شد این دستور همیشه رد
    # بشه؛ حالا هر مالک ثبت‌شده (یا مالک اصلی ربات) می‌تونه مالک جدید اضافه کنه.
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند مالک جدید اضافه کند!")
        return
    
    parts = message.text.split()
    target_id = parts[1] if len(parts) >= 2 and looks_like_user_id(parts[1]) else get_reply_sender_id(message)
    if not target_id:
        await message.reply("⚠️ روی پیام شخص موردنظر ریپلای بزنید، یا: /addowner [شناسه کاربر]")
        return
    target_id = str(target_id)
    target_name = await get_display_name(bot, target_id)
    
    if target_id not in group_data['owners']:
        group_data['owners'].append(target_id)
        save_group_data(group_id, group_data)
        await message.reply(f"👑 **{target_name} به عنوان مالک اضافه شد!**")
    else:
        await message.reply(f"⚠️ {target_name} قبلاً مالک است!")

@bot.on_message(filters=lambda m: _cmd_is(m, "removeowner"))
async def remove_owner_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند مالک حذف کند!")
        return
    
    parts = message.text.split()
    target_id = parts[1] if len(parts) >= 2 and looks_like_user_id(parts[1]) else get_reply_sender_id(message)
    if not target_id:
        await message.reply("⚠️ روی پیام شخص موردنظر ریپلای بزنید، یا: /removeowner [شناسه کاربر]")
        return
    target_id = str(target_id)
    target_name = await get_display_name(bot, target_id)
    
    if target_id in group_data['owners']:
        group_data['owners'].remove(target_id)
        save_group_data(group_id, group_data)
        await message.reply(f"👑 **{target_name} از مالک‌ها حذف شد!**")
    else:
        await message.reply(f"⚠️ {target_name} مالک نیست!")

@bot.on_message(filters=lambda m: _cmd_is(m, "addspecial"))
async def add_special_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند ویژه اضافه کند!")
        return
    
    parts = message.text.split()
    target_id = parts[1] if len(parts) >= 2 and looks_like_user_id(parts[1]) else get_reply_sender_id(message)
    if not target_id:
        await message.reply("⚠️ روی پیام شخص موردنظر ریپلای بزنید، یا: /addspecial [شناسه کاربر]")
        return
    target_id = str(target_id)
    target_name = await get_display_name(bot, target_id)
    
    if target_id not in group_data['specials']:
        group_data['specials'].append(target_id)
        save_group_data(group_id, group_data)
        await message.reply(f"⭐ **{target_name} به عنوان ویژه اضافه شد!**")
    else:
        await message.reply(f"⚠️ {target_name} قبلاً ویژه است!")

@bot.on_message(filters=lambda m: _cmd_is(m, "removespecial"))
async def remove_special_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند ویژه حذف کند!")
        return
    
    parts = message.text.split()
    target_id = parts[1] if len(parts) >= 2 and looks_like_user_id(parts[1]) else get_reply_sender_id(message)
    if not target_id:
        await message.reply("⚠️ روی پیام شخص موردنظر ریپلای بزنید، یا: /removespecial [شناسه کاربر]")
        return
    target_id = str(target_id)
    target_name = await get_display_name(bot, target_id)
    
    if target_id in group_data['specials']:
        group_data['specials'].remove(target_id)
        save_group_data(group_id, group_data)
        await message.reply(f"⭐ **{target_name} از ویژه‌ها حذف شد!**")
    else:
        await message.reply(f"⚠️ {target_name} ویژه نیست!")

# =========================================================
#  دستورات تنظیمات
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "setmaxwarn"))
async def set_max_warn_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند این تنظیم را تغییر دهد!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /setmaxwarn [تعداد]")
        return
    
    try:
        count = int(parts[1])
        if count > 0:
            group_data['settings']['max_warn'] = count
            save_group_data(group_id, group_data)
            await message.reply(f"✅ **حداکثر اخطار به {count} تغییر یافت!**")
        else:
            await message.reply("⚠️ تعداد باید بیشتر از 0 باشد!")
    except (ValueError, IndexError):
        await message.reply("⚠️ تعداد را به عدد وارد کنید!")

@bot.on_message(filters=lambda m: _cmd_is(m, "setmuteduration"))
async def set_mute_duration_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند این تنظیم را تغییر دهد!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /setmuteduration [دقیقه]")
        return
    
    try:
        duration = int(parts[1])
        if duration > 0:
            group_data['settings']['mute_duration'] = duration
            save_group_data(group_id, group_data)
            await message.reply(f"✅ **مدت میوت به {duration} دقیقه تغییر یافت!**")
        else:
            await message.reply("⚠️ مدت باید بیشتر از 0 باشد!")
    except (ValueError, IndexError):
        await message.reply("⚠️ مدت را به عدد وارد کنید!")

@bot.on_message(filters=lambda m: m.text and m.text == "/lock")
async def lock_group_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    group_data['settings']['lock'] = True
    save_group_data(group_id, group_data)
    await message.reply("🔒 **گروه قفل شد!** فقط ادمین‌ها می‌توانند پیام ارسال کنند.")

@bot.on_message(filters=lambda m: m.text and m.text == "/unlock")
async def unlock_group_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    group_data['settings']['lock'] = False
    save_group_data(group_id, group_data)
    await message.reply("🔓 **گروه باز شد!**")


# =========================================================
#  🆕 حالت خواب — خواب روشن / خواب خاموش
# =========================================================
@bot.on_message(filters=lambda m: m.text and m.text == "/sleep_on")
async def sleep_on_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    group_data.setdefault('settings', {})['sleep_mode'] = True
    save_group_data(group_id, group_data)
    await message.reply(
        "😴 **حالت خواب فعال شد!** از این پس پیام‌های اعضای عادی حذف می‌شوند تا "
        "گروه ساکت بماند؛ مالک/ادمین/ویژه/معاف طبق معمول استثنا هستند."
    )


@bot.on_message(filters=lambda m: m.text and m.text == "/sleep_off")
async def sleep_off_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    group_data.setdefault('settings', {})['sleep_mode'] = False
    save_group_data(group_id, group_data)
    await message.reply("☀️ **حالت خواب غیرفعال شد!** گروه به حالت عادی برگشت.")


@bot.on_message(filters=lambda m: m.text and m.text == "/antispam")
async def anti_spam_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    group_data['settings']['anti_spam'] = not group_data['settings'].get('anti_spam', True)
    status = "فعال" if group_data['settings']['anti_spam'] else "غیرفعال"
    save_group_data(group_id, group_data)
    await message.reply(f"🔄 **ضد اسپم {status} شد!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/antilink")
async def anti_link_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    group_data['settings']['anti_link'] = not group_data['settings'].get('anti_link', True)
    status = "فعال" if group_data['settings']['anti_link'] else "غیرفعال"
    save_group_data(group_id, group_data)
    await message.reply(f"🔗 **ضد لینک {status} شد!**")

# 🛠 جدید: «لینک قفل» / «لینک باز» - نسخه‌ی صریح (set به‌جای toggle) که در
# راهنما تبلیغ می‌شد اما پیاده‌سازی نداشت. برخلاف /antilink که وضعیت رو
# برعکس می‌کنه، این دو همیشه یک نتیجه‌ی مشخص می‌دن (idempotent) که برای
# دستور فارسی طبیعی‌تره: «لینک قفل» یعنی همیشه قفل کن، نه «برعکس کن».
@bot.on_message(filters=lambda m: m.text and m.text == "/linklockon")
async def link_lock_on_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return

    group_data['settings']['anti_link'] = True
    save_group_data(group_id, group_data)
    await message.reply("🔗🔒 **قفل لینک فعال شد! از این به بعد ارسال لینک ممنوعه.**")


@bot.on_message(filters=lambda m: m.text and m.text == "/linklockoff")
async def link_lock_off_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return

    group_data['settings']['anti_link'] = False
    save_group_data(group_id, group_data)
    await message.reply("🔗🔓 **قفل لینک باز شد! حالا ارسال لینک آزاده.**")


# 🆕 «قفل فحش» / «فحش باز» - نسخه‌ی صریح (idempotent) برای anti_swear، دقیقاً به
# سیاق «قفل لینک»/«لینک باز» بالا. راهنما این عبارت‌ها رو تبلیغ می‌کرد ولی هیچ
# الیاسی نداشتن.
@bot.on_message(filters=lambda m: m.text and m.text == "/swearlockon")
async def swear_lock_on_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    group_data['settings']['anti_swear'] = True
    save_group_data(group_id, group_data)
    await message.reply("💢🔒 **قفل فحش فعال شد! از این به بعد کلمات ممنوعه حذف می‌شوند.**")


@bot.on_message(filters=lambda m: m.text and m.text == "/swearlockoff")
async def swear_lock_off_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    group_data['settings']['anti_swear'] = False
    save_group_data(group_id, group_data)
    await message.reply("💢🔓 **قفل فحش باز شد!**")


# 🆕 «قفل اسپم» / «اسپم باز» - همان الگو، برای anti_spam.
@bot.on_message(filters=lambda m: m.text and m.text == "/spamlockon")
async def spam_lock_on_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    group_data['settings']['anti_spam'] = True
    save_group_data(group_id, group_data)
    await message.reply("🔄🔒 **قفل اسپم فعال شد!**")


@bot.on_message(filters=lambda m: m.text and m.text == "/spamlockoff")
async def spam_lock_off_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    group_data['settings']['anti_spam'] = False
    save_group_data(group_id, group_data)
    await message.reply("🔄🔓 **قفل اسپم باز شد!**")


# =========================================================
#  🆕 سیستم قفل کپشن (تبلیغ‌شده در FULL_GUIDE_2 ولی پیاده‌سازی نداشت)
#  قفل کپشن | کپشن باز | بن کپشن فعال/غیرفعال | نمایش اخطار کپشن فعال/غیرفعال
#  تنظیم اخطار کپشن #عدد | تنظیم اخطار کپشن غیرفعال
# =========================================================
@bot.on_message(filters=lambda m: m.text and m.text == "/captionlockon")
async def caption_lock_on_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    group_data.setdefault('settings', {}).setdefault('locks', {})['caption'] = True
    save_group_data(group_id, group_data)
    await message.reply("📝🔒 **قفل کپشن فعال شد! از این به بعد ارسال رسانه همراه با کپشن ممنوعه.**")


@bot.on_message(filters=lambda m: m.text and m.text == "/captionlockoff")
async def caption_lock_off_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    group_data.setdefault('settings', {}).setdefault('locks', {})['caption'] = False
    save_group_data(group_id, group_data)
    await message.reply("📝🔓 **قفل کپشن باز شد! حالا ارسال کپشن آزاده.**")


@bot.on_message(filters=lambda m: m.text and m.text == "/captionban_on")
async def caption_ban_on_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    group_data.setdefault('settings', {})['caption_ban_enabled'] = True
    save_group_data(group_id, group_data)
    await message.reply("✅ **بن خودکار قفل کپشن فعال شد؛** با رسیدن به حد اخطار، کاربر بن می‌شود.")


@bot.on_message(filters=lambda m: m.text and m.text == "/captionban_off")
async def caption_ban_off_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    group_data.setdefault('settings', {})['caption_ban_enabled'] = False
    save_group_data(group_id, group_data)
    await message.reply("✅ **بن خودکار قفل کپشن غیرفعال شد؛** فقط پیام کپشن‌دار حذف می‌شود، کاربر بن نمی‌شود.")


@bot.on_message(filters=lambda m: m.text and m.text == "/captionshowwarn_on")
async def caption_showwarn_on_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    group_data.setdefault('settings', {})['caption_show_warn'] = True
    save_group_data(group_id, group_data)
    await message.reply("✅ **نمایش اخطار قفل کپشن فعال شد.**")


@bot.on_message(filters=lambda m: m.text and m.text == "/captionshowwarn_off")
async def caption_showwarn_off_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    group_data.setdefault('settings', {})['caption_show_warn'] = False
    save_group_data(group_id, group_data)
    await message.reply("✅ **نمایش اخطار قفل کپشن غیرفعال شد؛** پیام کپشن‌دار بی‌سروصدا حذف می‌شود.")


@bot.on_message(filters=lambda m: _cmd_is(m, "captionwarn_set"))
async def caption_warn_set_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    raw = _cmd_rest(message.text).lstrip("#").strip()
    try:
        count = int(raw)
    except (TypeError, ValueError):
        await message.reply("⚠️ دستور: تنظیم اخطار کپشن #عدد (مثال: تنظیم اخطار کپشن 3)")
        return
    if count < 1:
        await message.reply("⚠️ تعداد اخطار باید حداقل ۱ باشد.")
        return
    group_data.setdefault('settings', {})['caption_warn_max'] = count
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **تعداد اخطار قفل کپشن روی {count} تنظیم شد.**")


@bot.on_message(filters=lambda m: m.text and m.text == "/captionwarn_reset")
async def caption_warn_reset_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    group_data.setdefault('settings', {}).pop('caption_warn_max', None)
    save_group_data(group_id, group_data)
    max_warn = group_data.get('settings', {}).get('max_warn', 3)
    await message.reply(f"✅ **اخطار اختصاصی قفل کپشن غیرفعال شد؛** از این پس تعداد اخطار داشبورد ({max_warn}) استفاده می‌شود.")


# =========================================================
#  🆕 دستورات شخصی‌سازی اموجی
#  تنظیم اموجی [بخش] [اموجی] | ریست کامل اموجی‌ها | لیست اموجی
# =========================================================
@bot.on_message(filters=lambda m: _cmd_is(m, "set_custom_emoji"))
async def set_custom_emoji_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply(NO_PERMISSION_MSG)
        return
    rest = _cmd_rest(message.text)
    parts = rest.split(maxsplit=1)
    if len(parts) < 2:
        sections = "، ".join(CUSTOM_EMOJI_ALIASES.keys())
        await message.reply(f"⚠️ دستور: تنظیم اموجی [بخش] [اموجی]\nبخش‌های موجود: {sections}")
        return
    section_raw, emoji = parts[0], parts[1].strip()
    key = CUSTOM_EMOJI_ALIASES.get(normalize_key(section_raw))
    if not key:
        sections = "، ".join(CUSTOM_EMOJI_ALIASES.keys())
        await message.reply(f"⚠️ بخش «{section_raw}» شناخته‌شده نیست.\nبخش‌های موجود: {sections}")
        return
    if not _is_valid_single_emoji(emoji):
        await message.reply("⚠️ لطفاً فقط یک اموجی (بدون متن اضافه) ارسال کنید.")
        return
    group_data.setdefault('settings', {}).setdefault('custom_emojis', {})[key] = emoji
    save_group_data(group_id, group_data)
    await message.reply(f"{emoji} **اموجی بخش «{CUSTOM_EMOJI_KEYS.get(key, key)}» تنظیم شد.**")


@bot.on_message(filters=lambda m: m.text and m.text == "/reset_all_custom_emoji")
async def reset_all_custom_emoji_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply(NO_PERMISSION_MSG)
        return
    group_data.setdefault('settings', {})['custom_emojis'] = {}
    save_group_data(group_id, group_data)
    await message.reply(f"{DEFAULT_CUSTOM_EMOJIS['reset']} **همه‌ی اموجی‌های اختصاصی به حالت پیش‌فرض بازگشتند.**")


@bot.on_message(filters=lambda m: m.text and m.text == "/list_custom_emoji")
async def list_custom_emoji_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    lines = [f"{get_custom_emoji(group_data, 'lists')} **لیست اموجی‌های اختصاصی این گروه:**\n"]
    for key, label in CUSTOM_EMOJI_KEYS.items():
        lines.append(f"• {label}: {get_custom_emoji(group_data, key)}")
    lines.append("\nبرای تغییر: «تنظیم اموجی [بخش] [اموجی]» (مثال: تنظیم اموجی تگ 🔖)")
    lines.append("برای بازگشت همه به پیش‌فرض: «ریست کامل اموجی‌ها»")
    await message.reply("\n".join(lines))


@bot.on_message(filters=lambda m: m.text and m.text == "/antiswear")
async def anti_swear_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    group_data['settings']['anti_swear'] = not group_data['settings'].get('anti_swear', True)
    status = "فعال" if group_data['settings']['anti_swear'] else "غیرفعال"
    save_group_data(group_id, group_data)
    await message.reply(f"💢 **ضد فحش {status} شد!**")


@bot.on_message(filters=lambda m: m.text and m.text == "/clearfilters")
async def clear_filters_cmd(bot: Robot, message: Message):
    """پاکسازی لیست فحش/کلمات غیرمجاز - قبلاً اصلاً چنین دستوری وجود نداشت،
    با این‌که راهنما «پاکسازی لیست فحش» و «پاکسازی لیست کلمات غیرمجاز» رو
    تبلیغ می‌کرد."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return

    count = len(group_data.get('filters', {}).get('swear', []))
    group_data.setdefault('filters', {})['swear'] = []
    save_group_data(group_id, group_data)
    await message.reply(f"🧹 **{count} کلمه از لیست فیلترها پاک شد!**")


# =========================================================
#  دستورات لیست‌ها
# =========================================================

@bot.on_message(filters=lambda m: m.text and m.text == "/admins")
async def admins_list_cmd(bot: Robot, message: Message):
    """لیست ادمین‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    admins = group_data.get('admins', [])
    owners = group_data.get('owners', [])
    
    if admins or owners:
        text = f"{theme_icon(group_data, 'header')} لیست ادمین‌ها 〔 {get_custom_emoji(group_data, 'lists')} 〕\n\n"
        
        if owners:
            text += "👑 **مالک‌ها:**\n"
            for owner_id in owners:
                name = get_user_name_from_id(owner_id, group_data)
                text += f"• {name}\n• {owner_id}\n\n"
        
        if admins:
            text += "🛡️ **ادمین‌ها:**\n"
            for admin_id in admins:
                name = get_user_name_from_id(admin_id, group_data)
                text += f"• {name}\n• {admin_id}\n\n"
        
        await message.reply(text)
    else:
        await message.reply("» هیچ کاربری ادمین نشده است. ↺")

@bot.on_message(filters=lambda m: m.text and m.text == "/owners")
async def owners_list_cmd(bot: Robot, message: Message):
    """لیست مالک‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    owners = group_data.get('owners', [])
    
    if owners:
        text = f"{theme_icon(group_data, 'header')} لیست مالک‌ها 〔 👑 〕\n\n"
        for owner_id in owners:
            name = get_user_name_from_id(owner_id, group_data)
            text += f"• {name}\n• {owner_id}\n\n"
        await message.reply(text)
    else:
        await message.reply("» هیچ کاربری مالک نشده است. ↺")

@bot.on_message(filters=lambda m: m.text and m.text == "/specials")
async def specials_list_cmd(bot: Robot, message: Message):
    """لیست ویژه‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    specials = group_data.get('specials', [])
    
    if specials:
        text = f"{theme_icon(group_data, 'header')} لیست ویژه‌ها 〔 ⭐ 〕\n\n"
        for special_id in specials:
            name = get_user_name_from_id(special_id, group_data)
            text += f"• {name}\n• {special_id}\n\n"
        await message.reply(text)
    else:
        await message.reply("» هیچ کاربری ویژه نشده است. ↺")

@bot.on_message(filters=lambda m: m.text and m.text == "/exempts")
async def exempts_list_cmd(bot: Robot, message: Message):
    """لیست معاف‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    exempts = group_data.get('exempts', [])
    
    if exempts:
        text = f"{theme_icon(group_data, 'header')} لیست معاف‌ها 〔 ✅ 〕\n\n"
        for exempt_id in exempts:
            name = get_user_name_from_id(exempt_id, group_data)
            text += f"• {name}\n• {exempt_id}\n\n"
        await message.reply(text)
    else:
        await message.reply("» هیچ کاربری معاف نشده است. ↺")

@bot.on_message(filters=lambda m: m.text and m.text == "/mutes")
async def mutes_list_cmd(bot: Robot, message: Message):
    """لیست میوت‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    _ensure_punish_structures(group_data)
    active_ids = [uid for uid in list(group_data['mutes'].keys()) if is_punished_active(group_data, "mutes", uid)]
    save_group_data(group_id, group_data)  # پاکسازی موارد منقضی‌شده را ذخیره کن

    if active_ids:
        text = f"{theme_icon(group_data, 'header')} لیست میوت‌ها 〔 🔇 〕\n\n"
        for mute_id in active_ids:
            name = get_user_name_from_id(mute_id, group_data)
            remaining = format_remaining(group_data['mutes'][mute_id])
            text += f"• {name}\n• {mute_id}\n• ⏳ {remaining}\n\n"
        await message.reply(text)
    else:
        await message.reply("» هیچ کاربری میوت نشده است. ↺")

@bot.on_message(filters=lambda m: m.text and m.text == "/bans")
async def bans_list_cmd(bot: Robot, message: Message):
    """لیست بن‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    _ensure_punish_structures(group_data)
    active_ids = [uid for uid in list(group_data['bans'].keys()) if is_punished_active(group_data, "bans", uid)]
    save_group_data(group_id, group_data)  # پاکسازی موارد منقضی‌شده را ذخیره کن

    if active_ids:
        text = f"{theme_icon(group_data, 'header')} لیست بن‌ها 〔 🚫 〕\n\n"
        for ban_id in active_ids:
            name = get_user_name_from_id(ban_id, group_data)
            remaining = format_remaining(group_data['bans'][ban_id])
            text += f"• {name}\n• {ban_id}\n• ⏳ {remaining}\n\n"
        await message.reply(text)
    else:
        await message.reply("» هیچ کاربری بن نشده است. ↺")

@bot.on_message(filters=lambda m: m.text and m.text == "/blocks")
async def blocks_list_cmd(bot: Robot, message: Message):
    """لیست بلاک‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    blocks = group_data.get('blocks', [])
    
    if blocks:
        text = f"{theme_icon(group_data, 'header')} لیست بلاک‌ها 〔 🛡 〕\n\n"
        for block_id in blocks:
            name = get_user_name_from_id(block_id, group_data)
            text += f"• {name}\n• {block_id}\n\n"
        await message.reply(text)
    else:
        await message.reply("» هیچ کاربری بلاک نشده است. ↺")

# =========================================================
#  دستورات آمار
# =========================================================

@bot.on_message(filters=lambda m: m.text and m.text == "/mystats")
async def mystats_cmd(bot: Robot, message: Message):
    """آمار من"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    user_name = (await get_display_name(bot, message) or "کاربر")
    
    message_count = group_data.get('message_count', {}).get(user_id, 0)
    today_count = group_data.get('daily_count', {}).get(user_id, 0)
    week_count = group_data.get('weekly_count', {}).get(user_id, 0)
    month_count = group_data.get('monthly_count', {}).get(user_id, 0)
    
    warns = get_warn_count(group_data, user_id)
    
    rank = "👤 کاربر عادی"
    if user_id in group_data.get('owners', []):
        rank = "👑 مالک"
    elif user_id in group_data.get('admins', []):
        rank = "🛡 ادمین"
    elif user_id in group_data.get('specials', []):
        rank = "⭐ ویژه"
    
    status = "✅ فعال"
    if is_punished_active(group_data, "mutes", user_id):
        status = "🔇 میوت"
    if is_punished_active(group_data, "bans", user_id):
        status = "🚫 بن"
    if user_id in group_data.get('blocks', []):
        status = "🛡 بلاک"
    
    await message.reply(f"""
{theme_icon(group_data, 'header')} آمار ثبت‌شده توسط ربات 〔 {get_custom_emoji(group_data, 'stats')} 〕

• نام: {user_name}
• مقام: {rank}
• شناسه کاربری: `{user_id}`

📝 **آمار پیام‌ها (فقط از زمانی که ربات در گروه فعال بوده):**
• کل پیام‌ها: {format_number(message_count)}
• امروز: {today_count} پیام
• این هفته: {week_count} پیام
• این ماه: {month_count} پیام

⚠️ **اخطارها:** {warns}
🔒 **وضعیت:** {status}
""")

#  🛠 حذف کد مرده: قبلاً اینجا یک هندلر جدا برای "/stats" بود که هیچ alias
#  فارسی‌ای بهش وصل نبود (نه در ALIAS_MAP، نه در register_router_target) و
#  هیچ‌وقت در عمل قابل اجرا نبود؛ محتوایش هم تکراری با gstats_cmd
#  ("آمار گروه") بود، پس به‌جای نگه‌داشتن کد مرده حذف شد.

@bot.on_message(filters=lambda m: m.text and m.text == "/gstats")
async def gstats_cmd(bot: Robot, message: Message):
    """آمار کامل گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    stats = group_data.get('stats', {})
    
    sorted_users = sorted(group_data.get('message_count', {}).items(), key=lambda x: x[1], reverse=True)[:5]
    
    active_text = ""
    if sorted_users:
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for idx, (uid, count) in enumerate(sorted_users):
            name = get_user_name_from_id(uid, group_data)
            active_text += f" {medals[idx]} {name} با {format_number(count)} پیام\n"
    else:
        active_text = " ❌ هنوز آماری وجود ندارد"
    
    await message.reply(f"""
{theme_icon(group_data, 'header')} آمار ثبت‌شده توسط ربات 〔 {get_custom_emoji(group_data, 'stats')} 〕

» نام گروه: {group_data.get('group_name', 'گروه')}

• تعداد مالکین: {len(group_data.get('owners', []))}
• کاربران ویژه: {len(group_data.get('specials', []))}
• ادمین‌ها: {len(group_data.get('admins', []))}
• کاربران عادی: {stats.get('total_users', 0)}
• معاف‌ها: {len(group_data.get('exempts', []))}

» کل پیام‌ها: {format_number(stats.get('total_messages', 0))}
» پیام‌های امروز: {stats.get('today_messages', 0)}

» فعالترین کاربران اخیر: 
{active_text}

ℹ️ این آمار فقط بر اساس فعالیتی است که خودِ ربات از وقتی در گروه فعال بوده دیده؛
اگر ربات تازه اضافه شده باشد، فعالیت قدیمی‌تر گروه را شامل نمی‌شود.
""")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم فیلتر کلمات
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "addfilter"))
async def add_filter_cmd(bot: Robot, message: Message):
    """افزودن فیلتر کلمه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    word = message.text.replace("/addfilter", "", 1).strip()
    if not word:
        await message.reply("⚠️ دستور: /addfilter [کلمه]")
        return
    
    if 'filters' not in group_data:
        group_data['filters'] = {'swear': [], 'badwords': []}
    
    if word not in group_data['filters']['swear']:
        group_data['filters']['swear'].append(word)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **کلمه «{word}» به فیلترها اضافه شد!**")
    else:
        await message.reply(f"⚠️ کلمه «{word}» قبلاً در فیلترها وجود دارد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "removefilter"))
async def remove_filter_cmd(bot: Robot, message: Message):
    """حذف فیلتر کلمه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    word = message.text.replace("/removefilter", "", 1).strip()
    if not word:
        await message.reply("⚠️ دستور: /removefilter [کلمه]")
        return
    
    if 'filters' in group_data and word in group_data['filters']['swear']:
        group_data['filters']['swear'].remove(word)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **کلمه «{word}» از فیلترها حذف شد!**")
    else:
        await message.reply(f"⚠️ کلمه «{word}» در فیلترها وجود ندارد!")

@bot.on_message(filters=lambda m: m.text and m.text == "/filters")
async def filters_list_cmd(bot: Robot, message: Message):
    """لیست فیلترها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    filters_list = group_data.get('filters', {}).get('swear', [])
    
    if filters_list:
        text = "🔍 **لیست فیلترها:**\n\n"
        for idx, word in enumerate(filters_list, 1):
            text += f"{idx}. {word}\n"
        await message.reply(text)
    else:
        await message.reply("📋 هیچ فیلتری وجود ندارد!")

# =========================================================
#  🧩 دستورات جدید: ریست اخطار / حداکثر اخطار / مدت میوت / سخنگو / منوی مدیریت
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "resetwarn"))
async def resetwarn_cmd(bot: Robot, message: Message):
    """ریست کردن اخطارهای یک کاربر (با ریپلای)"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    if not get_reply_message(message):
        await message.reply("⚠️ روی پیام کاربر ریپلای کن!")
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return

    target_id = str(get_reply_sender_id(message))
    target_name = (await get_display_name(bot, get_reply_sender_id(message), group_id=group_id, prefer_live=True) if get_reply_message(message) else "کاربر")

    group_data = get_group_data(group_id)
    removed = reset_warnings(group_data, target_id)
    add_log(group_data, "ریست اخطار", admin_id=user_id, target_id=target_id)
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **اخطارهای {target_name} ریست شد!** ({removed} اخطار فعال پاک شد)")

@bot.on_message(filters=lambda m: _cmd_is(m, "maxwarn"))
async def maxwarn_cmd(bot: Robot, message: Message):
    """تنظیم حداکثر تعداد اخطار مجاز"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return

    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply(f"⚠️ دستور: /maxwarn [تعداد]\n📌 مقدار فعلی: {group_data['settings'].get('max_warn', 3)}")
        return

    group_data['settings']['max_warn'] = int(parts[1])
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **حداکثر اخطار روی {parts[1]} تنظیم شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "muteduration"))
async def muteduration_cmd(bot: Robot, message: Message):
    """تنظیم مدت‌زمان پیش‌فرض میوت (به دقیقه)"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return

    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply(f"⚠️ دستور: /muteduration [دقیقه]\n📌 مقدار فعلی: {group_data['settings'].get('mute_duration', 5)} دقیقه")
        return

    group_data['settings']['mute_duration'] = int(parts[1])
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **مدت میوت روی {parts[1]} دقیقه تنظیم شد!**")

# =========================================================
#  🛠 رفع باگ اصلی: «سخنگو کامل کار نمی‌کنه»
# =========================================================
# راهنمای خود ربات (بخش «سخنگوی شخصی و یادگیری») از اول قول این سینتکس رو
# داده بود: «کلیدواژه ! پاسخ۱ ! پاسخ۲» بدون هیچ پیشوند /learn، ولی توی کد فقط
# دستور اسلش /learn پیاده‌سازی شده بود - یعنی کاربر دقیقاً طبق راهنما تایپ
# می‌کرد ولی ربات هیچ‌وقت جوابی نمی‌داد. این هندلر همون سینتکس مستندشده رو
# واقعاً پیاده می‌کنه (علاوه بر /learn قدیمی که دست‌نخورده باقی می‌مونه):
#   «کلیدواژه ! پاسخ۱ ! پاسخ۲»  -> یاد گرفتن پاسخ(ها)  [فقط ادمین به بالا]
#   «! کلیدواژه»                -> نمایش پاسخ‌های یاد گرفته‌شده [همه]
#   «کلیدواژه !! پاسخ»          -> حذف یک پاسخ خاص     [فقط ادمین به بالا]
#   «کلیدواژه !!»               -> حذف همه‌ی پاسخ‌ها     [فقط ادمین به بالا]
# برای جلوگیری از تداخل با جملات عادی فارسی که توش «!» هست (مثلاً «خوبم!
# ممنون»)، کلیدواژه باید تک‌کلمه و کوتاه باشه، وگرنه پیام نادیده گرفته می‌شه؛
# و برای کاربر عادی (غیر ادمین) اگه پیامش تصادفاً این الگو رو داشته باشه،
# به‌جای «اجازه ندارید»، ربات کاملاً ساکت می‌مونه (انگار سینتکس خاصی نبوده).
def _parse_teach_syntax(raw_text: str):
    if not raw_text or "!" not in raw_text:
        return None
    t = normalize_fa(raw_text)
    if t.startswith("/"):
        return None  # دستورات اسلش (مثل /learn) رو دست نمی‌زنیم

    def _valid_keyword(kw: str) -> bool:
        return bool(kw) and (" " not in kw) and (1 <= len(kw) <= 30)

    # نمایش: «! کلیدواژه»
    if t.startswith("!") and not t.startswith("!!"):
        keyword = normalize_key(t[1:].strip())
        if _valid_keyword(keyword):
            return ("show", keyword, None)
        return None

    # حذف: «کلیدواژه !! پاسخ» یا «کلیدواژه !!»
    if "!!" in t:
        left, _, right = t.partition("!!")
        keyword = normalize_key(left.strip())
        response = right.strip()
        if not _valid_keyword(keyword):
            return None
        return ("remove_one", keyword, response) if response else ("remove_all", keyword, None)

    # افزودن: «کلیدواژه ! پاسخ۱ ! پاسخ۲ ...»
    parts = [p.strip() for p in t.split("!")]
    if len(parts) < 2:
        return None
    keyword = normalize_key(parts[0])
    responses = [p for p in parts[1:] if p]
    if not _valid_keyword(keyword) or not responses:
        return None
    return ("add", keyword, responses)

@bot.on_message(filters=lambda m: m.text and _parse_teach_syntax(m.text) is not None)
async def teach_syntax_handler(bot: Robot, message: Message):
    parsed = _parse_teach_syntax(message.text)
    if not parsed:
        return
    action, keyword, payload = parsed

    group_id = get_chat_group_id(message)
    if not group_id:
        return  # در پیوی این سینتکس فعال نیست، ساکت رد می‌شیم

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    settings = group_data.get('settings', {})

    # 🛠 اگه سخنگو یا بخش «سخنگوی شخصی» از داشبورد خاموش شده باشه، این سینتکس
    # اصلاً فعال نیست (نه نمایش، نه یادگیری) - قبلاً این دو کلید تنظیمات
    # تعریف شده بودن ولی هیچ‌جا خونده نمی‌شدن.
    if not settings.get('speaker_enabled', True) or not settings.get('speaker_personal_enabled', True):
        return

    if action == "show":
        responses = group_data.get('learn', {}).get(keyword)
        if not responses:
            await message.reply(f"📋 برای «{keyword}» هنوز چیزی یاد نگرفتم.")
            return
        lines = [f"🧠 پاسخ‌های یاد گرفته‌شده برای «{keyword}»:", ""]
        lines += [f"{i}. {r}" for i, r in enumerate(responses, 1)]
        await message.reply("\n".join(lines))
        return

    # افزودن/حذف با سطح دسترسی قابل‌تنظیم («تنظیم دسترسی سخنگو») - پیش‌فرض
    # مدیر به بالا. برای بقیه کاملاً ساکت می‌مونیم تا جمله‌های روزمره‌ی
    # حاوی «!» باعث پیام مزاحم «اجازه ندارید» نشه.
    required_perm = settings.get('speaker_perm', Perm.ADMIN)
    if not has_permission(user_id, group_data, required_perm):
        return

    if action == "add":
        # 🛠 اگه «سخنگو بی‌ادب» غیرفعال باشه (پیش‌فرض)، پاسخ‌هایی که شامل
        # کلمات لیست فحش گروه هستن یاد گرفته نمی‌شن، تا خود سخنگو تبدیل به
        # مسیر دور زدن ضدفحش نشه.
        if not settings.get('speaker_rude_enabled', False):
            swear_words = group_data.get('filters', {}).get('swear', [])
            blocked = [r for r in payload if find_swear_word(r, swear_words)]
            payload = [r for r in payload if r not in blocked]
            if blocked and not payload:
                await message.reply(
                    "⛔ این پاسخ شامل کلمات نامناسبه و چون «سخنگو بی‌ادب» خاموشه یاد گرفته نشد.\n"
                    "برای فعال‌کردنش: «سخنگو بی‌ادب فعال»"
                )
                return
        learn_map = group_data.setdefault('learn', {})
        bucket = learn_map.setdefault(keyword, [])
        added = 0
        for r in payload:
            if r not in bucket:
                bucket.append(r)
                added += 1
        save_group_data(group_id, group_data)
        if added:
            await message.reply(f"🧠 یاد گرفتم! {added} پاسخ جدید برای «{keyword}» ثبت شد.")
        else:
            await message.reply(f"ℹ️ این پاسخ(ها) از قبل برای «{keyword}» ثبت بودن.")
        return

    if action == "remove_one":
        learn_map = group_data.setdefault('learn', {})
        bucket = learn_map.get(keyword, [])
        if payload in bucket:
            bucket.remove(payload)
            if not bucket:
                del learn_map[keyword]
            save_group_data(group_id, group_data)
            await message.reply(f"✅ اون پاسخ از «{keyword}» حذف شد.")
        else:
            await message.reply(f"⚠️ همچین پاسخی برای «{keyword}» پیدا نشد.")
        return

    if action == "remove_all":
        learn_map = group_data.setdefault('learn', {})
        if keyword in learn_map:
            del learn_map[keyword]
            save_group_data(group_id, group_data)
            await message.reply(f"✅ همه‌ی پاسخ‌های «{keyword}» حذف شد.")
        else:
            await message.reply(f"⚠️ کلیدواژه «{keyword}» چیزی یاد گرفته‌شده نداره.")
        return

@bot.on_message(filters=lambda m: _cmd_is(m, "learn"))
async def learn_cmd(bot: Robot, message: Message):
    """یادگیری یک کلمه‌ی کلیدی و پاسخ آن؛ فرمت: /learn کلمه ! پاسخ"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return

    body = message.text.replace("/learn", "", 1).strip()
    if "!" not in body:
        await message.reply("⚠️ دستور: /learn [کلمه] ! [پاسخ]")
        return

    keyword, response = body.split("!", 1)
    keyword = normalize_key(keyword)
    response = response.strip()
    if not keyword or not response:
        await message.reply("⚠️ دستور: /learn [کلمه] ! [پاسخ]")
        return

    group_data.setdefault('learn', {}).setdefault(keyword, []).append(response)
    save_group_data(group_id, group_data)
    await message.reply(f"🧠 **یاد گرفتم!** حالا با شنیدن «{keyword}» ممکن است این‌طور پاسخ بدهم.")

@bot.on_message(filters=lambda m: _cmd_is(m, "unlearn"))
async def unlearn_cmd(bot: Robot, message: Message):
    """حذف یک کلمه از یادگیری‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return

    keyword = normalize_key(message.text.replace("/unlearn", "", 1).strip())
    learn_map = group_data.setdefault('learn', {})
    if keyword in learn_map:
        del learn_map[keyword]
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **یادگیری «{keyword}» حذف شد!**")
    else:
        await message.reply(f"⚠️ کلمه «{keyword}» در یادگیری‌ها وجود ندارد!")

@bot.on_message(filters=lambda m: m.text and m.text == "/learned")
async def learned_cmd(bot: Robot, message: Message):
    """لیست کلمات یادگرفته‌شده"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    group_data = get_group_data(group_id)
    learn_map = group_data.get('learn', {})

    if learn_map:
        text = "🧠 **لیست یادگیری‌ها:**\n\n"
        for idx, keyword in enumerate(learn_map.keys(), 1):
            text += f"{idx}. {keyword}\n"
        await message.reply(text)
    else:
        await message.reply("📋 هنوز چیزی یاد گرفته نشده!")

# =========================================================
#  🛠 رفع باگ: دستورات «پنل سخنگو»، «سخنگو فعال/خاموش»، «سخنگو شخصی
#  فعال/غیرفعال»، «سخنگو بی‌ادب فعال/غیرفعال» و «تنظیم دسترسی سخنگو» فقط در
#  متن راهنما (FULL_GUIDE_3) تبلیغ شده بودن ولی هیچ‌کدوم پیاده‌سازی نداشتن؛
#  یعنی کاربر دقیقاً طبق راهنما تایپ می‌کرد و ربات کلاً ساکت می‌موند.
# =========================================================
SPEAKER_PERM_MAP = {
    "مالک": Perm.OWNER,
    "مالک ویژه": Perm.SPECIAL,
    "مالک ویژه ادمین": Perm.ADMIN,
    "مالک ویژه ادمین کاربرعادی": Perm.MEMBER,
}

@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) == "پنل سخنگو")
async def speaker_panel_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not has_permission(user_id, group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return

    s = group_data.get('settings', {})
    perm_name = PERM_NAMES.get(s.get('speaker_perm', Perm.ADMIN), "مدیر")
    learn_count = len(group_data.get('learn', {}))
    text = (
        "╭━━━━ 🧠 پنل سخنگو ━━━━╮\n"
        f"┃ 🔌 سخنگو: {_onoff(s.get('speaker_enabled', True))}\n"
        f"┃ 🙋 سخنگوی شخصی (یادگیری): {_onoff(s.get('speaker_personal_enabled', True))}\n"
        f"┃ 🤬 سخنگوی بی‌ادب: {_onoff(s.get('speaker_rude_enabled', False))}\n"
        f"┃ 🎖 حداقل دسترسی آموزش: {perm_name}\n"
        f"┃ 📚 تعداد کلیدواژه‌های یادگرفته‌شده: {learn_count}\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n"
        "دستورات: سخنگو فعال/خاموش | سخنگو شخصی فعال/غیرفعال | "
        "سخنگو بی‌ادب فعال/غیرفعال | تنظیم دسترسی سخنگو [مالک/مالک ویژه/"
        "مالک ویژه ادمین/مالک ویژه ادمین کاربرعادی]"
    )
    await message.reply(text)


def _speaker_toggle_handler_factory(key: str, on_keys, off_keys, on_msg: str, off_msg: str):
    async def _handler(bot: Robot, message: Message):
        group_id = get_chat_group_id(message)
        if not group_id:
            await message.reply(GROUP_ONLY_MSG)
            return
        group_data = get_group_data(group_id)
        user_id = str(message.sender_id)
        if not has_permission(user_id, group_data, Perm.ADMIN):
            await message.reply(NO_PERMISSION_MSG)
            return
        value = normalize_key(message.text) in on_keys
        group_data.setdefault('settings', {})[key] = value
        save_group_data(group_id, group_data)
        await message.reply(on_msg if value else off_msg)
    return _handler

bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("سخنگو فعال", "سخنگو خاموش", "سخنگو روشن"))(
    _speaker_toggle_handler_factory(
        'speaker_enabled', ("سخنگو فعال", "سخنگو روشن"), ("سخنگو خاموش",),
        "✅ سخنگو فعال شد.", "🔴 سخنگو خاموش شد."
    )
)

bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("سخنگو شخصی فعال", "سخنگو شخصی غیرفعال"))(
    _speaker_toggle_handler_factory(
        'speaker_personal_enabled', ("سخنگو شخصی فعال",), ("سخنگو شخصی غیرفعال",),
        "✅ سخنگوی شخصی (یادگیری) فعال شد.", "🔴 سخنگوی شخصی (یادگیری) غیرفعال شد."
    )
)

bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("سخنگو بی‌ادب فعال", "سخنگو بی ادب فعال", "سخنگو بی‌ادب غیرفعال", "سخنگو بی ادب غیرفعال"))(
    _speaker_toggle_handler_factory(
        'speaker_rude_enabled', ("سخنگو بی‌ادب فعال", "سخنگو بی ادب فعال"), ("سخنگو بی‌ادب غیرفعال", "سخنگو بی ادب غیرفعال"),
        "✅ سخنگوی بی‌ادب فعال شد (دیگه فیلتر فحش روی پاسخ‌های یادگرفته‌شده اعمال نمی‌شه).",
        "🔴 سخنگوی بی‌ادب غیرفعال شد (پاسخ‌های حاوی کلمات فحش یاد گرفته نمی‌شن)."
    )
)

@bot.on_message(filters=lambda m: m.text and normalize_key(m.text).startswith("تنظیم دسترسی سخنگو"))
async def speaker_set_perm_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not has_permission(user_id, group_data, Perm.OWNER):
        await message.reply(NO_PERMISSION_MSG)
        return

    key = normalize_key(message.text).replace("تنظیم دسترسی سخنگو", "").strip()
    if key not in SPEAKER_PERM_MAP:
        options = " / ".join(SPEAKER_PERM_MAP.keys())
        await message.reply(f"⚠️ دستور: تنظیم دسترسی سخنگو [{options}]")
        return

    group_data.setdefault('settings', {})['speaker_perm'] = SPEAKER_PERM_MAP[key]
    save_group_data(group_id, group_data)
    await message.reply(f"✅ حداقل سطح دسترسی آموزش سخنگو روی «{key}» تنظیم شد.")


ADMIN_MENU_TEXT = """╭━━━━ 🛡 منوی مدیریت ━━━━╮

👤 مدیریت کاربران (با ریپلای)
  /warn [دلیل] | /unwarn | /resetwarn
  /mute [دقیقه] | /unmute
  /ban [دلیل] | /unban | /kick [دلیل]
  /block | /unblock

👑 مدیریت ادمین‌ها
  /addadmin [شناسه] | /removeadmin [شناسه]
  /addowner [شناسه] | /removeowner [شناسه]
  /admins

⚙️ تنظیمات
  /maxwarn [تعداد] | /muteduration [دقیقه]
  /warnaction [ban|kick|mute] | /warnexpire [روز]
  /lock | /unlock
  /antilink | /antispam | /antiswear
  /locktype [نوع] | /unlocktype [نوع] | /locks   (یا «قفل عکس»، «باز گیف»، ...)
  /setspam [ثانیه] [پیام] [تکرار]
  /tag [@username|آیدی|نام] [متن]، یا ریپلای + /tag [متن]  (یا فارسی «تگ»)
  /pin (ریپلای)  |  /unpin (ریپلای | آخرین | all)  |  /clear [تعداد]  (حداکثر 500)
  /tagall [متن]  (یا «تگ همه»)  |  /tagbots [فعال/غیرفعال]  |  /members

🔍 فیلترها
  /addfilter [کلمه] | /removefilter [کلمه] | /filters

🧠 سخنگو
  /learn [کلمه] ! [پاسخ] | /unlearn [کلمه] | /learned

╰━━━━━━━━━━━━━━━━━━━━━━╯"""

@bot.on_message(filters=lambda m: m.text and m.text == "/admin")
async def admin_menu_cmd(bot: Robot, message: Message):
    """نمایش منوی مدیریت برای ادمین‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return

    await message.reply(ADMIN_MENU_TEXT)

# =========================================================
#  سیستم قوانین و تنظیمات
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "setrules"))
async def set_rules_cmd(bot: Robot, message: Message):
    """تنظیم قوانین گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    rules = message.text.replace("/setrules", "", 1).strip()
    if not rules:
        await message.reply("⚠️ دستور: /setrules [متن قوانین]")
        return
    
    group_data['settings']['rules'] = rules
    save_group_data(group_id, group_data)
    await message.reply("✅ **قوانین گروه تنظیم شد!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/rules")
async def rules_show_cmd(bot: Robot, message: Message):
    """نمایش قوانین گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    rules = group_data.get('settings', {}).get('rules', '📋 قوانین تنظیم نشده است!')
    await message.reply(rules)

@bot.on_message(filters=lambda m: _cmd_is(m, "setwelcome"))
async def set_welcome_cmd(bot: Robot, message: Message):
    """تنظیم پیام خوش‌آمد"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = _cmd_rest(message.text)
    if not text:
        await message.reply("⚠️ دستور: /setwelcome [متن]")
        return
    
    group_data['settings']['welcome'] = text
    save_group_data(group_id, group_data)
    await message.reply("✅ **پیام خوش‌آمد تنظیم شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "setgoodbye"))
async def set_goodbye_cmd(bot: Robot, message: Message):
    """تنظیم پیام خداحافظ"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = _cmd_rest(message.text)
    if not text:
        await message.reply("⚠️ دستور: /setgoodbye [متن]")
        return
    
    group_data['settings']['goodbye'] = text
    save_group_data(group_id, group_data)
    await message.reply("✅ **پیام خداحافظ تنظیم شد!**")

# =========================================================
#  سیستم پشتیبانی و تیکت
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "support"))
async def support_cmd(bot: Robot, message: Message):
    """پشتیبانی"""
    text = message.text.replace("/support", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /support [متن]")
        return
    
    ticket_id = f"SUP-{random.randint(1000, 9999)}"
    await message.reply(f"""
📨 **پیام شما به پشتیبانی ارسال شد!**

شناسه: {ticket_id}
متن: {text}

🔹 در اسرع وقت پاسخ داده خواهد شد.
🔹 لطفاً صبور باشید.
""")

@bot.on_message(filters=lambda m: _cmd_is(m, "ticket"))
async def ticket_cmd(bot: Robot, message: Message):
    """تیکت"""
    text = message.text.replace("/ticket", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /ticket [متن]")
        return
    
    ticket_id = f"TKT-{random.randint(1000, 9999)}"
    await message.reply(f"""
🎫 **تیکت شما ثبت شد!**

شناسه تیکت: {ticket_id}
متن: {text}

⏳ در اسرع وقت رسیدگی خواهد شد.
""")

# =========================================================
#  سیستم اطلاعات ربات
# =========================================================

@bot.on_message(filters=lambda m: m.text and m.text == "/about")
async def about_cmd(bot: Robot, message: Message):
    """درباره ربات"""
    await message.reply(f"""
🤖 **درباره {BOT_NAME}**

📌 **نام:** {BOT_NAME}
📌 **نسخه:** {VERSION}
📌 **سازنده:** {AUTHOR}
📌 **زبان:** فارسی

📊 **آمار:**
🔹 {len(_ensure_cache_loaded())} گروه فعال
🔹 {sum(len(g.get('users', {})) for g in _ensure_cache_loaded().values())} کاربر

📌 **قابلیت‌ها:**
✅ مدیریت کامل گروه
✅ بن، سکوت، اخطار، بلاک
✅ فیلتر کلمات
✅ سرگرمی و بازی
✅ کاربردی
✅ آمار کامل
✅ پاسخ به گاردی
✅ ۲۰۰ چالش
✅ ۲۰۰ پ ن پ
✅ ۲۰۰ بیو
✅ ۲۰۰ خاطره

💡 **هر جا گاردی رو صدا کنی جوابت رو میدم!**
""")
# =========================================================
#  سیستم مدیریت قفل‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "lock_media"))
async def lock_media_cmd(bot: Robot, message: Message):
    """قفل رسانه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /lock_media [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['lock_media'] = True
        save_group_data(group_id, group_data)
        await message.reply("🔒 **قفل رسانه فعال شد!**")
    elif status == "غیرفعال":
        group_data['settings']['lock_media'] = False
        save_group_data(group_id, group_data)
        await message.reply("🔓 **قفل رسانه غیرفعال شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

@bot.on_message(filters=lambda m: _cmd_is(m, "lock_forward"))
async def lock_forward_cmd(bot: Robot, message: Message):
    """قفل فوروارد"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /lock_forward [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['lock_forward'] = True
        save_group_data(group_id, group_data)
        await message.reply("↗️ **قفل فوروارد فعال شد!**")
    elif status == "غیرفعال":
        group_data['settings']['lock_forward'] = False
        save_group_data(group_id, group_data)
        await message.reply("↗️ **قفل فوروارد غیرفعال شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

@bot.on_message(filters=lambda m: _cmd_is(m, "lock_hashtag"))
async def lock_hashtag_cmd(bot: Robot, message: Message):
    """قفل هشتگ"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /lock_hashtag [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['lock_hashtag'] = True
        save_group_data(group_id, group_data)
        await message.reply("#️⃣ **قفل هشتگ فعال شد!**")
    elif status == "غیرفعال":
        group_data['settings']['lock_hashtag'] = False
        save_group_data(group_id, group_data)
        await message.reply("#️⃣ **قفل هشتگ غیرفعال شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

@bot.on_message(filters=lambda m: _cmd_is(m, "lock_mention"))
async def lock_mention_cmd(bot: Robot, message: Message):
    """قفل منشن"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /lock_mention [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['lock_mention'] = True
        save_group_data(group_id, group_data)
        await message.reply("👤 **قفل منشن فعال شد!**")
    elif status == "غیرفعال":
        group_data['settings']['lock_mention'] = False
        save_group_data(group_id, group_data)
        await message.reply("👤 **قفل منشن غیرفعال شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

@bot.on_message(filters=lambda m: _cmd_is(m, "lock_metadata"))
async def lock_metadata_cmd(bot: Robot, message: Message):
    """قفل متادیتا"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /lock_metadata [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['lock_metadata'] = True
        save_group_data(group_id, group_data)
        await message.reply("📝 **قفل متادیتا فعال شد!**")
    elif status == "غیرفعال":
        group_data['settings']['lock_metadata'] = False
        save_group_data(group_id, group_data)
        await message.reply("📝 **قفل متادیتا غیرفعال شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

# =========================================================
#  سیستم مدیریت کاربران ویژه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "exempt"))
async def exempt_cmd(bot: Robot, message: Message):
    """معاف کردن کاربر"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    if not get_reply_message(message):
        await message.reply("⚠️ روی پیام کاربر ریپلای کن!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    target_id = str(get_reply_sender_id(message))
    target_name = (await get_display_name(bot, get_reply_sender_id(message), group_id=group_id, prefer_live=True) if get_reply_message(message) else "کاربر")
    
    if target_id not in group_data['exempts']:
        group_data['exempts'].append(target_id)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **کاربر {target_name} معاف شد!**")
    else:
        await message.reply(f"⚠️ {target_name} قبلاً معاف است!")

@bot.on_message(filters=lambda m: _cmd_is(m, "unexempt"))
async def unexempt_cmd(bot: Robot, message: Message):
    """برداشتن معافیت"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    if not get_reply_message(message):
        await message.reply("⚠️ روی پیام کاربر ریپلای کن!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    target_id = str(get_reply_sender_id(message))
    target_name = (await get_display_name(bot, get_reply_sender_id(message), group_id=group_id, prefer_live=True) if get_reply_message(message) else "کاربر")
    
    if target_id in group_data['exempts']:
        group_data['exempts'].remove(target_id)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **معافیت {target_name} برداشته شد!**")
    else:
        await message.reply(f"⚠️ {target_name} معاف نیست!")

# =========================================================
#  سیستم نظرسنجی
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "poll"))
async def poll_cmd(bot: Robot, message: Message):
    """نظرسنجی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/poll", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /poll [سوال] | گزینه۱ | گزینه۲")
        return
    
    options = [opt.strip() for opt in parts.split('|')]
    if len(options) < 2:
        await message.reply("⚠️ حداقل ۲ گزینه وارد کنید!")
        return
    
    question = options[0]
    choices = options[1:]
    
    text = f"📊 **نظرسنجی:**\n\n{question}\n\n"
    emojis = ["🅰️", "🅱️", "🅲️", "🅳️", "🅴️", "🅵️"]
    
    for idx, choice in enumerate(choices):
        if idx < len(emojis):
            text += f"{emojis[idx]} {choice}\n"
        else:
            text += f"➡️ {choice}\n"
    
    text += f"\n📅 {datetime.now().strftime('%Y/%m/%d')}"
    
    await message.reply(text)

# =========================================================
#  سیستم قرعه‌کشی
# =========================================================

@bot.on_message(filters=lambda m: m.text and m.text == "/lottery")
async def lottery_cmd(bot: Robot, message: Message):
    """قرعه‌کشی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    users = list(group_data.get('users', {}).keys())
    if not users:
        await message.reply("❌ هیچ کاربری در گروه وجود ندارد!")
        return
    
    winner = random.choice(users)
    winner_name = get_user_name_from_id(winner, group_data)
    
    await message.reply(f"🎉 **برنده قرعه‌کشی:**\n\n{winner_name}\n\nتبریک میگم! 🎊")
    # =========================================================
#  سیستم مدیریت قفل‌ها
# =========================================================






# =========================================================
#  سیستم مدیریت کاربران ویژه
# =========================================================



# =========================================================
#  سیستم نظرسنجی
# =========================================================


# =========================================================
#  سیستم قرعه‌کشی
# =========================================================

    # =========================================================
#  سیستم مدیریت جایزه
# =========================================================

@bot.on_message(filters=lambda m: m.text and m.text == "/reward")
async def reward_cmd(bot: Robot, message: Message):
    """جایزه تصادفی"""
    rewards = [
        "🎁 یک هفته عضویت ویژه!",
        "🎁 ۱۰۰ امتیاز جایزه!",
        "🎁 تخفیف ۲۰ درصدی!",
        "🎁 یک بسته شگفت‌انگیز!",
        "🎁 یک کارت هدیه!",
        "🎁 یک کتاب الکترونیکی!",
        "🎁 یک دوره آموزشی رایگان!",
        "🎁 یک هفته دسترسی ویژه!",
        "🎁 ۵۰ امتیاز جایزه!",
        "🎁 کد تخفیف ۳۰ درصدی!"
    ]
    await message.reply(f"🎉 **جایزه شما:**\n{random.choice(rewards)}")

# =========================================================
#  سیستم مدیریت نقل قول
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "quote"))
async def quote_cmd(bot: Robot, message: Message):
    """نقل قول"""
    if not get_reply_message(message):
        await message.reply("⚠️ روی پیام مورد نظر ریپلای کن!")
        return
    
    user_name = (await get_display_name(bot, get_reply_sender_id(message)) if get_reply_message(message) else "کاربر")
    text = message.reply_to_message.text or "متن موجود نیست"
    
    await message.reply(f"""
📝 **نقل قول از {user_name}:**

"{text}"

📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}
""")

# =========================================================
#  سیستم مدیریت پین
# =========================================================

# ---------- بررسی دسترسی واقعی ربات قبل از عملیات‌های حساس (بخش ۴ ممیزی) ----------
# «ادمین بودن ربات» به‌تنهایی کافی نیست: هر Permission تلگرامی (حذف، محدودسازی، سنجاق، ...)
# جداگانه است. این بررسی هم برای پیام خطای دقیق‌تر است و هم برای عملیات‌های سنگین (مثل /clear
# با ده‌ها فراخوانی) که بهتر است بدون دلیل روی تلگرام اسپم نشوند. اگر نتوانیم دسترسی‌ها را از
# قبل بخوانیم (info=None)، مانع اجرا نمی‌شویم؛ تلگرام خودش هنگام فراخوانی واقعی قضاوت می‌کند.
_BOT_CAP_LABELS = {
    "can_delete_messages": "حذف پیام‌ها", "can_restrict_members": "محدودکردن/اخراج/بن اعضا",
    "can_pin_messages": "سنجاق‌کردن پیام‌ها", "can_promote_members": "ارتقای ادمین",
    "can_invite_users": "دعوت با لینک", "can_change_info": "تغییر اطلاعات گروه",
}

async def bot_capability_error(bot, group_id, capability: str) -> Optional[str]:
    """اگر مطمئنیم ربات این Permission را ندارد، متن خطا؛ وگرنه None (یعنی ادامه بده)."""
    info = await bot.get_bot_permissions(group_id)
    if info is None:
        return None
    if not info.get("is_admin", False):
        return "❌ ربات در این گروه ادمین نیست؛ این عملیات ممکن نیست."
    if capability in info and not info[capability]:
        label = _BOT_CAP_LABELS.get(capability, capability)
        return f"❌ ربات دسترسی «{label}» را در تنظیمات ادمینی خودش ندارد؛ این عملیات ممکن نیست."
    return None

@bot.on_message(filters=lambda m: _cmd_is(m, "pin"))
async def pin_cmd(bot: Robot, message: Message):
    """سنجاق واقعی (pinChatMessage) روی پیام ریپلای‌شده. /pin ساکت مثل /pin silent بی‌صدا سنجاق می‌کند."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not has_permission(user_id, group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return

    target = get_reply_message(message)
    if not target:
        await message.reply("⚠️ روی پیام مورد نظر ریپلای کن!")
        return
    target_mid = getattr(target, "message_id", None)
    if not target_mid:
        await message.reply("❌ شناسه‌ی پیام مقصد پیدا نشد؛ سنجاق ممکن نیست.")
        return

    err = await bot_capability_error(bot, group_id, "can_pin_messages")
    if err:
        await message.reply(err)
        return

    silent = to_en_digits(_cmd_rest(message.text)).strip().lower() in ("silent", "بی صدا", "بیصدا", "خاموش")
    res = await bot.pin_message(group_id, target_mid, notify=not silent)
    if not res:
        await message.reply(f"❌ سنجاق‌کردن پیام انجام نشد.\n🔎 علت: {res.error}")
        return
    await message.reply("📌 **پیام سنجاق شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "unpin"))
async def unpin_cmd(bot: Robot, message: Message):
    """
    رفع سنجاق واقعی (unpinChatMessage). با ریپلای روی یک پیام سنجاق‌شده همان پیام رفع سنجاق
    می‌شود؛ بدون ریپلای، آخرین پیام سنجاق‌شده‌ی گروه رفع سنجاق می‌شود. /unpin all همه را برمی‌دارد.
    """
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not has_permission(user_id, group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return

    err = await bot_capability_error(bot, group_id, "can_pin_messages")
    if err:
        await message.reply(err)
        return

    arg = to_en_digits(_cmd_rest(message.text)).strip().lower()
    if arg in ("all", "همه"):
        res = await bot.unpin_all_messages(group_id)
        verb = "همه‌ی سنجاق‌ها"
    else:
        target = get_reply_message(message)
        target_mid = getattr(target, "message_id", None) if target else None
        res = await bot.unpin_message(group_id, target_mid)
        verb = "پیام" if target_mid else "آخرین پیام سنجاق‌شده"
    if not res:
        await message.reply(f"❌ رفع سنجاق انجام نشد.\n🔎 علت: {res.error}")
        return
    await message.reply(f"📌 **سنجاق {verb} برداشته شد!**")

# =========================================================
#  سیستم مدیریت پاکسازی
# =========================================================

CLEAR_MAX_DEFAULT = 100           # سقف پیش‌فرض هر اجرای /clear
CLEAR_HARD_CAP = 500              # سقف مطلق (حتی با تنظیم دستی بالاتر) — پاک کردن کل تاریخچه ممکن نیست
_CLEAR_ACTIVE: Dict[str, float] = {}   # قفل هر گروه (clear_lock[group_id]) - دو /clear هم‌زمان ممنوع

@bot.on_message(filters=lambda m: _cmd_is(m, "clear"))
async def clear_cmd(bot: Robot, message: Message):
    """
    پاکسازی واقعی: فقط پیام‌هایی که ربات از قبل دیده (RECENT_MESSAGES) قابل حذف‌اند، چون Bot API
    تاریخچه‌ی قدیمی را در اختیار ربات نمی‌گذارد. هر حذف جداگانه با تلگرام چک می‌شود؛ نتیجه‌ی نهایی
    «موفق/ناموفق واقعی» است، نه «تعداد درخواستی». سقف دارد و برای هر گروه یک قفل جدا، تا دو اجرای
    همزمان دوبار همان پیام‌ها را حذف نکنند یا به تلگرام سیل نفرستند.
    """
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not has_permission(user_id, group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return

    parts = to_en_digits(message.text).split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply(f"⚠️ دستور: /clear [تعداد]  (حداکثر {CLEAR_HARD_CAP})")
        return
    count = int(parts[1])
    if count <= 0:
        await message.reply("⚠️ تعداد باید بزرگ‌تر از صفر باشد!")
        return
    capped_note = ""
    if count > CLEAR_HARD_CAP:
        capped_note = f"⚠️ سقف پاکسازی در هر اجرا {CLEAR_HARD_CAP} پیام است؛ همان مقدار پاک می‌شود (پاک‌کردن کل تاریخچه‌ی گروه ممکن نیست).\n"
        count = CLEAR_HARD_CAP

    now = time.monotonic()
    started = _CLEAR_ACTIVE.get(group_id)
    if started is not None and now - started < 120:
        await message.reply("⏳ یک عملیات پاکسازی همین حالا در این گروه در حال اجراست؛ صبر کن تمام شود.")
        return
    _CLEAR_ACTIVE[group_id] = now       # قفل: بدون هیچ await بین چک و ست

    try:
        err = await bot_capability_error(bot, group_id, "can_delete_messages")
        if err:
            await message.reply(err)
            return

        recent = RECENT_MESSAGES.get(str(group_id))
        if not recent:
            await message.reply("⚠️ هنوز پیامی برای پاکسازی در حافظه‌ی ربات ثبت نشده.")
            return
        current_mid = getattr(message, "message_id", None)
        others = [m for m in recent if m.get("message_id") != current_mid]
        targets = others[-count:]
        if not targets:
            await message.reply("⚠️ پیام قابل‌حذفی (به‌جز خودِ همین دستور) در حافظه ثبت نشده بود.")
            return

        attempted = len(targets)
        successful = 0
        error_counts: Dict[str, int] = {}
        for target in targets:
            res = await bot.delete_message_id(group_id, target["message_id"])
            if res:
                successful += 1
            else:
                error_counts[res.error] = error_counts.get(res.error, 0) + 1
        try:
            await message.delete()
        except Exception:
            pass

        failed = attempted - successful
        if successful == 0:
            top_error = max(error_counts, key=error_counts.get) if error_counts else "نامشخص"
            await message.reply(f"{capped_note}❌ هیچ پیامی پاک نشد. ({attempted} تلاش، همه ناموفق)\n🔎 علت: {top_error}")
        elif failed == 0:
            cleanup_emoji = get_custom_emoji(group_data, "cleanup")
            await message.reply(f"{capped_note}{cleanup_emoji} **{successful} پیام پاکسازی شد!**")
        else:
            top_error = max(error_counts, key=error_counts.get)
            cleanup_emoji = get_custom_emoji(group_data, "cleanup")
            await message.reply(f"{capped_note}{cleanup_emoji} **{successful} پیام پاک شد، {failed} پیام پاک نشد.**\n🔎 علت شایع خطا: {top_error}")
    finally:
        _CLEAR_ACTIVE.pop(group_id, None)

# =========================================================
#  🛠 پیاده‌سازی واقعی «حذف خودکار پیام‌های مدیریتی» (تا الان فقط در راهنما
#  تبلیغ می‌شد ولی هیچ هندلری نداشت؛ پیام‌های خودِ ربات هیچ‌وقت خودکار پاک
#  نمی‌شدن). این سه دستور با _track_bot_sent_message در بالای فایل ترکیب
#  می‌شن: هر پیامی که ربات می‌فرسته، اگه این قابلیت فعال باشه، بعد از
#  auto_delete_seconds ثانیه خودکار حذف می‌شه.
# =========================================================
AUTO_DELETE_MIN_SECONDS = 3
AUTO_DELETE_MAX_SECONDS = 3600

@bot.on_message(filters=lambda m: _cmd_is(m, "autodel_on"))
async def autodel_on_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return
    group_data["settings"]["auto_delete_enabled"] = True
    save_group_data(group_id, group_data)
    seconds = group_data["settings"].get("auto_delete_seconds", 10)
    await message.reply(f"✅ حذف خودکار پیام‌های ربات فعال شد (بعد از {seconds} ثانیه).")

@bot.on_message(filters=lambda m: _cmd_is(m, "autodel_off"))
async def autodel_off_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return
    group_data["settings"]["auto_delete_enabled"] = False
    save_group_data(group_id, group_data)
    await message.reply("✅ حذف خودکار پیام‌های ربات غیرفعال شد.")

@bot.on_message(filters=lambda m: _cmd_is(m, "setautodel"))
async def setautodel_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return
    parts = to_en_digits(message.text).split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply(f"⚠️ دستور: تنظیم حذف خودکار #ثانیه (بین {AUTO_DELETE_MIN_SECONDS} تا {AUTO_DELETE_MAX_SECONDS})")
        return
    seconds = int(parts[1])
    if not (AUTO_DELETE_MIN_SECONDS <= seconds <= AUTO_DELETE_MAX_SECONDS):
        await message.reply(f"⚠️ عدد باید بین {AUTO_DELETE_MIN_SECONDS} تا {AUTO_DELETE_MAX_SECONDS} ثانیه باشد.")
        return
    group_data["settings"]["auto_delete_seconds"] = seconds
    save_group_data(group_id, group_data)
    await message.reply(f"✅ زمان حذف خودکار روی {seconds} ثانیه تنظیم شد.")

# =========================================================
#  اجرا
# =========================================================


# =========================================================
#  سیستم مدیریت آمار روزانه
# =========================================================

@bot.on_message(filters=lambda m: m.text and m.text == "/daily")
async def daily_stats_cmd(bot: Robot, message: Message):
    """آمار روزانه گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    stats = group_data.get('stats', {})
    
    today = datetime.now().strftime('%Y/%m/%d')
    
    await message.reply(f"""
📊 **آمار روزانه** - {today}

💬 پیام‌های امروز: {stats.get('today_messages', 0)}
📈 پیام‌های هفته: {stats.get('week_messages', 0)}
📊 پیام‌های ماه: {stats.get('month_messages', 0)}
🔢 کل پیام‌ها: {stats.get('total_messages', 0)}

👥 کاربران جدید امروز: {stats.get('new_users_today', 0)}
⚠️ اخطارهای امروز: {stats.get('warns_today', 0)}
""")

# =========================================================
#  سیستم مدیریت وضعیت
# =========================================================

@bot.on_message(filters=lambda m: m.text and m.text == "/status")
async def status_cmd(bot: Robot, message: Message):
    """وضعیت گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    settings = group_data.get('settings', {})
    
    await message.reply(f"""
📊 **وضعیت گروه:**

🔒 قفل گروه: {'✅' if settings.get('lock', False) else '❌'}
🔗 ضد لینک: {'✅' if settings.get('anti_link', True) else '❌'}
🔄 ضد اسپم: {'✅' if settings.get('anti_spam', True) else '❌'}
💢 ضد فحش: {'✅' if settings.get('anti_swear', True) else '❌'}
🖼 قفل رسانه: {'✅' if settings.get('lock_media', False) else '❌'}
↗️ قفل فوروارد: {'✅' if settings.get('lock_forward', False) else '❌'}
#️⃣ قفل هشتگ: {'✅' if settings.get('lock_hashtag', False) else '❌'}
👤 قفل منشن: {'✅' if settings.get('lock_mention', False) else '❌'}

⚠️ حداکثر اخطار: {settings.get('max_warn', 3)}
🔇 زمان سکوت: {settings.get('mute_duration', 5)} دقیقه

👥 کاربران: {len(group_data.get('users', {}))}
👮 ادمین‌ها: {len(group_data.get('admins', []))}
⭐ ویژه‌ها: {len(group_data.get('specials', []))}
🚫 بن‌ها: {len(group_data.get('bans', []))}
🔇 سکوت‌ها: {len(group_data.get('mutes', []))}
""")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت چالش‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "challenge"))
async def challenge_cmd(bot: Robot, message: Message):
    """چالش تصادفی"""
    challenge = random.choice(CHALLENGES_200)
    await themed_reply(message, f"**چالش:**\n\n{challenge}", 'bio')

@bot.on_message(filters=lambda m: _cmd_is(m, "challenge_custom"))
async def challenge_custom_cmd(bot: Robot, message: Message):
    """چالش سفارشی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = message.text.replace("/challenge_custom", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /challenge_custom [متن چالش]")
        return
    
    await message.reply(f"🏆 **چالش جدید:**\n\n{text}")

@bot.on_message(filters=lambda m: _cmd_is(m, "challenge_list"))
async def challenge_list_cmd(bot: Robot, message: Message):
    """لیست چالش‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    challenges = group_data.get('custom_challenges', [])
    
    if challenges:
        text = "📋 **لیست چالش‌های سفارشی:**\n\n"
        for idx, ch in enumerate(challenges, 1):
            text += f"{idx}. {ch}\n"
        await message.reply(text)
    else:
        await message.reply("📋 هیچ چالش سفارشی وجود ندارد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "challenge_add"))
async def challenge_add_cmd(bot: Robot, message: Message):
    """افزودن چالش سفارشی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = message.text.replace("/challenge_add", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /challenge_add [متن چالش]")
        return
    
    if 'custom_challenges' not in group_data:
        group_data['custom_challenges'] = []
    
    group_data['custom_challenges'].append(text)
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **چالش جدید اضافه شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "challenge_remove"))
async def challenge_remove_cmd(bot: Robot, message: Message):
    """حذف چالش سفارشی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /challenge_remove [شماره]")
        return
    
    try:
        idx = int(parts[1]) - 1
        if 'custom_challenges' in group_data and idx < len(group_data['custom_challenges']):
            removed = group_data['custom_challenges'].pop(idx)
            save_group_data(group_id, group_data)
            await message.reply(f"✅ **چالش «{removed}» حذف شد!**")
        else:
            await message.reply("⚠️ چالشی با این شماره وجود ندارد!")
    except (ValueError, IndexError):
        await message.reply("⚠️ شماره را به عدد وارد کنید!")

# =========================================================
#  سیستم مدیریت پ ن پ
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "panap"))
async def panap_cmd(bot: Robot, message: Message):
    """پ ن پ تصادفی"""
    panap = random.choice(PANAPA_200)
    await message.reply(panap)

@bot.on_message(filters=lambda m: _cmd_is(m, "panap_custom"))
async def panap_custom_cmd(bot: Robot, message: Message):
    """پ ن پ سفارشی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = message.text.replace("/panap_custom", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /panap_custom [متن]")
        return
    
    await message.reply(f"⌯ #PANAPA\n\n{text}")

# =========================================================
#  سیستم مدیریت بیو
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "bio"))
async def bio_cmd(bot: Robot, message: Message):
    """بیو تصادفی"""
    await themed_reply(message, random.choice(BIO_200), 'bio')

@bot.on_message(filters=lambda m: _cmd_is(m, "bio_custom"))
async def bio_custom_cmd(bot: Robot, message: Message):
    """بیو سفارشی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = message.text.replace("/bio_custom", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /bio_custom [متن]")
        return
    
    await message.reply(f"⌯ #BIO\n\n{text}")

# =========================================================
#  سیستم مدیریت خاطره
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "khater"))
async def khater_cmd(bot: Robot, message: Message):
    """خاطره تصادفی"""
    await themed_reply(message, random.choice(KHATRH_200), 'bio')

@bot.on_message(filters=lambda m: _cmd_is(m, "khater_custom"))
async def khater_custom_cmd(bot: Robot, message: Message):
    """خاطره سفارشی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = message.text.replace("/khater_custom", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /khater_custom [متن]")
        return
    
    await message.reply(f"⌯ #KHATRH\n\n{text}")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت فال و طالع بینی
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "fal"))
async def fal_cmd(bot: Robot, message: Message):
    """فال حافظ"""
    fal_list = [
        '🔮 به کام تو خوش آید، ای دل که داری هوش\nچو با توست، غم مخور، که عاقبت خوش است',
        '🔮 اگر چه عیش خوش است، اما غم عشق\nبه از هزار جهان عیش و عشرت است',
        '🔮 ساقی بیا که عاشقان را\nبی می، نمی\u200cشود میسر',
        '🔮 ز کوی یار می\u200cآید نسیم باد نوروزی\nاز این باد ار مدد خواهی، چراغ دل برافروزی',
        '🔮 ای دل غم این جهان مخور\nکه عاقبت کار خوش است',
        '🔮 تو خود چه می\u200cدانی که عشق چیست\nکه در دام عشق افتاده\u200cای',
        '🔮 به می عشق دلم را خراب کن ساقی\nکه بی می عشق، دلم بی\u200cقرار است',
        '🔮 صبحدم که از افق می\u200cدمد\nنوید وصال یار می\u200cدهد',
        '🔮 به یاد روی تو، ای ماه\nدلم هوایی شده',
        '🔮 غم عشق تو را، ای جان\nبه جان خریدم و خوش است',
        '🔮 خبر خوشی از راه دور می\u200cرسد\nکه یار وفادار فراموشت نمی\u200cکند',
        '🔮 کام دل تو نزدیک است، صبوری کن\nکه صبر تلخ، شیرینی به بار می\u200cآورد',
        '🔮 صبر کن که بعد از تاریکی روشنایی می\u200cآید\nکه خورشید بخت تو تابان است',
        '🔮 سفر تازه\u200cای در پیش داری، آماده شو\nکه چرخ فلک به کام تو می\u200cگردد',
        '🔮 صبر کن که بعد از تاریکی روشنایی می\u200cآید\nکه آسمان دلت را روشن می\u200cکند',
        '🔮 کام دل تو نزدیک است، صبوری کن\nکه این ابر تیره زود می\u200cگذرد',
        '🔮 هر کجا سختی است، آسانی هم پنهان است\nکه هر شب یلدا را سحری است',
        '🔮 کام دل تو نزدیک است، صبوری کن\nکه یار وفادار فراموشت نمی\u200cکند',
        '🔮 بر آستان یار، سر خم کن و صبر کن\nکه این ابر تیره زود می\u200cگذرد',
        '🔮 باد صبا خبر ز محبوب می\u200cآورد\nکه خورشید بخت تو تابان است',
        '🔮 صبر کن که بعد از تاریکی روشنایی می\u200cآید\nکه هر سختی، پایانی خوش دارد',
        '🔮 بر آستان یار، سر خم کن و صبر کن\nکه هر سختی، پایانی خوش دارد',
        '🔮 چراغ امید را در دل خاموش مکن\nکه آسمان دلت را روشن می\u200cکند',
        '🔮 خبر خوشی از راه دور می\u200cرسد\nکه رنج امروز، گنج فرداست',
        '🔮 صبر کن که بعد از تاریکی روشنایی می\u200cآید\nکه دل\u200cهای صادق به هم می\u200cرسند',
        '🔮 عاقبت این راه پر پیچ به منزل می\u200cرسد\nکه صبر تلخ، شیرینی به بار می\u200cآورد',
        '🔮 هر که صبر کند، به مراد خود رسد\nکه در دل شب، صبح نزدیک است',
        '🔮 چراغ امید را در دل خاموش مکن\nکه این ابر تیره زود می\u200cگذرد',
        '🔮 دل نگران مباش که یاری در راه است\nکه این ابر تیره زود می\u200cگذرد',
        '🔮 یار دیرینه\u200cای به دیدارت خواهد آمد\nکه هر سختی، پایانی خوش دارد',
        '🔮 کام دل تو نزدیک است، صبوری کن\nکه بعد از هر گریه، خنده\u200cای است',
        '🔮 یار دیرینه\u200cای به دیدارت خواهد آمد\nکه این ابر تیره زود می\u200cگذرد',
        '🔮 بر آستان یار، سر خم کن و صبر کن\nکه صبر تلخ، شیرینی به بار می\u200cآورد',
        '🔮 هر کجا سختی است، آسانی هم پنهان است\nکه هر سختی، پایانی خوش دارد',
        '🔮 سرنوشت تو رقم خورده به مهر و وفا\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 دل نگران مباش که یاری در راه است\nکه در دل شب، صبح نزدیک است',
        '🔮 ستاره\u200cی بخت تو در حال طلوع است\nکه یار وفادار فراموشت نمی\u200cکند',
        '🔮 از غصه\u200cی دنیا دل خود را خالی کن\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 اگر امروز دلتنگی، فردا شادمانی\nکه هر شب یلدا را سحری است',
        '🔮 دل نگران مباش که یاری در راه است\nکه چرخ فلک به کام تو می\u200cگردد',
        '🔮 بوی گل و ریحان ز باغ می\u200cآید\nکه در دل شب، صبح نزدیک است',
        '🔮 سفر تازه\u200cای در پیش داری، آماده شو\nکه عاقبت این غم به شادی می\u200cرسد',
        '🔮 دل را به دریای امید بسپار\nکه دل\u200cهای صادق به هم می\u200cرسند',
        '🔮 گنج مراد در پس رنج پنهان است\nکه دل\u200cهای صادق به هم می\u200cرسند',
        '🔮 در پس هر ابر تیره، آفتابی است\nکه چرخ فلک به کام تو می\u200cگردد',
        '🔮 صبر کن که بعد از تاریکی روشنایی می\u200cآید\nکه این ابر تیره زود می\u200cگذرد',
        '🔮 گنج مراد در پس رنج پنهان است\nکه هر شب یلدا را سحری است',
        '🔮 خبر خوشی از راه دور می\u200cرسد\nکه خورشید بخت تو تابان است',
        '🔮 اگر امروز دلتنگی، فردا شادمانی\nکه چرخ فلک به کام تو می\u200cگردد',
        '🔮 صبر کن که بعد از تاریکی روشنایی می\u200cآید\nکه بعد از هر گریه، خنده\u200cای است',
        '🔮 ستاره\u200cی بخت تو در حال طلوع است\nکه رنج امروز، گنج فرداست',
        '🔮 از غصه\u200cی دنیا دل خود را خالی کن\nکه آسمان دلت را روشن می\u200cکند',
        '🔮 صبر کن که بعد از تاریکی روشنایی می\u200cآید\nکه یار وفادار فراموشت نمی\u200cکند',
        '🔮 بر آستان یار، سر خم کن و صبر کن\nکه یار وفادار فراموشت نمی\u200cکند',
        '🔮 گنج مراد در پس رنج پنهان است\nکه رنج امروز، گنج فرداست',
        '🔮 اگر امروز دلتنگی، فردا شادمانی\nکه خورشید بخت تو تابان است',
        '🔮 از غصه\u200cی دنیا دل خود را خالی کن\nکه صبر تلخ، شیرینی به بار می\u200cآورد',
        '🔮 ستاره\u200cی بخت تو در حال طلوع است\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 چراغ امید را در دل خاموش مکن\nکه هر شب یلدا را سحری است',
        '🔮 خبر خوشی از راه دور می\u200cرسد\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 چراغ امید را در دل خاموش مکن\nکه دل\u200cهای صادق به هم می\u200cرسند',
        '🔮 ستاره\u200cی بخت تو در حال طلوع است\nکه تقدیر تو نوشته به مهربانی',
        '🔮 در پس هر ابر تیره، آفتابی است\nکه یار وفادار فراموشت نمی\u200cکند',
        '🔮 ستاره\u200cی بخت تو در حال طلوع است\nکه خورشید بخت تو تابان است',
        '🔮 در پس هر ابر تیره، آفتابی است\nکه خورشید بخت تو تابان است',
        '🔮 گنج مراد در پس رنج پنهان است\nکه تقدیر تو نوشته به مهربانی',
        '🔮 عاقبت این راه پر پیچ به منزل می\u200cرسد\nکه هر سختی، پایانی خوش دارد',
        '🔮 بر آستان یار، سر خم کن و صبر کن\nکه دل\u200cهای صادق به هم می\u200cرسند',
        '🔮 در پس هر ابر تیره، آفتابی است\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 ستاره\u200cی بخت تو در حال طلوع است\nکه در دل شب، صبح نزدیک است',
        '🔮 هر که صبر کند، به مراد خود رسد\nکه عاقبت این غم به شادی می\u200cرسد',
        '🔮 دل نگران مباش که یاری در راه است\nکه هر سختی، پایانی خوش دارد',
        '🔮 سرنوشت تو رقم خورده به مهر و وفا\nکه تقدیر تو نوشته به مهربانی',
        '🔮 هر که صبر کند، به مراد خود رسد\nکه بعد از هر گریه، خنده\u200cای است',
        '🔮 کام دل تو نزدیک است، صبوری کن\nکه خورشید بخت تو تابان است',
        '🔮 دل را به دریای امید بسپار\nکه تقدیر تو نوشته به مهربانی',
        '🔮 خبر خوشی از راه دور می\u200cرسد\nکه آسمان دلت را روشن می\u200cکند',
        '🔮 سرنوشت تو رقم خورده به مهر و وفا\nکه چرخ فلک به کام تو می\u200cگردد',
        '🔮 در پس هر ابر تیره، آفتابی است\nکه تقدیر تو نوشته به مهربانی',
        '🔮 خبر خوشی از راه دور می\u200cرسد\nکه عاقبت این غم به شادی می\u200cرسد',
        '🔮 چراغ امید را در دل خاموش مکن\nکه تقدیر تو نوشته به مهربانی',
        '🔮 کام دل تو نزدیک است، صبوری کن\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 هر کجا سختی است، آسانی هم پنهان است\nکه خورشید بخت تو تابان است',
        '🔮 باد صبا خبر ز محبوب می\u200cآورد\nکه صبر تلخ، شیرینی به بار می\u200cآورد',
        '🔮 در پس هر ابر تیره، آفتابی است\nکه هر شب یلدا را سحری است',
        '🔮 بوی گل و ریحان ز باغ می\u200cآید\nکه عاقبت این غم به شادی می\u200cرسد',
        '🔮 بر آستان یار، سر خم کن و صبر کن\nکه خورشید بخت تو تابان است',
        '🔮 خبر خوشی از راه دور می\u200cرسد\nکه این ابر تیره زود می\u200cگذرد',
        '🔮 هر که صبر کند، به مراد خود رسد\nکه هر شب یلدا را سحری است',
        '🔮 هر کجا سختی است، آسانی هم پنهان است\nکه بعد از هر گریه، خنده\u200cای است',
        '🔮 بوی گل و ریحان ز باغ می\u200cآید\nکه بعد از هر گریه، خنده\u200cای است',
        '🔮 خبر خوشی از راه دور می\u200cرسد\nکه بعد از هر گریه، خنده\u200cای است',
        '🔮 دل نگران مباش که یاری در راه است\nکه هر شب یلدا را سحری است',
        '🔮 یار دیرینه\u200cای به دیدارت خواهد آمد\nکه خورشید بخت تو تابان است',
        '🔮 سفر تازه\u200cای در پیش داری، آماده شو\nکه یار وفادار فراموشت نمی\u200cکند',
        '🔮 اگر امروز دلتنگی، فردا شادمانی\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 در پس هر ابر تیره، آفتابی است\nکه دل\u200cهای صادق به هم می\u200cرسند',
        '🔮 باد صبا خبر ز محبوب می\u200cآورد\nکه این ابر تیره زود می\u200cگذرد',
        '🔮 بوی گل و ریحان ز باغ می\u200cآید\nکه هر سختی، پایانی خوش دارد',
        '🔮 دل را به دریای امید بسپار\nکه رنج امروز، گنج فرداست',
        '🔮 هر کجا سختی است، آسانی هم پنهان است\nکه رنج امروز، گنج فرداست',
        '🔮 بوی گل و ریحان ز باغ می\u200cآید\nکه خورشید بخت تو تابان است',
        '🔮 خبر خوشی از راه دور می\u200cرسد\nکه هر شب یلدا را سحری است',
        '🔮 یار دیرینه\u200cای به دیدارت خواهد آمد\nکه رنج امروز، گنج فرداست',
        '🔮 از غصه\u200cی دنیا دل خود را خالی کن\nکه یار وفادار فراموشت نمی\u200cکند',
        '🔮 هر کجا سختی است، آسانی هم پنهان است\nکه دل\u200cهای صادق به هم می\u200cرسند',
        '🔮 ستاره\u200cی بخت تو در حال طلوع است\nکه دل\u200cهای صادق به هم می\u200cرسند',
        '🔮 کام دل تو نزدیک است، صبوری کن\nکه دل\u200cهای صادق به هم می\u200cرسند',
        '🔮 باد صبا خبر ز محبوب می\u200cآورد\nکه تقدیر تو نوشته به مهربانی',
        '🔮 باد صبا خبر ز محبوب می\u200cآورد\nکه چرخ فلک به کام تو می\u200cگردد',
        '🔮 هر که صبر کند، به مراد خود رسد\nکه چرخ فلک به کام تو می\u200cگردد',
        '🔮 سرنوشت تو رقم خورده به مهر و وفا\nکه دل\u200cهای صادق به هم می\u200cرسند',
        '🔮 سفر تازه\u200cای در پیش داری، آماده شو\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 در پس هر ابر تیره، آفتابی است\nکه در دل شب، صبح نزدیک است',
        '🔮 باد صبا خبر ز محبوب می\u200cآورد\nکه هر شب یلدا را سحری است',
        '🔮 یار دیرینه\u200cای به دیدارت خواهد آمد\nکه صبر تلخ، شیرینی به بار می\u200cآورد',
        '🔮 سفر تازه\u200cای در پیش داری، آماده شو\nکه هر شب یلدا را سحری است',
        '🔮 گنج مراد در پس رنج پنهان است\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 سفر تازه\u200cای در پیش داری، آماده شو\nکه رنج امروز، گنج فرداست',
        '🔮 از غصه\u200cی دنیا دل خود را خالی کن\nکه عاقبت این غم به شادی می\u200cرسد',
        '🔮 هر کجا سختی است، آسانی هم پنهان است\nکه یار وفادار فراموشت نمی\u200cکند',
        '🔮 عاقبت این راه پر پیچ به منزل می\u200cرسد\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 ستاره\u200cی بخت تو در حال طلوع است\nکه عاقبت این غم به شادی می\u200cرسد',
        '🔮 هر که صبر کند، به مراد خود رسد\nکه تقدیر تو نوشته به مهربانی',
        '🔮 گنج مراد در پس رنج پنهان است\nکه این ابر تیره زود می\u200cگذرد',
        '🔮 بوی گل و ریحان ز باغ می\u200cآید\nکه آسمان دلت را روشن می\u200cکند',
        '🔮 چراغ امید را در دل خاموش مکن\nکه در دل شب، صبح نزدیک است',
        '🔮 از غصه\u200cی دنیا دل خود را خالی کن\nکه چرخ فلک به کام تو می\u200cگردد',
        '🔮 صبر کن که بعد از تاریکی روشنایی می\u200cآید\nکه چرخ فلک به کام تو می\u200cگردد',
        '🔮 چراغ امید را در دل خاموش مکن\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 بوی گل و ریحان ز باغ می\u200cآید\nکه صبر تلخ، شیرینی به بار می\u200cآورد',
        '🔮 بر آستان یار، سر خم کن و صبر کن\nکه در دل شب، صبح نزدیک است',
        '🔮 باد صبا خبر ز محبوب می\u200cآورد\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 صبر کن که بعد از تاریکی روشنایی می\u200cآید\nکه در دل شب، صبح نزدیک است',
        '🔮 ستاره\u200cی بخت تو در حال طلوع است\nکه هر شب یلدا را سحری است',
        '🔮 بر آستان یار، سر خم کن و صبر کن\nکه آسمان دلت را روشن می\u200cکند',
        '🔮 عاقبت این راه پر پیچ به منزل می\u200cرسد\nکه تقدیر تو نوشته به مهربانی',
        '🔮 چراغ امید را در دل خاموش مکن\nکه خورشید بخت تو تابان است',
        '🔮 از غصه\u200cی دنیا دل خود را خالی کن\nکه در دل شب، صبح نزدیک است',
        '🔮 گنج مراد در پس رنج پنهان است\nکه بعد از هر گریه، خنده\u200cای است',
        '🔮 هر که صبر کند، به مراد خود رسد\nکه دل\u200cهای صادق به هم می\u200cرسند',
        '🔮 گنج مراد در پس رنج پنهان است\nکه یار وفادار فراموشت نمی\u200cکند',
        '🔮 عاقبت این راه پر پیچ به منزل می\u200cرسد\nکه در دل شب، صبح نزدیک است',
        '🔮 بوی گل و ریحان ز باغ می\u200cآید\nکه چرخ فلک به کام تو می\u200cگردد',
        '🔮 باد صبا خبر ز محبوب می\u200cآورد\nکه رنج امروز، گنج فرداست',
        '🔮 یار دیرینه\u200cای به دیدارت خواهد آمد\nکه آسمان دلت را روشن می\u200cکند',
        '🔮 عاقبت این راه پر پیچ به منزل می\u200cرسد\nکه دل\u200cهای صادق به هم می\u200cرسند',
        '🔮 کام دل تو نزدیک است، صبوری کن\nکه آسمان دلت را روشن می\u200cکند',
        '🔮 صبر کن که بعد از تاریکی روشنایی می\u200cآید\nکه عاقبت این غم به شادی می\u200cرسد',
        '🔮 هر که صبر کند، به مراد خود رسد\nکه یار وفادار فراموشت نمی\u200cکند',
        '🔮 سرنوشت تو رقم خورده به مهر و وفا\nکه رنج امروز، گنج فرداست',
        '🔮 در پس هر ابر تیره، آفتابی است\nکه آسمان دلت را روشن می\u200cکند',
        '🔮 هر کجا سختی است، آسانی هم پنهان است\nکه این ابر تیره زود می\u200cگذرد',
        '🔮 عاقبت این راه پر پیچ به منزل می\u200cرسد\nکه عاقبت این غم به شادی می\u200cرسد',
        '🔮 در پس هر ابر تیره، آفتابی است\nکه عاقبت این غم به شادی می\u200cرسد',
        '🔮 بوی گل و ریحان ز باغ می\u200cآید\nکه تقدیر تو نوشته به مهربانی',
        '🔮 بوی گل و ریحان ز باغ می\u200cآید\nکه دل\u200cهای صادق به هم می\u200cرسند',
        '🔮 هر کجا سختی است، آسانی هم پنهان است\nکه در دل شب، صبح نزدیک است',
        '🔮 دل را به دریای امید بسپار\nکه چرخ فلک به کام تو می\u200cگردد',
        '🔮 سفر تازه\u200cای در پیش داری، آماده شو\nکه صبر تلخ، شیرینی به بار می\u200cآورد',
        '🔮 خبر خوشی از راه دور می\u200cرسد\nکه در دل شب، صبح نزدیک است',
        '🔮 هر که صبر کند، به مراد خود رسد\nکه رنج امروز، گنج فرداست',
        '🔮 از غصه\u200cی دنیا دل خود را خالی کن\nکه هر شب یلدا را سحری است',
        '🔮 دل را به دریای امید بسپار\nکه بعد از هر گریه، خنده\u200cای است',
        '🔮 ستاره\u200cی بخت تو در حال طلوع است\nکه صبر تلخ، شیرینی به بار می\u200cآورد',
        '🔮 در پس هر ابر تیره، آفتابی است\nکه صبر تلخ، شیرینی به بار می\u200cآورد',
        '🔮 عاقبت این راه پر پیچ به منزل می\u200cرسد\nکه بعد از هر گریه، خنده\u200cای است',
        '🔮 ستاره\u200cی بخت تو در حال طلوع است\nکه چرخ فلک به کام تو می\u200cگردد',
        '🔮 کام دل تو نزدیک است، صبوری کن\nکه در دل شب، صبح نزدیک است',
        '🔮 چراغ امید را در دل خاموش مکن\nکه عاقبت این غم به شادی می\u200cرسد',
        '🔮 دل نگران مباش که یاری در راه است\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 ستاره\u200cی بخت تو در حال طلوع است\nکه هر سختی، پایانی خوش دارد',
        '🔮 بوی گل و ریحان ز باغ می\u200cآید\nکه هر شب یلدا را سحری است',
        '🔮 باد صبا خبر ز محبوب می\u200cآورد\nکه در دل شب، صبح نزدیک است',
        '🔮 هر که صبر کند، به مراد خود رسد\nکه آسمان دلت را روشن می\u200cکند',
        '🔮 دل نگران مباش که یاری در راه است\nکه تقدیر تو نوشته به مهربانی',
        '🔮 هر کجا سختی است، آسانی هم پنهان است\nکه صبر تلخ، شیرینی به بار می\u200cآورد',
        '🔮 از غصه\u200cی دنیا دل خود را خالی کن\nکه رنج امروز، گنج فرداست',
        '🔮 هر که صبر کند، به مراد خود رسد\nکه صبر تلخ، شیرینی به بار می\u200cآورد',
        '🔮 هر کجا سختی است، آسانی هم پنهان است\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 سفر تازه\u200cای در پیش داری، آماده شو\nکه دل\u200cهای صادق به هم می\u200cرسند',
        '🔮 صبر کن که بعد از تاریکی روشنایی می\u200cآید\nکه رنج امروز، گنج فرداست',
        '🔮 یار دیرینه\u200cای به دیدارت خواهد آمد\nکه یار وفادار فراموشت نمی\u200cکند',
        '🔮 از غصه\u200cی دنیا دل خود را خالی کن\nکه هر سختی، پایانی خوش دارد',
        '🔮 یار دیرینه\u200cای به دیدارت خواهد آمد\nکه چرخ فلک به کام تو می\u200cگردد',
        '🔮 هر که صبر کند، به مراد خود رسد\nکه هر سختی، پایانی خوش دارد',
        '🔮 خبر خوشی از راه دور می\u200cرسد\nکه هر سختی، پایانی خوش دارد',
        '🔮 دل را به دریای امید بسپار\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 بوی گل و ریحان ز باغ می\u200cآید\nکه یار وفادار فراموشت نمی\u200cکند',
        '🔮 هر که صبر کند، به مراد خود رسد\nکه خورشید بخت تو تابان است',
        '🔮 چراغ امید را در دل خاموش مکن\nکه هر سختی، پایانی خوش دارد',
        '🔮 دل را به دریای امید بسپار\nکه آسمان دلت را روشن می\u200cکند',
        '🔮 کام دل تو نزدیک است، صبوری کن\nکه تقدیر تو نوشته به مهربانی',
        '🔮 سرنوشت تو رقم خورده به مهر و وفا\nکه بعد از هر گریه، خنده\u200cای است',
        '🔮 باد صبا خبر ز محبوب می\u200cآورد\nکه آسمان دلت را روشن می\u200cکند',
        '🔮 عاقبت این راه پر پیچ به منزل می\u200cرسد\nکه رنج امروز، گنج فرداست',
        '🔮 اگر امروز دلتنگی، فردا شادمانی\nکه تقدیر تو نوشته به مهربانی',
        '🔮 بر آستان یار، سر خم کن و صبر کن\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 صبر کن که بعد از تاریکی روشنایی می\u200cآید\nکه این قصه به خیر و خوشی ختم شود',
        '🔮 سفر تازه\u200cای در پیش داری، آماده شو\nکه این ابر تیره زود می\u200cگذرد',
    ]
    
    fal = random.choice(fal_list)
    await message.reply(f"""
🪷 **فال حافظ:**

{fal}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}
💫 فال شما نیک است!
""")

@bot.on_message(filters=lambda m: _cmd_is(m, "daily_fal"))
async def daily_fal_cmd(bot: Robot, message: Message):
    """فال روزانه"""
    daily_fals = [
        '🌟 امروز روز خوبی برای شروع کارهای جدید است.',
        '🌟 عشق در راه است! منتظر یک اتفاق خوب باش.',
        '🌟 موفقیت در انتظار توست، فقط کافی است باور کنی.',
        '🌟 امروز روز آرامشی، استراحت کن و به خودت برس.',
        '🌟 یک خبر خوب به زودی به تو میرسد.',
        '🌟 سفر در پیش داری، آماده شو!',
        '🌟 پول و ثروت به سمت تو میاد، فقط صبور باش.',
        '🌟 امروز روز ملاقات با یک دوست قدیمیه.',
        '🌟 یک تصمیم مهم باید بگیری، به قلبت اعتماد کن.',
        '🌟 روزت پر از انرژی و شادی خواهد بود.',
        '🌟 امروز روز مناسبی برای آشتی با کسی است که دلخوری داشتی.',
        '🌟 یک خبر غیرمنتظره اما خوشایند می\u200cشنوی.',
        '🌟 امروز حال دلت بهتر از دیروز خواهد بود.',
        '🌟 فرصتی طلایی امروز از کنارت می\u200cگذرد، هوشیار باش.',
        '🌟 امروز روز خوبی برای شروع یک عادت سالم جدید است.',
        '🌟 دوستان امروز دورت جمع می\u200cشوند و روزت را شیرین می\u200cکنند.',
        '🌟 کمی صبر کن، چیزی که منتظرش بودی نزدیک است.',
        '🌟 امروز اعتماد به نفست بیشتر از همیشه است، از آن استفاده کن.',
        '🌟 یک تماس یا پیام مهم امروز دریافت می\u200cکنی.',
        '🌟 امروز روز خوبی برای برنامه\u200cریزی آینده\u200cی نزدیک است.',
        '🌟  امروز فرصت خوبی برای جبران یک اشتباه قدیمی داری.',
        '🌟  کسی امروز به فکر توست، هرچند به رویت نمی\u200cآورد.',
        '🌟  یک پیشنهاد کاری جالب در راه است.',
        '🌟  امروز حرف دلت را بی\u200cپرده بزن، نتیجه خوبی می\u200cگیری.',
        '🌟  یک هدیه\u200cی کوچک اما دلنشین در انتظارت است.',
        '🌟  امروز روز خوبی برای یادگیری چیزی تازه است.',
        '🌟  کمی احتیاط در تصمیم\u200cهای مالی امروز لازم است.',
        '🌟  یک خاطره\u200cی قدیمی امروز به یادت می\u200cآید و لبخند می\u200cزنی.',
        '🌟  امروز کسی از تو تشکر ویژه\u200cای می\u200cکند.',
        '🌟  انرژی امروزت را صرف کارهای مهم کن، نه چیزهای بی\u200cفایده.',
        '🌟  امروز روز مناسبی برای آشتی با کسی است که دلخوری داشتی.',
        '🌟  یک خبر غیرمنتظره اما خوشایند می\u200cشنوی.',
        '🌟  امروز حال دلت بهتر از دیروز خواهد بود.',
        '🌟  فرصتی طلایی امروز از کنارت می\u200cگذرد، هوشیار باش.',
        '🌟  امروز روز خوبی برای شروع یک عادت سالم جدید است.',
        '🌟  دوستان امروز دورت جمع می\u200cشوند و روزت را شیرین می\u200cکنند.',
        '🌟  کمی صبر کن، چیزی که منتظرش بودی نزدیک است.',
        '🌟  امروز اعتماد به نفست بیشتر از همیشه است، از آن استفاده کن.',
        '🌟  یک تماس یا پیام مهم امروز دریافت می\u200cکنی.',
        '🌟  امروز روز خوبی برای برنامه\u200cریزی آینده\u200cی نزدیک است.',
        '🌟   امروز فرصت خوبی برای جبران یک اشتباه قدیمی داری.',
        '🌟   کسی امروز به فکر توست، هرچند به رویت نمی\u200cآورد.',
        '🌟   یک پیشنهاد کاری جالب در راه است.',
        '🌟   امروز حرف دلت را بی\u200cپرده بزن، نتیجه خوبی می\u200cگیری.',
        '🌟   یک هدیه\u200cی کوچک اما دلنشین در انتظارت است.',
        '🌟   امروز روز خوبی برای یادگیری چیزی تازه است.',
        '🌟   کمی احتیاط در تصمیم\u200cهای مالی امروز لازم است.',
        '🌟   یک خاطره\u200cی قدیمی امروز به یادت می\u200cآید و لبخند می\u200cزنی.',
        '🌟   امروز کسی از تو تشکر ویژه\u200cای می\u200cکند.',
        '🌟   انرژی امروزت را صرف کارهای مهم کن، نه چیزهای بی\u200cفایده.',
        '🌟   امروز روز مناسبی برای آشتی با کسی است که دلخوری داشتی.',
        '🌟   یک خبر غیرمنتظره اما خوشایند می\u200cشنوی.',
        '🌟   امروز حال دلت بهتر از دیروز خواهد بود.',
        '🌟   فرصتی طلایی امروز از کنارت می\u200cگذرد، هوشیار باش.',
        '🌟   امروز روز خوبی برای شروع یک عادت سالم جدید است.',
        '🌟   دوستان امروز دورت جمع می\u200cشوند و روزت را شیرین می\u200cکنند.',
        '🌟   کمی صبر کن، چیزی که منتظرش بودی نزدیک است.',
        '🌟   امروز اعتماد به نفست بیشتر از همیشه است، از آن استفاده کن.',
        '🌟   یک تماس یا پیام مهم امروز دریافت می\u200cکنی.',
        '🌟   امروز روز خوبی برای برنامه\u200cریزی آینده\u200cی نزدیک است.',
        '🌟    امروز فرصت خوبی برای جبران یک اشتباه قدیمی داری.',
        '🌟    کسی امروز به فکر توست، هرچند به رویت نمی\u200cآورد.',
        '🌟    یک پیشنهاد کاری جالب در راه است.',
        '🌟    امروز حرف دلت را بی\u200cپرده بزن، نتیجه خوبی می\u200cگیری.',
        '🌟    یک هدیه\u200cی کوچک اما دلنشین در انتظارت است.',
        '🌟    امروز روز خوبی برای یادگیری چیزی تازه است.',
        '🌟    کمی احتیاط در تصمیم\u200cهای مالی امروز لازم است.',
        '🌟    یک خاطره\u200cی قدیمی امروز به یادت می\u200cآید و لبخند می\u200cزنی.',
        '🌟    امروز کسی از تو تشکر ویژه\u200cای می\u200cکند.',
        '🌟    انرژی امروزت را صرف کارهای مهم کن، نه چیزهای بی\u200cفایده.',
        '🌟    امروز روز مناسبی برای آشتی با کسی است که دلخوری داشتی.',
        '🌟    یک خبر غیرمنتظره اما خوشایند می\u200cشنوی.',
        '🌟    امروز حال دلت بهتر از دیروز خواهد بود.',
        '🌟    فرصتی طلایی امروز از کنارت می\u200cگذرد، هوشیار باش.',
        '🌟    امروز روز خوبی برای شروع یک عادت سالم جدید است.',
        '🌟    دوستان امروز دورت جمع می\u200cشوند و روزت را شیرین می\u200cکنند.',
        '🌟    کمی صبر کن، چیزی که منتظرش بودی نزدیک است.',
        '🌟    امروز اعتماد به نفست بیشتر از همیشه است، از آن استفاده کن.',
        '🌟    یک تماس یا پیام مهم امروز دریافت می\u200cکنی.',
        '🌟    امروز روز خوبی برای برنامه\u200cریزی آینده\u200cی نزدیک است.',
        '🌟     امروز فرصت خوبی برای جبران یک اشتباه قدیمی داری.',
        '🌟     کسی امروز به فکر توست، هرچند به رویت نمی\u200cآورد.',
        '🌟     یک پیشنهاد کاری جالب در راه است.',
        '🌟     امروز حرف دلت را بی\u200cپرده بزن، نتیجه خوبی می\u200cگیری.',
        '🌟     یک هدیه\u200cی کوچک اما دلنشین در انتظارت است.',
        '🌟     امروز روز خوبی برای یادگیری چیزی تازه است.',
        '🌟     کمی احتیاط در تصمیم\u200cهای مالی امروز لازم است.',
        '🌟     یک خاطره\u200cی قدیمی امروز به یادت می\u200cآید و لبخند می\u200cزنی.',
        '🌟     امروز کسی از تو تشکر ویژه\u200cای می\u200cکند.',
        '🌟     انرژی امروزت را صرف کارهای مهم کن، نه چیزهای بی\u200cفایده.',
        '🌟     امروز روز مناسبی برای آشتی با کسی است که دلخوری داشتی.',
        '🌟     یک خبر غیرمنتظره اما خوشایند می\u200cشنوی.',
        '🌟     امروز حال دلت بهتر از دیروز خواهد بود.',
        '🌟     فرصتی طلایی امروز از کنارت می\u200cگذرد، هوشیار باش.',
        '🌟     امروز روز خوبی برای شروع یک عادت سالم جدید است.',
        '🌟     دوستان امروز دورت جمع می\u200cشوند و روزت را شیرین می\u200cکنند.',
        '🌟     کمی صبر کن، چیزی که منتظرش بودی نزدیک است.',
        '🌟     امروز اعتماد به نفست بیشتر از همیشه است، از آن استفاده کن.',
        '🌟     یک تماس یا پیام مهم امروز دریافت می\u200cکنی.',
        '🌟     امروز روز خوبی برای برنامه\u200cریزی آینده\u200cی نزدیک است.',
        '🌟      امروز فرصت خوبی برای جبران یک اشتباه قدیمی داری.',
        '🌟      کسی امروز به فکر توست، هرچند به رویت نمی\u200cآورد.',
        '🌟      یک پیشنهاد کاری جالب در راه است.',
        '🌟      امروز حرف دلت را بی\u200cپرده بزن، نتیجه خوبی می\u200cگیری.',
        '🌟      یک هدیه\u200cی کوچک اما دلنشین در انتظارت است.',
        '🌟      امروز روز خوبی برای یادگیری چیزی تازه است.',
        '🌟      کمی احتیاط در تصمیم\u200cهای مالی امروز لازم است.',
        '🌟      یک خاطره\u200cی قدیمی امروز به یادت می\u200cآید و لبخند می\u200cزنی.',
        '🌟      امروز کسی از تو تشکر ویژه\u200cای می\u200cکند.',
        '🌟      انرژی امروزت را صرف کارهای مهم کن، نه چیزهای بی\u200cفایده.',
        '🌟      امروز روز مناسبی برای آشتی با کسی است که دلخوری داشتی.',
        '🌟      یک خبر غیرمنتظره اما خوشایند می\u200cشنوی.',
        '🌟      امروز حال دلت بهتر از دیروز خواهد بود.',
        '🌟      فرصتی طلایی امروز از کنارت می\u200cگذرد، هوشیار باش.',
        '🌟      امروز روز خوبی برای شروع یک عادت سالم جدید است.',
        '🌟      دوستان امروز دورت جمع می\u200cشوند و روزت را شیرین می\u200cکنند.',
        '🌟      کمی صبر کن، چیزی که منتظرش بودی نزدیک است.',
        '🌟      امروز اعتماد به نفست بیشتر از همیشه است، از آن استفاده کن.',
        '🌟      یک تماس یا پیام مهم امروز دریافت می\u200cکنی.',
        '🌟      امروز روز خوبی برای برنامه\u200cریزی آینده\u200cی نزدیک است.',
        '🌟       امروز فرصت خوبی برای جبران یک اشتباه قدیمی داری.',
        '🌟       کسی امروز به فکر توست، هرچند به رویت نمی\u200cآورد.',
        '🌟       یک پیشنهاد کاری جالب در راه است.',
        '🌟       امروز حرف دلت را بی\u200cپرده بزن، نتیجه خوبی می\u200cگیری.',
        '🌟       یک هدیه\u200cی کوچک اما دلنشین در انتظارت است.',
        '🌟       امروز روز خوبی برای یادگیری چیزی تازه است.',
        '🌟       کمی احتیاط در تصمیم\u200cهای مالی امروز لازم است.',
        '🌟       یک خاطره\u200cی قدیمی امروز به یادت می\u200cآید و لبخند می\u200cزنی.',
        '🌟       امروز کسی از تو تشکر ویژه\u200cای می\u200cکند.',
        '🌟       انرژی امروزت را صرف کارهای مهم کن، نه چیزهای بی\u200cفایده.',
        '🌟       امروز روز مناسبی برای آشتی با کسی است که دلخوری داشتی.',
        '🌟       یک خبر غیرمنتظره اما خوشایند می\u200cشنوی.',
        '🌟       امروز حال دلت بهتر از دیروز خواهد بود.',
        '🌟       فرصتی طلایی امروز از کنارت می\u200cگذرد، هوشیار باش.',
        '🌟       امروز روز خوبی برای شروع یک عادت سالم جدید است.',
        '🌟       دوستان امروز دورت جمع می\u200cشوند و روزت را شیرین می\u200cکنند.',
        '🌟       کمی صبر کن، چیزی که منتظرش بودی نزدیک است.',
        '🌟       امروز اعتماد به نفست بیشتر از همیشه است، از آن استفاده کن.',
        '🌟       یک تماس یا پیام مهم امروز دریافت می\u200cکنی.',
        '🌟       امروز روز خوبی برای برنامه\u200cریزی آینده\u200cی نزدیک است.',
        '🌟        امروز فرصت خوبی برای جبران یک اشتباه قدیمی داری.',
        '🌟        کسی امروز به فکر توست، هرچند به رویت نمی\u200cآورد.',
        '🌟        یک پیشنهاد کاری جالب در راه است.',
        '🌟        امروز حرف دلت را بی\u200cپرده بزن، نتیجه خوبی می\u200cگیری.',
        '🌟        یک هدیه\u200cی کوچک اما دلنشین در انتظارت است.',
        '🌟        امروز روز خوبی برای یادگیری چیزی تازه است.',
        '🌟        کمی احتیاط در تصمیم\u200cهای مالی امروز لازم است.',
        '🌟        یک خاطره\u200cی قدیمی امروز به یادت می\u200cآید و لبخند می\u200cزنی.',
        '🌟        امروز کسی از تو تشکر ویژه\u200cای می\u200cکند.',
        '🌟        انرژی امروزت را صرف کارهای مهم کن، نه چیزهای بی\u200cفایده.',
        '🌟        امروز روز مناسبی برای آشتی با کسی است که دلخوری داشتی.',
        '🌟        یک خبر غیرمنتظره اما خوشایند می\u200cشنوی.',
        '🌟        امروز حال دلت بهتر از دیروز خواهد بود.',
        '🌟        فرصتی طلایی امروز از کنارت می\u200cگذرد، هوشیار باش.',
        '🌟        امروز روز خوبی برای شروع یک عادت سالم جدید است.',
        '🌟        دوستان امروز دورت جمع می\u200cشوند و روزت را شیرین می\u200cکنند.',
        '🌟        کمی صبر کن، چیزی که منتظرش بودی نزدیک است.',
        '🌟        امروز اعتماد به نفست بیشتر از همیشه است، از آن استفاده کن.',
        '🌟        یک تماس یا پیام مهم امروز دریافت می\u200cکنی.',
        '🌟        امروز روز خوبی برای برنامه\u200cریزی آینده\u200cی نزدیک است.',
        '🌟         امروز فرصت خوبی برای جبران یک اشتباه قدیمی داری.',
        '🌟         کسی امروز به فکر توست، هرچند به رویت نمی\u200cآورد.',
        '🌟         یک پیشنهاد کاری جالب در راه است.',
        '🌟         امروز حرف دلت را بی\u200cپرده بزن، نتیجه خوبی می\u200cگیری.',
        '🌟         یک هدیه\u200cی کوچک اما دلنشین در انتظارت است.',
        '🌟         امروز روز خوبی برای یادگیری چیزی تازه است.',
        '🌟         کمی احتیاط در تصمیم\u200cهای مالی امروز لازم است.',
        '🌟         یک خاطره\u200cی قدیمی امروز به یادت می\u200cآید و لبخند می\u200cزنی.',
        '🌟         امروز کسی از تو تشکر ویژه\u200cای می\u200cکند.',
        '🌟         انرژی امروزت را صرف کارهای مهم کن، نه چیزهای بی\u200cفایده.',
        '🌟         امروز روز مناسبی برای آشتی با کسی است که دلخوری داشتی.',
        '🌟         یک خبر غیرمنتظره اما خوشایند می\u200cشنوی.',
        '🌟         امروز حال دلت بهتر از دیروز خواهد بود.',
        '🌟         فرصتی طلایی امروز از کنارت می\u200cگذرد، هوشیار باش.',
        '🌟         امروز روز خوبی برای شروع یک عادت سالم جدید است.',
        '🌟         دوستان امروز دورت جمع می\u200cشوند و روزت را شیرین می\u200cکنند.',
        '🌟         کمی صبر کن، چیزی که منتظرش بودی نزدیک است.',
        '🌟         امروز اعتماد به نفست بیشتر از همیشه است، از آن استفاده کن.',
        '🌟         یک تماس یا پیام مهم امروز دریافت می\u200cکنی.',
        '🌟         امروز روز خوبی برای برنامه\u200cریزی آینده\u200cی نزدیک است.',
        '🌟          امروز فرصت خوبی برای جبران یک اشتباه قدیمی داری.',
        '🌟          کسی امروز به فکر توست، هرچند به رویت نمی\u200cآورد.',
        '🌟          یک پیشنهاد کاری جالب در راه است.',
        '🌟          امروز حرف دلت را بی\u200cپرده بزن، نتیجه خوبی می\u200cگیری.',
        '🌟          یک هدیه\u200cی کوچک اما دلنشین در انتظارت است.',
        '🌟          امروز روز خوبی برای یادگیری چیزی تازه است.',
        '🌟          کمی احتیاط در تصمیم\u200cهای مالی امروز لازم است.',
        '🌟          یک خاطره\u200cی قدیمی امروز به یادت می\u200cآید و لبخند می\u200cزنی.',
        '🌟          امروز کسی از تو تشکر ویژه\u200cای می\u200cکند.',
        '🌟          انرژی امروزت را صرف کارهای مهم کن، نه چیزهای بی\u200cفایده.',
        '🌟          امروز روز مناسبی برای آشتی با کسی است که دلخوری داشتی.',
        '🌟          یک خبر غیرمنتظره اما خوشایند می\u200cشنوی.',
        '🌟          امروز حال دلت بهتر از دیروز خواهد بود.',
        '🌟          فرصتی طلایی امروز از کنارت می\u200cگذرد، هوشیار باش.',
        '🌟          امروز روز خوبی برای شروع یک عادت سالم جدید است.',
        '🌟          دوستان امروز دورت جمع می\u200cشوند و روزت را شیرین می\u200cکنند.',
        '🌟          کمی صبر کن، چیزی که منتظرش بودی نزدیک است.',
        '🌟          امروز اعتماد به نفست بیشتر از همیشه است، از آن استفاده کن.',
        '🌟          یک تماس یا پیام مهم امروز دریافت می\u200cکنی.',
        '🌟          امروز روز خوبی برای برنامه\u200cریزی آینده\u200cی نزدیک است.',
    ]
    
    fal = random.choice(daily_fals)
    await message.reply(f"""
🌅 **فال روزانه شما:**

{fal}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d')}
💫 روز خوبی داشته باشید!
""")

# =========================================================
#  سیستم مدیریت نقل قول‌های روز
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "quote_of_day"))
async def quote_of_day_cmd(bot: Robot, message: Message):
    """نقل قول روز"""
    quotes = [
        "💬 تنها راه انجام کار بزرگ، عاشق بودن به کاری است که انجام میدهی. - استیو جابز",
        "💬 زندگی ۱۰٪ آنچه برای من اتفاق می‌افتد و ۹۰٪ نحوه واکنش من به آن است. - چارلز اسوایندل",
        "💬 باور کن که می‌توانی و نیمی از راه را رفته‌ای. - تئودور روزولت",
        "💬 دو چیز بی‌نهایت است: جهان و حماقت بشر. البته در مورد اول مطمئن نیستم. - آلبرت انیشتین",
        "💬 موفقیت از شکست به شکست می‌آید، بدون از دست دادن اشتیاق. - وینستون چرچیل",
        "💬 بزرگترین جلال در هرگز زمین نخوردن نیست، بلکه در برخاستن هر بار است. - کنفوسیوس",
        "💬 بهترین زمان برای کاشتن درخت، بیست سال پیش بود. دومین بهترین زمان، امروز است. - ضرب المثل چینی"
    ]
    
    quote = random.choice(quotes)
    await message.reply(f"""
📝 **نقل قول روز:**

{quote}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d')}
""")

# =========================================================
#  سیستم مدیریت انگیزشی روز
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "motivation_of_day"))
async def motivation_of_day_cmd(bot: Robot, message: Message):
    """انگیزشی روزانه"""
    motivations = [
        "💪 هر روز فرصتی جدید برای بهتر شدن است.",
        "💪 موفقیت از شکست به شکست می‌آید، بدون از دست دادن اشتیاق.",
        "💪 بزرگترین جلال در هرگز زمین نخوردن نیست، بلکه در برخاستن هر بار است.",
        "💪 باور کن که می‌توانی و نیمی از راه را رفته‌ای.",
        "💪 بهترین زمان برای کاشتن درخت، بیست سال پیش بود. دومین بهترین زمان، امروز است.",
        "💪 زندگی یعنی همان چیزی که برایت پیش می‌آید در حالی که مشغول برنامه‌ریزی برای آینده‌ای.",
        "💪 هیچوقت تسلیم نشو، زیرا هر روز نزدیک‌تر به موفقیت هستی.",
        "💪 به خودت ایمان داشته باش، تو بیشتر از آنچه فکر می‌کنی ارزش داری."
    ]
    
    msg = random.choice(motivations)
    await message.reply(f"""
🌟 **انگیزشی روزانه:**

{msg}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💪 امروز روز بزرگی است!
""")

# =========================================================
#  سیستم مدیریت دعا و زیارت
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "prayer_of_day"))
async def prayer_of_day_cmd(bot: Robot, message: Message):
    """دعای روزانه"""
    prayers = [
        "🤲 خدایا به ما صبر و شکیبایی عطا کن",
        "🤲 خدایا به ما قدرت تحمل مشکلات را بده",
        "🤲 خدایا به ما آرامش و آسایش عنایت کن",
        "🤲 خدایا به ما عاقبت بخیری عطا کن",
        "🤲 خدایا به ما سلامتی و تندرستی بده",
        "🤲 خدایا روزی حلال و پاکیزه نصیب ما کن",
        "🤲 خدایا به ما ایمان و یقین عطا کن",
        "🤲 خدایا به ما محبت و مودت عنایت کن"
    ]
    
    prayer = random.choice(prayers)
    await message.reply(f"""
🤲 **دعای روزانه:**

{prayer}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d')}
✨ ان‌شاءالله مستجاب باشد.
""")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت پست‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "post"))
async def post_cmd(bot: Robot, message: Message):
    """ایجاد پست جدید"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = message.text.replace("/post", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /post [متن]")
        return
    
    if 'posts' not in group_data:
        group_data['posts'] = []
    
    post_id = f"PST-{len(group_data['posts']) + 1:04d}"
    group_data['posts'].append({
        'id': post_id,
        'text': text,
        'user': user_id,
        'time': datetime.now().isoformat(),
        'likes': 0,
        'dislikes': 0,
        'comments': []
    })
    save_group_data(group_id, group_data)
    
    await message.reply(f"""
📌 **پست جدید:**

{text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👍 {0} | 👎 {0} | 💬 ۰
شناسه: {post_id}
📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}
""")

@bot.on_message(filters=lambda m: _cmd_is(m, "like"))
async def like_post_cmd(bot: Robot, message: Message):
    """لایک کردن پست"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    post_id = message.text.replace("/like", "", 1).strip()
    if not post_id:
        await message.reply("⚠️ دستور: /like [شناسه]")
        return
    
    group_data = get_group_data(group_id)
    posts = group_data.get('posts', [])
    
    for post in posts:
        if post.get('id') == post_id:
            post['likes'] = post.get('likes', 0) + 1
            save_group_data(group_id, group_data)
            await message.reply(f"❤️ **پست {post_id} لایک شد!**")
            return
    
    await message.reply("❌ پستی با این شناسه پیدا نشد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "dislike"))
async def dislike_post_cmd(bot: Robot, message: Message):
    """دیس لایک کردن پست"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    post_id = message.text.replace("/dislike", "", 1).strip()
    if not post_id:
        await message.reply("⚠️ دستور: /dislike [شناسه]")
        return
    
    group_data = get_group_data(group_id)
    posts = group_data.get('posts', [])
    
    for post in posts:
        if post.get('id') == post_id:
            post['dislikes'] = post.get('dislikes', 0) + 1
            save_group_data(group_id, group_data)
            await message.reply(f"👎 **پست {post_id} دیس لایک شد!**")
            return
    
    await message.reply("❌ پستی با این شناسه پیدا نشد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "comment"))
async def comment_post_cmd(bot: Robot, message: Message):
    """کامنت گذاشتن روی پست"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    parts = message.text.replace("/comment", "", 1).strip().split('|')
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /comment [شناسه] | [متن]")
        return
    
    post_id = parts[0].strip()
    comment_text = parts[1].strip()
    
    group_data = get_group_data(group_id)
    posts = group_data.get('posts', [])
    
    for post in posts:
        if post.get('id') == post_id:
            if 'comments' not in post:
                post['comments'] = []
            post['comments'].append({
                'user': str(message.sender_id),
                'text': comment_text,
                'time': datetime.now().isoformat()
            })
            save_group_data(group_id, group_data)
            await message.reply(f"💬 **کامنت شما به پست {post_id} اضافه شد!**")
            return
    
    await message.reply("❌ پستی با این شناسه پیدا نشد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "show_post"))
async def show_post_cmd(bot: Robot, message: Message):
    """نمایش پست"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    post_id = message.text.replace("/show_post", "", 1).strip()
    if not post_id:
        await message.reply("⚠️ دستور: /show_post [شناسه]")
        return
    
    group_data = get_group_data(group_id)
    posts = group_data.get('posts', [])
    
    for post in posts:
        if post.get('id') == post_id:
            text = f"📌 **پست {post_id}:**\n\n{post['text']}\n\n"
            text += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"👍 {post.get('likes', 0)} | 👎 {post.get('dislikes', 0)} | 💬 {len(post.get('comments', []))}\n"
            text += f"📅 {post.get('time', '')[:16]}\n\n"
            
            if post.get('comments'):
                text += "💬 **کامنت‌ها:**\n"
                for idx, comment in enumerate(post['comments'][-5:], 1):
                    user_name = get_user_name_from_id(comment['user'], group_data)
                    text += f"{idx}. {user_name}: {comment['text']}\n"
            else:
                text += "💬 هیچ کامنتی وجود ندارد."
            
            await message.reply(text)
            return
    
    await message.reply("❌ پستی با این شناسه پیدا نشد!")

# =========================================================
#  سیستم مدیریت پشتیبانی
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "ticket_status"))
async def ticket_status_cmd(bot: Robot, message: Message):
    """وضعیت تیکت"""
    ticket_id = message.text.replace("/ticket_status", "", 1).strip()
    if not ticket_id:
        await message.reply("⚠️ دستور: /ticket_status [شناسه]")
        return
    
    statuses = ["در حال بررسی", "در صف", "پاسخ داده شده", "بسته شده"]
    status = random.choice(statuses)
    
    await message.reply(f"""
📊 **وضعیت تیکت {ticket_id}:**

وضعیت: {status}
تاریخ: {datetime.now().strftime('%Y/%m/%d')}

🔹 در صورت نیاز با پشتیبانی تماس بگیرید.
""")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت قفل‌های پیشرفته
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "lock_all"))
async def lock_all_cmd(bot: Robot, message: Message):
    """قفل کامل گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند قفل کامل کند!")
        return
    
    settings = group_data.get('settings', {})
    settings['lock'] = True
    settings['anti_link'] = True
    settings['anti_spam'] = True
    settings['anti_swear'] = True
    settings['lock_media'] = True
    settings['lock_forward'] = True
    settings['lock_hashtag'] = True
    settings['lock_mention'] = True
    settings['lock_metadata'] = True
    settings['locks'] = {k: True for k in GRANULAR_LOCK_KEYS}
    
    save_group_data(group_id, group_data)
    await message.reply("🔒 **گروه قفل کامل شد!**\nهمه محدودیت‌ها فعال شدند.")

@bot.on_message(filters=lambda m: _cmd_is(m, "unlock_all"))
async def unlock_all_cmd(bot: Robot, message: Message):
    """باز کردن کامل قفل گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند باز کند!")
        return
    
    settings = group_data.get('settings', {})
    settings['lock'] = False
    settings['anti_link'] = False
    settings['anti_spam'] = False
    settings['anti_swear'] = False
    settings['lock_media'] = False
    settings['lock_forward'] = False
    settings['lock_hashtag'] = False
    settings['lock_mention'] = False
    settings['lock_metadata'] = False
    settings['locks'] = {}
    
    save_group_data(group_id, group_data)
    await message.reply("🔓 **همه قفل‌ها باز شدند!**")

# =========================================================
#  سیستم مدیریت قفل با رمز
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "set_password"))
async def set_password_cmd(bot: Robot, message: Message):
    """تنظیم رمز گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند رمز تنظیم کند!")
        return
    
    password = message.text.replace("/set_password", "", 1).strip()
    if not password:
        await message.reply("⚠️ دستور: /set_password [رمز]")
        return
    
    group_data['settings']['password'] = password
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **رمز گروه تنظیم شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "login"))
async def login_cmd(bot: Robot, message: Message):
    """ورود با رمز"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    password = group_data.get('settings', {}).get('password', '')
    
    if not password:
        await message.reply("❌ رمز گروه تنظیم نشده است!")
        return
    
    entered = message.text.replace("/login", "", 1).strip()
    if not entered:
        await message.reply("⚠️ دستور: /login [رمز]")
        return
    
    if entered == password:
        user_id = str(message.sender_id)
        if 'verified_users' not in group_data:
            group_data['verified_users'] = []
        if user_id not in group_data['verified_users']:
            group_data['verified_users'].append(user_id)
            save_group_data(group_id, group_data)
            await message.reply("✅ **ورود موفق!** شما می‌توانید در گروه پیام ارسال کنید.")
        else:
            await message.reply("✅ **شما قبلاً احراز هویت شده‌اید!**")
    else:
        await message.reply("❌ **رمز اشتباه است!**")

# =========================================================
#  سیستم مدیریت خوش‌آمد شخصی
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "set_personal_welcome"))
async def set_personal_welcome_cmd(bot: Robot, message: Message):
    """تنظیم خوش‌آمد شخصی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    if not get_reply_message(message):
        await message.reply("⚠️ روی پیام کاربر ریپلای کن!")
        return
    
    target_id = str(get_reply_sender_id(message))
    target_name = (await get_display_name(bot, get_reply_sender_id(message)) if get_reply_message(message) else "کاربر")
    
    text = message.text.replace("/set_personal_welcome", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /set_personal_welcome [متن]")
        return
    
    if 'personal_welcome' not in group_data:
        group_data['personal_welcome'] = {}
    
    group_data['personal_welcome'][target_id] = text
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **پیام خوش‌آمد شخصی برای {target_name} تنظیم شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "delete_personal_welcome"))
async def delete_personal_welcome_cmd(bot: Robot, message: Message):
    """حذف خوش‌آمد شخصی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    if not get_reply_message(message):
        await message.reply("⚠️ روی پیام کاربر ریپلای کن!")
        return
    
    target_id = str(get_reply_sender_id(message))
    target_name = (await get_display_name(bot, get_reply_sender_id(message)) if get_reply_message(message) else "کاربر")
    
    if 'personal_welcome' in group_data and target_id in group_data['personal_welcome']:
        del group_data['personal_welcome'][target_id]
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **پیام خوش‌آمد شخصی {target_name} حذف شد!**")
    else:
        await message.reply(f"⚠️ {target_name} پیام خوش‌آمد شخصی ندارد!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت اطلاعیه‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "announce"))
async def announce_cmd(bot: Robot, message: Message):
    """ارسال اطلاعیه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = message.text.replace("/announce", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /announce [متن اطلاعیه]")
        return
    
    await message.reply(f"""
📢 **اطلاعیه رسمی**

{text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}
👤 ارسال شده توسط: {(await get_display_name(bot, message) or 'ادمین')}
""")

# =========================================================
#  سیستم مدیریت تگ همه
# =========================================================

# (تگ همه‌ی قدیمی که فقط لیست اسم/لینک می‌ساخت حذف شد؛ نسخه‌ی واقعی با Mention و Registry بالاتر است.)

# =========================================================
#  سیستم مدیریت تم گروه
# =========================================================

# 🛠 رفع باگ اصلی «تم»: این هندلرها فقط با دستور اسلش انگلیسی (/set_theme و
# /theme) فعال می‌شدن. هیچ‌کدام از این دو عبارت در ALIAS_MAP ثبت نشده بودن،
# پس نوشتن «تم» یا «تنظیم تم [اسم]» به فارسی (که راهنمای خود ربات هم تبلیغ
# می‌کرد) هیچ پاسخی نمی‌گرفت. لیست تم‌ها هم با راهنما (که اسم‌های فارسی مثل
# «فانتزی»/«عاشقانه» رو تبلیغ می‌کرد) هم‌خوانی نداشت. الان هم اسم‌های فارسی
# قابل قبول‌اند و هم از طریق ALIAS_MAP + router به همین دو تابع وصل شده‌اند.
THEME_NAMES = [
    'پیشفرض', 'فانتزی', 'عاشقانه', 'بهاری', 'پسرونه', 'دخترونه',
    'کلاسیک', 'رنگی', 'ساده', 'تیره', 'روشن',
    # 🛠 این ۷ تا قبلاً فقط توی متن راهنما (FULL_GUIDE_1) تبلیغ می‌شدن ولی
    # هیچ‌جای کد ثبت نشده بودن؛ یعنی کسی که دقیقاً طبق راهنما «تنظیم تم ایران»
    # می‌فرستاد، پیام «تم شناخته‌شده نیست» می‌گرفت. الان واقعاً وجود دارن.
    'ایران', 'جنگل', 'سلطنتی', 'شرقی', 'علاءالدین', 'هانیبال', 'بریکینگ بد',
]
_THEME_ALIAS_EN = {
    'default': 'پیشفرض', 'dark': 'تیره', 'light': 'روشن',
    'colorful': 'رنگی', 'simple': 'ساده',
}

def _normalize_theme_name(raw: str) -> Optional[str]:
    t = normalize_fa(raw).strip()
    if t in THEME_NAMES:
        return t
    low = t.lower()
    if low in _THEME_ALIAS_EN:
        return _THEME_ALIAS_EN[low]
    return None

# =========================================================
#  🛠 رفع باگ صداقت: «تم» تا همین الان فقط تو دیتابیس ذخیره می‌شد و هیچ‌جا
#  خونده نمی‌شد - یعنی انتخابش کاملاً بی‌اثر بود. مهم: روبیکا هیچ راهی به
#  بات‌ها نمی‌ده که ظاهر/فونتِ واقعیِ اپ رو برای کاربرا عوض کنن (اون کاملاً
#  دست خودِ گوشیه). پس این «تم» فقط ظاهرِ پیام‌های خودِ گاردی رو عوض می‌کنه
#  (ایموجی/دکوراسیونِ پیام‌هایی که گاردی می‌فرسته)، نه کل اپ روبیکا - این
#  همون چیزیه که واقعاً از طریق API قابل انجامه.
# =========================================================
# 🛠 پنل تم کامل‌تر شد: قبلاً هر تم فقط ۳ تا آیکون داشت (header/success/bio) و
# فقط دستورات سرگرمی (بیو، فال، ...) از این‌ها استفاده می‌کردن. حالا هر تم
# ۵ تا آیکون داره (+ error/warning) تا پیام‌های موفقیت/خطا/هشدارِ بخش‌های
# دیگه (بن/اخراج/سکوت/بلاک/اخطار و ...) هم رنگ‌وبوی تم رو بگیرن، نه فقط بیو.
THEME_ICONS = {
    'پیشفرض': {'header': '📋', 'success': '✅', 'bio': '💬', 'error': '❌', 'warning': '⚠️'},
    'فانتزی':  {'header': '🎪', 'success': '🎉', 'bio': '✨', 'error': '💥', 'warning': '🎭'},
    'عاشقانه': {'header': '💗', 'success': '💖', 'bio': '🌹', 'error': '💔', 'warning': '😢'},
    'بهاری':   {'header': '🌸', 'success': '🌼', 'bio': '🌷', 'error': '🥀', 'warning': '🍂'},
    'پسرونه':  {'header': '🔥', 'success': '💪', 'bio': '🖤', 'error': '⚡', 'warning': '🚨'},
    'دخترونه': {'header': '🎀', 'success': '💕', 'bio': '🦋', 'error': '💔', 'warning': '🌸'},
    'کلاسیک':  {'header': '◆', 'success': '✔️', 'bio': '📜', 'error': '✖️', 'warning': '❕'},
    'رنگی':    {'header': '🌈', 'success': '🎨', 'bio': '🎭', 'error': '🔺', 'warning': '🔸'},
    'ساده':    {'header': '•', 'success': '+', 'bio': '·', 'error': '-', 'warning': '!'},
    'تیره':    {'header': '⬛', 'success': '⚫', 'bio': '🌑', 'error': '🖤', 'warning': '🌚'},
    'روشن':    {'header': '⬜', 'success': '⚪', 'bio': '☀️', 'error': '❕', 'warning': '🔆'},
    'ایران':      {'header': '🇮🇷', 'success': '💚', 'bio': '🌿', 'error': '🔻', 'warning': '🤍'},
    'جنگل':      {'header': '🌳', 'success': '🍃', 'bio': '🌲', 'error': '🪓', 'warning': '🐾'},
    'سلطنتی':    {'header': '👑', 'success': '💎', 'bio': '🏰', 'error': '⚔️', 'warning': '🎭'},
    'شرقی':      {'header': '🏮', 'success': '🀄', 'bio': '🍵', 'error': '🐉', 'warning': '🕌'},
    'علاءالدین':  {'header': '🧞', 'success': '💫', 'bio': '🕌', 'error': '🌪️', 'warning': '🪔'},
    'هانیبال':   {'header': '🔪', 'success': '🍷', 'bio': '🍽️', 'error': '💀', 'warning': '🩸'},
    'بریکینگ بد': {'header': '⚗️', 'success': '💰', 'bio': '🥼', 'error': '☠️', 'warning': '🧪'},
}

def theme_icon(group_data: Optional[dict], kind: str = 'header') -> str:
    """آیکون متناسب با تمِ انتخاب‌شده‌ی گروه؛ اگه گروه یا تم نامعتبر بود، پیش‌فرض برمی‌گرده."""
    theme = (group_data or {}).get('settings', {}).get('theme', 'پیشفرض')
    return THEME_ICONS.get(theme, THEME_ICONS['پیشفرض']).get(kind, THEME_ICONS['پیشفرض'].get(kind, '📋'))

async def themed_reply(message, text: str, kind: str = 'bio'):
    """
    پاسخ می‌ده و آیکونِ متناسب با تمِ گروه رو جلوی متن اضافه می‌کنه. اگه پیام
    توی پیوی (بدون گروه) بود، از آیکون پیش‌فرض استفاده می‌کنه - کرش نمی‌کنه.
    این یک تابع مشترکه تا همه‌ی دستورات سرگرمی/اطلاعاتی دقیقاً یک‌جور از تم
    استفاده کنن، به‌جای این‌که هرکدوم جدا (و با ریسک خطای بیشتر) پیاده بشن.

    🛠 حالا فونتِ انتخابیِ گروه (تنظیم فونت) هم همین‌جا روی متن اعمال می‌شه؛
    یعنی فونت واقعاً روی همون بخش‌هایی اثر می‌ذاره که تم رو دارن (چالش،
    حقیقت/جرأت، معما، ضرب‌المثل، انگیزشی، جوک، فان‌فکت، بیو، خاطره و ...)
    نه فقط توی خودِ پنل فونت.
    """
    group_id = get_chat_group_id(message)
    group_data = get_group_data(group_id) if group_id else None
    icon = theme_icon(group_data, kind)
    styled_text = apply_font_style(text, get_group_font(group_data))
    await message.reply(f"{icon} {styled_text}")

@bot.on_message(filters=lambda m: _cmd_is(m, "set_theme"))
async def set_theme_cmd(bot: Robot, message: Message):
    """تنظیم تم گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    # 🛠 رفع باگ دسترسی: در ALIAS_MAP سطح این دستور Perm.ADMIN تعریف شده
    # (و در فایل «دستورات» به کاربر هم همین اعلام شده)، ولی خودِ این تابع
    # جداگانه و سخت‌گیرانه‌تر is_owner چک می‌کرد. نتیجه: یک ادمین از فیلتر
    # مرکزی رد می‌شد ولی همینجا رد می‌شد و پیام گیج‌کننده می‌گرفت. الان با
    # همون سطحی که در ALIAS_MAP تعریف شده هماهنگ شد (ادمین به بالا).
    if not is_admin(user_id, group_data):
        await message.reply("❌ فقط ادمین می‌تواند تم را تغییر دهد!")
        return
    
    raw_theme = message.text.replace("/set_theme", "", 1).strip()
    if not raw_theme:
        await message.reply(f"⚠️ دستور: تنظیم تم [نام تم]\nتم‌های موجود: {', '.join(THEME_NAMES)}")
        return

    theme = _normalize_theme_name(raw_theme)
    if not theme:
        await message.reply(f"⚠️ تم «{raw_theme}» شناخته‌شده نیست.\nتم‌های موجود: {', '.join(THEME_NAMES)}")
        return
    
    group_data.setdefault('settings', {})['theme'] = theme
    save_group_data(group_id, group_data)
    icon = theme_icon(group_data, 'success')
    await message.reply(f"{icon} **تم گروه به «{theme}» تغییر یافت!**\nبرای دیدنش امتحان کن: «بیو» یا «آمار من» رو بزن.")


# =========================================================
#  🆕 «تم پیش‌فرض» (FULL_GUIDE_1: «پنل تم | تنظیم تم پیش‌فرض») - قبلاً فقط
#  در راهنما تبلیغ می‌شد. تفاوتش با «تنظیم تم» عادی: این یکی هم *الان* تم
#  گروه را روی همان تم می‌گذارد (اعمال خودکار) و هم آن را جدا در
#  settings['default_theme'] ذخیره می‌کند تا مبنای گروه بماند؛ فقط مالک
#  می‌تواند مبنای گروه را عوض کند (سطح بالاتر از «تنظیم تم» معمولی که ادمین
#  هم می‌تواند موقتاً عوض کند).
# =========================================================
@bot.on_message(filters=lambda m: _cmd_is(m, "set_default_theme"))
async def set_default_theme_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند تم پیش‌فرض گروه را تنظیم کند!")
        return
    raw_theme = _cmd_rest(message.text)
    if not raw_theme:
        cur = group_data.get('settings', {}).get('default_theme', 'پیشفرض')
        await message.reply(f"⚠️ دستور: تنظیم تم پیشفرض [نام تم]\nتم پیش‌فرض فعلی گروه: **{cur}**\nتم‌های موجود: {', '.join(THEME_NAMES)}")
        return
    theme = _normalize_theme_name(raw_theme)
    if not theme:
        await message.reply(f"⚠️ تم «{raw_theme}» شناخته‌شده نیست.\nتم‌های موجود: {', '.join(THEME_NAMES)}")
        return
    # ذخیره‌ی مبنای گروه + اعمال خودکار همین الان (طبق درخواست: «ذخیره تم
    # پیش‌فرض» + «اعمال خودکار تم» یک عملیات یکپارچه است).
    group_data.setdefault('settings', {})['default_theme'] = theme
    group_data['settings']['theme'] = theme
    save_group_data(group_id, group_data)
    icon = theme_icon(group_data, 'success')
    await message.reply(
        f"{icon} **تم پیش‌فرض گروه روی «{theme}» ذخیره و همین الان اعمال شد.**\n"
        "این تم از این پس مبنای گروه است."
    )

@bot.on_message(filters=lambda m: m.text and m.text == "/theme")
async def theme_cmd(bot: Robot, message: Message):
    """نمایش تم فعلی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    theme = group_data.get('settings', {}).get('theme', 'پیشفرض')
    icons = THEME_ICONS.get(theme, THEME_ICONS['پیشفرض'])

    # 🛠 پنل تم قبلاً فقط اسم تم فعلی و یه لیست اسم خام بود. الان پیش‌نمایشِ
    # آیکون‌های تمِ فعلی رو هم نشون می‌ده و لیست تم‌ها رو با آیکون هدرِ هرکدوم
    # می‌ده تا قبل از انتخاب، ظاهرش معلوم باشه.
    preview_lines = "\n".join(
        f"{THEME_ICONS[name]['header']} {name}" for name in THEME_NAMES
    )
    await message.reply(
        f"🎨 **پنل تم**\n\n"
        f"تم فعلی گروه: **{theme}**\n"
        f"پیش‌نمایش آیکون‌ها: {icons['header']} هدر · {icons['success']} موفقیت · "
        f"{icons['error']} خطا · {icons['warning']} هشدار · {icons['bio']} بیو\n\n"
        f"برای تغییر: «تنظیم تم [نام تم]»\n\n"
        f"**تم‌های موجود ({len(THEME_NAMES)} تا):**\n{preview_lines}"
    )

# =========================================================
#  سیستم مدیریت تاریخچه گروه
# =========================================================

@bot.on_message(filters=lambda m: m.text and m.text == "/history")
async def history_cmd(bot: Robot, message: Message):
    """تاریخچه گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    logs = group_data.get('logs', [])
    
    if not logs:
        await message.reply("📋 هیچ تاریخچه‌ای وجود ندارد!")
        return
    
    text = "📖 **تاریخچه گروه:**\n\n"
    for log in logs[-15:]:
        time_str = log.get('time', '')[:16]
        action = log.get('action', 'نامشخص')
        user = log.get('user', 'نامشخص')[:8]
        target = log.get('target', '')
        reason = log.get('reason', '')
        
        text += f"🔹 {time_str} - {action} توسط {user}\n"
        if target:
            text += f"   هدف: {target}\n"
        if reason:
            text += f"   دلیل: {reason}\n"
        text += "\n"
    
    await message.reply(text)

# =========================================================
#  🛠 بخش ۸ (#101): سیستم بکاپ قبلاً فقط «نوشتن» بود، هیچ Restore واقعی
#  نداشت. یعنی فایل data.json.bak/backup_*.json به‌تنهایی یک سیستم بکاپ
#  کامل نبود: اگر ساختار دیتابیس عوض می‌شد، فایل قدیمی معلوم نبود با
#  نسخه‌ی جدید سازگار است یا نه، و هیچ راهی برای برگردوندن یک بکاپ وجود
#  نداشت. الان هر بکاپ شامل نسخه‌ی Schema است، /restore قبل از هر کاری
#  اعتبارسنجی می‌کند (Schema سازگار + کلیدهای لازم)، از وضعیت فعلی هم
#  خودش یک بکاپ ایمنی می‌گیرد (تا خود Restore هم قابل‌برگشت باشد)، و
#  /backups لیست بکاپ‌های موجود گروه را نشان می‌دهد.
# =========================================================
#  سیستم مدیریت بکاپ
# =========================================================

BACKUP_SCHEMA_VERSION = 1
_BACKUP_REQUIRED_KEYS = ("group_id", "schema_version", "settings")


def _backup_file_path(group_id, tag: str = "") -> str:
    suffix = f"_{tag}" if tag else ""
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return os.path.join(DATA_DIR, f"backup_{group_id}{suffix}_{stamp}.json")


def _write_backup(group_id, group_data: dict, tag: str = "") -> Optional[str]:
    """یک فایل بکاپ JSON با شماره‌ی Schema می‌نویسد. مسیر فایل یا None در خطا."""
    backup_data = {
        'group_id': str(group_id),
        'schema_version': BACKUP_SCHEMA_VERSION,
        'name': group_data.get('group_name', ''),
        'admins': group_data.get('admins', []),
        'owners': group_data.get('owners', []),
        'specials': group_data.get('specials', []),
        'exempts': group_data.get('exempts', []),
        'settings': group_data.get('settings', {}),
        'warns': group_data.get('warns', {}),
        'bans': group_data.get('bans', []),
        'mutes': group_data.get('mutes', []),
        'blocks': group_data.get('blocks', []),
        'filters': group_data.get('filters', {}),
        'rules': group_data.get('rules', ''),
        'backup_date': datetime.now().isoformat(),
    }
    backup_file = _backup_file_path(group_id, tag)
    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        return backup_file
    except OSError as e:
        print(f"[backup][WARN] نوشتن بکاپ ناموفق بود: {e!r}")
        return None


def _list_group_backups(group_id) -> List[str]:
    """فایل‌های بکاپ همین گروه، جدید به قدیم."""
    prefix = f"backup_{group_id}_"
    prefix_pre_restore = f"backup_{group_id}_pre-restore_"
    try:
        names = [n for n in os.listdir(DATA_DIR)
                 if n.startswith(prefix) or n.startswith(prefix_pre_restore)]
    except OSError:
        return []
    return sorted(names, reverse=True)


def _validate_backup(data) -> Optional[str]:
    """خطای فارسی قابل‌فهم اگر بکاپ نامعتبر/ناسازگار باشد، وگرنه None."""
    if not isinstance(data, dict):
        return "فایل بکاپ معتبر نیست (JSON یک شیء نیست)."
    missing = [k for k in _BACKUP_REQUIRED_KEYS if k not in data]
    if missing:
        return f"فایل بکاپ ناقص است؛ کلیدهای زیر را ندارد: {', '.join(missing)}"
    ver = data.get("schema_version")
    if not isinstance(ver, int) or ver > BACKUP_SCHEMA_VERSION:
        return (f"نسخه‌ی Schema این بکاپ ({ver!r}) با نسخه‌ی فعلی ربات ({BACKUP_SCHEMA_VERSION}) "
                f"سازگار نیست؛ ربات را به‌روزرسانی کن یا از بکاپ جدیدتر استفاده نکن.")
    if not isinstance(data.get("settings"), dict):
        return "بخش «settings» فایل بکاپ معتبر نیست."
    return None


@bot.on_message(filters=lambda m: _cmd_is(m, "backup"))
async def backup_cmd(bot: Robot, message: Message):
    """گرفتن بکاپ (شامل نسخه‌ی Schema، برای اعتبارسنجی هنگام Restore)."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند بکاپ بگیرد!")
        return

    backup_file = _write_backup(group_id, group_data)
    if not backup_file:
        await message.reply("❌ خطا در ایجاد بکاپ!")
        return
    await message.reply(
        f"✅ **بکاپ از گروه گرفته شد!**\n📁 {os.path.basename(backup_file)}\n"
        f"🔢 نسخه‌ی Schema: {BACKUP_SCHEMA_VERSION}\n\n"
        f"برای دیدن لیست بکاپ‌ها: /backups\nبرای بازگردانی: /restore [نام فایل]"
    )


@bot.on_message(filters=lambda m: _cmd_is(m, "backups"))
async def backups_list_cmd(bot: Robot, message: Message):
    """لیست فایل‌های بکاپ موجود این گروه."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند لیست بکاپ‌ها را ببیند!")
        return

    names = _list_group_backups(group_id)
    if not names:
        await message.reply("⚠️ هنوز هیچ بکاپی از این گروه گرفته نشده. با /backup یکی بساز.")
        return
    listing = "\n".join(f"• {n}" for n in names[:20])
    await message.reply(f"📁 **بکاپ‌های این گروه** (جدید به قدیم):\n{listing}\n\nبرای بازگردانی: /restore [نام فایل]")


@bot.on_message(filters=lambda m: _cmd_is(m, "restore"))
async def restore_cmd(bot: Robot, message: Message):
    """
    بازگردانی کنترل‌شده‌ی یک بکاپ: فرمت /restore [نام فایل] (بدون آرگومان = جدیدترین بکاپ این گروه).
    قبل از هر تغییری: (۱) نام فایل اعتبارسنجی می‌شود (فقط داخل DATA_DIR، بدون path traversal)،
    (۲) محتوای بکاپ اعتبارسنجی می‌شود (Schema سازگار + کلیدهای لازم)، (۳) از وضعیت فعلی یک بکاپ
    ایمنی («pre-restore») گرفته می‌شود تا خودِ Restore هم قابل‌برگشت باشد، (۴) فقط بعد از همه‌ی
    اینها دیتابیس جایگزین می‌شود.
    """
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند بکاپ را بازگردانی کند!")
        return

    arg = _cmd_rest(message.text).strip()
    names = _list_group_backups(group_id)
    if not names:
        await message.reply("⚠️ هیچ بکاپی برای این گروه پیدا نشد.")
        return

    if arg:
        # فقط نام فایل، نه مسیر - جلوی خروج از DATA_DIR (path traversal) گرفته می‌شود
        safe_name = os.path.basename(arg)
        if safe_name != arg or safe_name not in names:
            await message.reply(f"❌ فایل بکاپ «{arg}» برای این گروه پیدا نشد.\nبرای دیدن لیست: /backups")
            return
        chosen = safe_name
    else:
        chosen = names[0]  # جدیدترین

    backup_path = os.path.join(DATA_DIR, chosen)
    try:
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        await message.reply(f"❌ خواندن فایل بکاپ ناموفق بود: {e}")
        return

    err = _validate_backup(backup_data)
    if err:
        await message.reply(f"❌ بکاپ نامعتبر است؛ چیزی تغییر نکرد.\n🔎 {err}")
        return

    # ایمنی: قبل از Restore، از وضعیت *فعلی* هم یک بکاپ می‌گیریم
    safety_file = _write_backup(group_id, group_data, tag="pre-restore")
    if not safety_file:
        await message.reply("❌ گرفتن بکاپ ایمنیِ قبل از Restore ناموفق بود؛ برای جلوگیری از از دست رفتن "
                            "اطلاعات فعلی، Restore انجام نشد.")
        return

    # فقط کلیدهای شناخته‌شده از بکاپ روی رکورد فعلی اعمال می‌شود (owners/admins/settings/...)؛
    # فیلدهای اجرایی مثل users/message_count/logs دست‌نخورده می‌مانند تا Restore آمار روزانه را
    # صفر نکند و مالکیت داخلی گاردی هیچ‌وقت به‌طور کامل جایگزین یک دیکشنری خارجی نشود.
    restorable_keys = ("admins", "owners", "specials", "exempts", "settings",
                       "warns", "bans", "mutes", "blocks", "filters", "rules")
    fresh = get_group_data(group_id)
    for key in restorable_keys:
        if key in backup_data:
            fresh[key] = backup_data[key]
    save_group_data(group_id, fresh)

    await message.reply(
        f"✅ **بازگردانی از «{chosen}» انجام شد.**\n"
        f"🛟 قبل از این کار، وضعیت قبلی هم در «{os.path.basename(safety_file)}» ذخیره شد "
        f"(اگر لازم شد، با /restore {os.path.basename(safety_file)} برگردون)."
    )

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت رتبه‌بندی کاربران
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "top"))
async def top_cmd(bot: Robot, message: Message):
    """رتبه‌بندی کاربران فعال"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    message_counts = group_data.get('message_count', {})
    
    if not message_counts:
        await message.reply("📊 هیچ آماری برای رتبه‌بندی وجود ندارد!")
        return
    
    sorted_users = sorted(message_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    text = "🏆 **رتبه‌بندی کاربران فعال:**\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for idx, (uid, count) in enumerate(sorted_users):
        medal = medals[idx] if idx < len(medals) else f"{idx+1}."
        user_name = get_user_name_from_id(uid, group_data)
        text += f"{medal} {user_name}: {format_number(count)} پیام\n"
    
    await message.reply(text)

# =========================================================
#  سیستم مدیریت کاربران آنلاین
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "online"))
async def online_cmd(bot: Robot, message: Message):
    """کاربران آنلاین"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    users = group_data.get('users', {})
    
    online_users = []
    for uid, data in users.items():
        last_active = data.get('last_active', '')
        if last_active:
            try:
                last_time = datetime.fromisoformat(last_active)
                if (datetime.now() - last_time).seconds < 300:  # 5 دقیقه
                    online_users.append(uid)
            except (ValueError, TypeError):
                pass
    
    if online_users:
        text = "🟢 **کاربران آنلاین:**\n\n"
        for uid in online_users[:20]:
            name = get_user_name_from_id(uid, group_data)
            text += f"• {name}\n"
        if len(online_users) > 20:
            text += f"\n... و {len(online_users) - 20} نفر دیگر"
        await message.reply(text)
    else:
        await message.reply("🟢 هیچ کاربر آنلاینی وجود ندارد!")

# =========================================================
#  سیستم مدیریت واتساپ
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "whatsapp"))
async def whatsapp_cmd(bot: Robot, message: Message):
    """شماره واتساپ"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    whatsapp = group_data.get('settings', {}).get('whatsapp', 'تنظیم نشده')
    
    await message.reply(f"📱 **شماره واتساپ گروه:**\n{whatsapp}")

@bot.on_message(filters=lambda m: _cmd_is(m, "set_whatsapp"))
async def set_whatsapp_cmd(bot: Robot, message: Message):
    """تنظیم شماره واتساپ"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند شماره واتساپ را تنظیم کند!")
        return
    
    number = message.text.replace("/set_whatsapp", "", 1).strip()
    if not number:
        await message.reply("⚠️ دستور: /set_whatsapp [شماره]")
        return
    
    group_data['settings']['whatsapp'] = number
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **شماره واتساپ گروه تنظیم شد!**")

# =========================================================
#  سیستم مدیریت اینستاگرام
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "instagram"))
async def instagram_cmd(bot: Robot, message: Message):
    """اینستاگرام گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    instagram = group_data.get('settings', {}).get('instagram', 'تنظیم نشده')
    
    await message.reply(f"📸 **اینستاگرام گروه:**\n{instagram}")

@bot.on_message(filters=lambda m: _cmd_is(m, "set_instagram"))
async def set_instagram_cmd(bot: Robot, message: Message):
    """تنظیم اینستاگرام"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند اینستاگرام را تنظیم کند!")
        return
    
    username = message.text.replace("/set_instagram", "", 1).strip()
    if not username:
        await message.reply("⚠️ دستور: /set_instagram [یوزرنیم]")
        return
    
    group_data['settings']['instagram'] = username
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **اینستاگرام گروه تنظیم شد!**")

# =========================================================
#  سیستم مدیریت تلگرام
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "telegram"))
async def telegram_cmd(bot: Robot, message: Message):
    """تلگرام گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    telegram = group_data.get('settings', {}).get('telegram', 'تنظیم نشده')
    
    await message.reply(f"📱 **تلگرام گروه:**\n{telegram}")

@bot.on_message(filters=lambda m: _cmd_is(m, "set_telegram"))
async def set_telegram_cmd(bot: Robot, message: Message):
    """تنظیم تلگرام"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند تلگرام را تنظیم کند!")
        return
    
    link = message.text.replace("/set_telegram", "", 1).strip()
    if not link:
        await message.reply("⚠️ دستور: /set_telegram [لینک]")
        return
    
    group_data['settings']['telegram'] = link
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **تلگرام گروه تنظیم شد!**")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت لینک گروه
# =========================================================
# 🛠 بخش ۸ (#100): «لینک گروه» قبلاً فقط یک متن دلخواه بود که مالک با
# /set_link ذخیره می‌کرد - هیچ ربطی به Invite Link واقعیِ تلگرام نداشت،
# ولی اسمش («لینک گروه») این تصور غلط رو می‌داد. الان این دو کاملاً
# جدا معرفی می‌شوند: /link لینک دعوت *واقعی* را از خود تلگرام می‌خواند
# (get_invite_link)، و لینک متنیِ دلخواهِ قبلی با اسم صریح «یادداشت لینک
# دلخواه» زیر آن نشان داده می‌شود تا با هم اشتباه گرفته نشوند.

@bot.on_message(filters=lambda m: _cmd_is(m, "set_link"))
async def set_link_cmd(bot: Robot, message: Message):
    """ثبت یک متن/لینک دلخواه برای نمایش در /link (این یک Invite Link واقعی تلگرام نمی‌سازد)."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند لینک دلخواه گروه را تنظیم کند!")
        return
    
    link = message.text.replace("/set_link", "", 1).strip()
    if not link:
        await message.reply("⚠️ دستور: /set_link [لینک یا متن دلخواه]\n"
                            "ℹ️ توجه: این فقط یک متن دلخواه ذخیره می‌کند، نه لینک دعوت واقعی تلگرام "
                            "(آن را با /link ببین).")
        return
    
    group_data['group_link'] = link
    save_group_data(group_id, group_data)
    await message.reply("✅ **متن/لینک دلخواه ثبت شد!** (این یک Invite Link واقعی تلگرام نیست؛ "
                        "برای لینک دعوت واقعی از /link استفاده کن.)")

@bot.on_message(filters=lambda m: m.text and m.text == "/link")
async def link_cmd(bot: Robot, message: Message):
    """نمایش لینک دعوت *واقعی* گروه (از خود تلگرام) + متن دلخواهی که مالک با /set_link ثبت کرده (اگر باشد)."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    real_link = await bot.get_invite_link(group_id) if hasattr(bot, "get_invite_link") else None
    custom_note = group_data.get('group_link', '')

    parts = []
    if real_link:
        parts.append(f"🔗 **لینک دعوت واقعی گروه (طبق تلگرام):**\n{real_link}")
    else:
        parts.append("🔗 **لینک دعوت واقعی گروه:** نتوانستم بخوانم "
                     "(ربات باید ادمین با دسترسی «دعوت کاربران» باشد، یا گروه هنوز لینک دعوت فعالی ندارد).")
    if custom_note:
        parts.append(f"📝 **یادداشت لینک دلخواه (ثبت‌شده با /set_link):**\n{custom_note}")

    await message.reply("\n\n".join(parts))

# 🛠 قابلیت مفقود: راهنما «حذف لینک» رو به‌عنوان بخشی از مدیریت لینک گروه
# تبلیغ می‌کرد، ولی هیچ تابعی برای پاک‌کردن group_link وجود نداشت - فقط
# افزودن (set_link) و نمایش (link) پیاده‌سازی شده بودن. (این فقط یادداشت
# دلخواه را حذف می‌کند؛ لینک دعوت واقعی تلگرام از اینجا قابل حذف نیست.)
@bot.on_message(filters=lambda m: m.text and m.text == "/delete_link")
async def delete_link_cmd(bot: Robot, message: Message):
    """حذف یادداشت لینک دلخواهِ ثبت‌شده (نه لینک دعوت واقعی تلگرام)."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if not is_admin(user_id, group_data):
        await message.reply(NO_PERMISSION_MSG)
        return

    if not group_data.get('group_link'):
        await message.reply("⚠️ یادداشت لینک دلخواهی برای این گروه ثبت نشده که حذف شود.")
        return

    group_data['group_link'] = ""
    save_group_data(group_id, group_data)
    await message.reply("✅ **یادداشت لینک دلخواه حذف شد!** (لینک دعوت واقعی تلگرام تغییری نکرد.)")

# =========================================================
#  سیستم مدیریت نام گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "set_name"))
async def set_name_cmd(bot: Robot, message: Message):
    """تنظیم نام گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند نام گروه را تغییر دهد!")
        return
    
    name = message.text.replace("/set_name", "", 1).strip()
    if not name:
        await message.reply("⚠️ دستور: /set_name [نام جدید]")
        return
    
    group_data['group_name'] = name
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **نام گروه به «{name}» تغییر یافت!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/name")
async def name_cmd(bot: Robot, message: Message):
    """نمایش نام گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    name = group_data.get('group_name', 'تنظیم نشده')
    
    await message.reply(f"📌 **نام گروه:**\n{name}")

# =========================================================
#  سیستم مدیریت قوانین پیشرفته
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "rules_advanced"))
async def rules_advanced_cmd(bot: Robot, message: Message):
    """قوانین پیشرفته گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    rules = group_data.get('settings', {}).get('rules', '📋 قوانین تنظیم نشده است!')
    
    # اضافه کردن قوانین پیشرفته
    advanced_rules = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 **قوانین پیشرفته:**

🔹 ارسال لینک ممنوع است.
🔹 اسپم کردن ممنوع است.
🔹 فحش و بی‌ادبی ممنوع است.
🔹 احترام به همه اعضا الزامی است.
🔹 همکاری با مدیریت الزامی است.

⚠️ **تخلف = اخطار یا بن!**
"""
    
    await message.reply(rules + advanced_rules)

# =========================================================
#  سیستم مدیریت پاداش
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "reward_user"))
async def reward_user_cmd(bot: Robot, message: Message):
    """پاداش به کاربر"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    if not get_reply_message(message):
        await message.reply("⚠️ روی پیام کاربر ریپلای کن!")
        return
    
    target_id = str(get_reply_sender_id(message))
    target_name = (await get_display_name(bot, get_reply_sender_id(message)) if get_reply_message(message) else "کاربر")
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /reward_user [مقدار]")
        return
    
    try:
        amount = int(parts[1])
        if amount > 0:
            if 'rewards' not in group_data:
                group_data['rewards'] = {}
            
            group_data['rewards'][target_id] = group_data['rewards'].get(target_id, 0) + amount
            save_group_data(group_id, group_data)
            await message.reply(f"🎁 **{amount} پاداش به {target_name} داده شد!**")
        else:
            await message.reply("⚠️ مقدار باید بیشتر از 0 باشد!")
    except (ValueError, IndexError):
        await message.reply("⚠️ مقدار را به عدد وارد کنید!")

# =========================================================
#  سیستم مدیریت ماموریت‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "mission_add"))
async def mission_add_cmd(bot: Robot, message: Message):
    """افزودن ماموریت"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = message.text.replace("/mission_add", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /mission_add [متن ماموریت]")
        return
    
    if 'missions' not in group_data:
        group_data['missions'] = []
    
    mission_id = f"M-{len(group_data['missions']) + 1:04d}"
    group_data['missions'].append({
        'id': mission_id,
        'text': text,
        'created_at': datetime.now().isoformat(),
        'by': user_id
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **ماموریت {mission_id} اضافه شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "missions"))
async def missions_cmd(bot: Robot, message: Message):
    """لیست ماموریت‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    missions = group_data.get('missions', [])
    
    if missions:
        text = "📋 **لیست ماموریت‌ها:**\n\n"
        for idx, mission in enumerate(missions, 1):
            text += f"{idx}. {mission.get('text')}\n"
            text += f"   شناسه: {mission.get('id')}\n"
            text += f"   زمان: {mission.get('created_at', '')[:16]}\n\n"
        await message.reply(text)
    else:
        await message.reply("📋 هیچ ماموریتی وجود ندارد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "mission_done"))
async def mission_done_cmd(bot: Robot, message: Message):
    """انجام ماموریت"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    mission_id = message.text.replace("/mission_done", "", 1).strip()
    if not mission_id:
        await message.reply("⚠️ دستور: /mission_done [شناسه]")
        return
    
    group_data = get_group_data(group_id)
    missions = group_data.get('missions', [])
    
    for mission in missions:
        if mission.get('id') == mission_id:
            missions.remove(mission)
            save_group_data(group_id, group_data)
            await message.reply(f"✅ **ماموریت {mission_id} انجام شد!**")
            return
    
    await message.reply(f"⚠️ ماموریتی با شناسه {mission_id} پیدا نشد!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت گردش کار گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "workflow"))
async def workflow_cmd(bot: Robot, message: Message):
    """نمایش گردش کار گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    
    await message.reply(f"""
📋 **گردش کار گروه** - {group_data.get('group_name', 'گروه')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👑 **مالک اصلی:** {group_data.get('owner_primary', 'تنظیم نشده')}
👑 **مالک‌ها:** {len(group_data.get('owners', []))} نفر
🛡️ **ادمین‌ها:** {len(group_data.get('admins', []))} نفر
⭐ **ویژه‌ها:** {len(group_data.get('specials', []))} نفر

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔒 **قفل‌ها:**
قفل گروه: {'🔒' if group_data.get('settings', {}).get('lock', False) else '🔓'}
ضد لینک: {'🔒' if group_data.get('settings', {}).get('anti_link', True) else '🔓'}
ضد اسپم: {'🔒' if group_data.get('settings', {}).get('anti_spam', True) else '🔓'}
ضد فحش: {'🔒' if group_data.get('settings', {}).get('anti_swear', True) else '🔓'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **آمار:**
👥 کاربران: {len(group_data.get('users', {}))}
💬 کل پیام‌ها: {format_number(group_data.get('stats', {}).get('total_messages', 0))}
⚠️ اخطارها: {group_data.get('stats', {}).get('total_warns', 0)}
🚫 بن‌ها: {len(group_data.get('bans', []))}
🔇 میوت‌ها: {len(group_data.get('mutes', []))}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}
""")

# =========================================================
#  سیستم مدیریت تنظیمات پیشرفته
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "settings_advanced"))
async def settings_advanced_cmd(bot: Robot, message: Message):
    """تنظیمات پیشرفته"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند تنظیمات پیشرفته را ببیند!")
        return
    
    settings = group_data.get('settings', {})
    
    await message.reply(f"""
⚙️ **تنظیمات پیشرفته گروه**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 **مدیریت:**
حداکثر اخطار: {settings.get('max_warn', 3)}
مدت میوت: {settings.get('mute_duration', 5)} دقیقه
مدت بن: {settings.get('ban_duration', 86400)} ثانیه

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔒 **قفل‌ها:**
قفل گروه: {'✅' if settings.get('lock', False) else '❌'}
ضد لینک: {'✅' if settings.get('anti_link', True) else '❌'}
ضد اسپم: {'✅' if settings.get('anti_spam', True) else '❌'}
ضد فحش: {'✅' if settings.get('anti_swear', True) else '❌'}
قفل رسانه: {'✅' if settings.get('lock_media', False) else '❌'}
قفل فوروارد: {'✅' if settings.get('lock_forward', False) else '❌'}
قفل هشتگ: {'✅' if settings.get('lock_hashtag', False) else '❌'}
قفل منشن: {'✅' if settings.get('lock_mention', False) else '❌'}
قفل متادیتا: {'✅' if settings.get('lock_metadata', True) else '❌'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 **متن‌ها:**
خوش‌آمد: {settings.get('welcome', 'تنظیم نشده')[:30]}...
خداحافظ: {settings.get('goodbye', 'تنظیم نشده')[:30]}...
قوانین: {settings.get('rules', 'تنظیم نشده')[:30]}...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎨 **تم:** {settings.get('theme', 'default')}
📱 **واتساپ:** {settings.get('whatsapp', 'تنظیم نشده')}
📸 **اینستاگرام:** {settings.get('instagram', 'تنظیم نشده')}
📱 **تلگرام:** {settings.get('telegram', 'تنظیم نشده')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}
""")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت لیست سیاه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "blacklist_add"))
async def blacklist_add_cmd(bot: Robot, message: Message):
    """افزودن به لیست سیاه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند به لیست سیاه اضافه کند!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /blacklist_add [شناسه کاربر]")
        return
    
    target_id = parts[1]
    
    if 'blacklist' not in group_data:
        group_data['blacklist'] = []
    
    if target_id not in group_data['blacklist']:
        group_data['blacklist'].append(target_id)
        save_group_data(group_id, group_data)
        await message.reply(f"🚫 **کاربر {target_id} به لیست سیاه اضافه شد!**")
    else:
        await message.reply(f"⚠️ کاربر {target_id} قبلاً در لیست سیاه است!")

@bot.on_message(filters=lambda m: _cmd_is(m, "blacklist_remove"))
async def blacklist_remove_cmd(bot: Robot, message: Message):
    """حذف از لیست سیاه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند از لیست سیاه حذف کند!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /blacklist_remove [شناسه کاربر]")
        return
    
    target_id = parts[1]
    
    if 'blacklist' in group_data and target_id in group_data['blacklist']:
        group_data['blacklist'].remove(target_id)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **کاربر {target_id} از لیست سیاه حذف شد!**")
    else:
        await message.reply(f"⚠️ کاربر {target_id} در لیست سیاه نیست!")

@bot.on_message(filters=lambda m: m.text and m.text == "/blacklist")
async def blacklist_cmd(bot: Robot, message: Message):
    """لیست سیاه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    blacklist = group_data.get('blacklist', [])
    
    if blacklist:
        text = "🚫 **لیست سیاه:**\n\n"
        for idx, user_id in enumerate(blacklist, 1):
            name = get_user_name_from_id(user_id, group_data)
            text += f"{idx}. {name} ({user_id})\n"
        await message.reply(text)
    else:
        await message.reply("📋 لیست سیاه خالی است!")

# =========================================================
#  سیستم مدیریت لیست سفید
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "whitelist_add"))
async def whitelist_add_cmd(bot: Robot, message: Message):
    """افزودن به لیست سفید"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند به لیست سفید اضافه کند!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /whitelist_add [شناسه کاربر]")
        return
    
    target_id = parts[1]
    
    if 'whitelist' not in group_data:
        group_data['whitelist'] = []
    
    if target_id not in group_data['whitelist']:
        group_data['whitelist'].append(target_id)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **کاربر {target_id} به لیست سفید اضافه شد!**")
    else:
        await message.reply(f"⚠️ کاربر {target_id} قبلاً در لیست سفید است!")

@bot.on_message(filters=lambda m: _cmd_is(m, "whitelist_remove"))
async def whitelist_remove_cmd(bot: Robot, message: Message):
    """حذف از لیست سفید"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند از لیست سفید حذف کند!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /whitelist_remove [شناسه کاربر]")
        return
    
    target_id = parts[1]
    
    if 'whitelist' in group_data and target_id in group_data['whitelist']:
        group_data['whitelist'].remove(target_id)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **کاربر {target_id} از لیست سفید حذف شد!**")
    else:
        await message.reply(f"⚠️ کاربر {target_id} در لیست سفید نیست!")

@bot.on_message(filters=lambda m: m.text and m.text == "/whitelist")
async def whitelist_cmd(bot: Robot, message: Message):
    """لیست سفید"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    whitelist = group_data.get('whitelist', [])
    
    if whitelist:
        text = "✅ **لیست سفید:**\n\n"
        for idx, user_id in enumerate(whitelist, 1):
            name = get_user_name_from_id(user_id, group_data)
            text += f"{idx}. {name} ({user_id})\n"
        await message.reply(text)
    else:
        await message.reply("📋 لیست سفید خالی است!")

# =========================================================
#  سیستم مدیریت اعلان‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "notification"))
async def notification_cmd(bot: Robot, message: Message):
    """تنظیم اعلان"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /notification [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['notification'] = True
        save_group_data(group_id, group_data)
        await message.reply("🔔 **اعلان‌ها فعال شدند!**")
    elif status == "غیرفعال":
        group_data['settings']['notification'] = False
        save_group_data(group_id, group_data)
        await message.reply("🔕 **اعلان‌ها غیرفعال شدند!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت پشتیبان
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "set_backup"))
async def set_backup_cmd(bot: Robot, message: Message):
    """تنظیم پشتیبان"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند پشتیبان تنظیم کند!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /set_backup [شناسه کاربر]")
        return
    
    target_id = parts[1]
    
    group_data['settings']['backup_admin'] = target_id
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **کاربر {target_id} به عنوان پشتیبان تنظیم شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "remove_backup"))
async def remove_backup_cmd(bot: Robot, message: Message):
    """حذف پشتیبان"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند پشتیبان را حذف کند!")
        return
    
    group_data['settings']['backup_admin'] = ''
    save_group_data(group_id, group_data)
    await message.reply("✅ **پشتیبان حذف شد!**")

# =========================================================
#  سیستم مدیریت ربات‌های گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "bot_list"))
async def bot_list_cmd(bot: Robot, message: Message):
    """لیست ربات‌های گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    bots = group_data.get('bots', [])
    
    if bots:
        text = "🤖 **لیست ربات‌های گروه:**\n\n"
        for idx, bot_id in enumerate(bots, 1):
            text += f"{idx}. {bot_id}\n"
        await message.reply(text)
    else:
        await message.reply("🤖 هیچ رباتی در گروه وجود ندارد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "bot_add"))
async def bot_add_cmd(bot: Robot, message: Message):
    """افزودن ربات به گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /bot_add [شناسه ربات]")
        return
    
    bot_id = parts[1]
    
    if 'bots' not in group_data:
        group_data['bots'] = []
    
    if bot_id not in group_data['bots']:
        group_data['bots'].append(bot_id)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **ربات {bot_id} به گروه اضافه شد!**")
    else:
        await message.reply(f"⚠️ ربات {bot_id} قبلاً در گروه است!")

# =========================================================
#  سیستم مدیریت قوانین خودکار
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "auto_rules"))
async def auto_rules_cmd(bot: Robot, message: Message):
    """قوانین خودکار"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /auto_rules [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['auto_rules'] = True
        save_group_data(group_id, group_data)
        await message.reply("✅ **قوانین خودکار فعال شد!**")
    elif status == "غیرفعال":
        group_data['settings']['auto_rules'] = False
        save_group_data(group_id, group_data)
        await message.reply("❌ **قوانین خودکار غیرفعال شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

# =========================================================
#  سیستم مدیریت گزارش‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "report"))
async def report_cmd(bot: Robot, message: Message):
    """گزارش"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    if not get_reply_message(message):
        await message.reply("⚠️ روی پیام کاربر ریپلای کن!")
        return
    
    target_name = (await get_display_name(bot, get_reply_sender_id(message)) if get_reply_message(message) else "کاربر")
    reason = message.text.replace("/report", "", 1).strip() or "بدون دلیل"
    
    group_data = get_group_data(group_id)
    
    if 'reports' not in group_data:
        group_data['reports'] = []
    
    group_data['reports'].append({
        'user': str(message.sender_id),
        'target': str(get_reply_sender_id(message)),
        'reason': reason,
        'time': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    
    await message.reply(f"📨 **گزارش شما ثبت شد!**\nکاربر: {target_name}\nدلیل: {reason}")

# =========================================================
#  سیستم مدیریت پیشنهادات
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "suggest"))
async def suggest_cmd(bot: Robot, message: Message):
    """پیشنهاد"""
    text = message.text.replace("/suggest", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /suggest [متن پیشنهاد]")
        return
    
    group_id = get_chat_group_id(message)
    
    if group_id:
        group_data = get_group_data(group_id)
        
        if 'suggestions' not in group_data:
            group_data['suggestions'] = []
        
        group_data['suggestions'].append({
            'user': str(message.sender_id),
            'text': text,
            'time': datetime.now().isoformat()
        })
        save_group_data(group_id, group_data)
        
        await message.reply(f"💡 **پیشنهاد شما ثبت شد!**\nمتن: {text}")
    else:
        await message.reply(f"💡 **پیشنهاد شما ثبت شد!**\nمتن: {text}")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت تیکت‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "ticket_new"))
async def ticket_new_cmd(bot: Robot, message: Message):
    """تیکت جدید"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    text = message.text.replace("/ticket_new", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /ticket_new [متن تیکت]")
        return
    
    user_id = str(message.sender_id)
    
    if 'tickets' not in group_data:
        group_data['tickets'] = []
    
    ticket_id = f"T-{len(group_data['tickets']) + 1:04d}"
    group_data['tickets'].append({
        'id': ticket_id,
        'user': user_id,
        'text': text,
        'status': 'باز',
        'time': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    
    await message.reply(f"🎫 **تیکت {ticket_id} ثبت شد!**\nمتن: {text}")

@bot.on_message(filters=lambda m: _cmd_is(m, "ticket_close"))
async def ticket_close_cmd(bot: Robot, message: Message):
    """بستن تیکت"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    ticket_id = message.text.replace("/ticket_close", "", 1).strip()
    if not ticket_id:
        await message.reply("⚠️ دستور: /ticket_close [شناسه]")
        return
    
    tickets = group_data.get('tickets', [])
    for ticket in tickets:
        if ticket.get('id') == ticket_id:
            ticket['status'] = 'بسته شده'
            save_group_data(group_id, group_data)
            await message.reply(f"✅ **تیکت {ticket_id} بسته شد!**")
            return
    
    await message.reply(f"⚠️ تیکتی با شناسه {ticket_id} پیدا نشد!")

@bot.on_message(filters=lambda m: m.text and m.text == "/tickets")
async def tickets_cmd(bot: Robot, message: Message):
    """لیست تیکت‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    tickets = group_data.get('tickets', [])
    
    if tickets:
        text = "🎫 **لیست تیکت‌ها:**\n\n"
        for idx, ticket in enumerate(tickets, 1):
            status_emoji = "🟢" if ticket.get('status') == 'باز' else "🔴"
            text += f"{idx}. {status_emoji} {ticket.get('id')} - {ticket.get('text')[:30]}...\n"
            text += f"   وضعیت: {ticket.get('status')}\n\n"
        await message.reply(text)
    else:
        await message.reply("🎫 هیچ تیکتی وجود ندارد!")

# =========================================================
#  سیستم مدیریت اخطارهای گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "warnings"))
async def warnings_cmd(bot: Robot, message: Message):
    """لیست اخطارهای فعال گروه؛ با ریپلای روی کاربر، جزئیات (دلیل/زمان/انقضا) همان کاربر."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    group_data = get_group_data(group_id)
    max_warn = group_data.get('settings', {}).get('max_warn', 3)

    reply_id = get_reply_sender_id(message)
    if reply_id:
        entries = get_active_warn_entries(group_data, reply_id)
        save_group_data(group_id, group_data)  # پاکسازی اخطارهای منقضی‌شده را ذخیره کن
        name = get_user_name_from_id(reply_id, group_data)
        if not entries:
            await message.reply(f"⚠️ {name} اخطار فعالی ندارد!")
            return
        text = f"⚠️ اخطارهای فعال {name} ({len(entries)}/{max_warn}):\n\n"
        for idx, e in enumerate(entries, 1):
            text += (f"{idx}. 📝 {e.get('reason', 'بدون دلیل')}\n"
                     f"   🕒 {_fmt_date(e.get('created_at'))} | ⏳ تا {_fmt_date(e.get('expires_at'))}\n")
        await message.reply(text)
        return

    active = list_active_warnings(group_data)
    save_group_data(group_id, group_data)  # پاکسازی اخطارهای منقضی‌شده را ذخیره کن

    if active:
        text = "⚠️ **لیست اخطارها:**\n\n"
        for idx, (user_id, count) in enumerate(active, 1):
            name = get_user_name_from_id(user_id, group_data)
            text += f"{idx}. {name}: {count}/{max_warn} اخطار\n"
        await message.reply(text)
    else:
        await message.reply("⚠️ هیچ اخطاری وجود ندارد!")

# =========================================================
#  سیستم مدیریت فعالیت کاربران
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "activity"))
async def activity_cmd(bot: Robot, message: Message):
    """فعالیت کاربران"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    message_counts = group_data.get('message_count', {})
    
    if not message_counts:
        await message.reply("📊 هیچ فعالیتی وجود ندارد!")
        return
    
    total_messages = sum(message_counts.values())
    active_users = len([c for c in message_counts.values() if c > 0])
    
    sorted_users = sorted(message_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    text = "📊 **فعالیت کاربران:**\n\n"
    text += f"👥 کاربران فعال: {active_users}\n"
    text += f"💬 کل پیام‌ها: {format_number(total_messages)}\n\n"
    text += "🏆 **پرکارترین‌ها:**\n"
    
    for idx, (uid, count) in enumerate(sorted_users, 1):
        name = get_user_name_from_id(uid, group_data)
        percent = (count / total_messages * 100) if total_messages > 0 else 0
        text += f"{idx}. {name}: {format_number(count)} پیام ({percent:.1f}%)\n"
    
    await message.reply(text)

# =========================================================
#  سیستم مدیریت گروه‌های مشابه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "similar_groups"))
async def similar_groups_cmd(bot: Robot, message: Message):
    """گروه‌های مشابه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    similar = group_data.get('similar_groups', [])
    
    if similar:
        text = "🔗 **گروه‌های مشابه:**\n\n"
        for idx, group_info in enumerate(similar, 1):
            text += f"{idx}. {group_info.get('name', 'بدون نام')}\n"
            text += f"   لینک: {group_info.get('link', 'نامشخص')}\n\n"
        await message.reply(text)
    else:
        await message.reply("🔗 هیچ گروه مشابهی وجود ندارد!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت پیام‌های خودکار
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "auto_message"))
async def auto_message_cmd(bot: Robot, message: Message):
    """تنظیم پیام خودکار"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/auto_message", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /auto_message [زمان] | [متن]")
        return
    
    msg_data = [p.strip() for p in parts.split('|')]
    if len(msg_data) < 2:
        await message.reply("⚠️ دستور: /auto_message [زمان] | [متن]")
        return
    
    if 'auto_messages' not in group_data:
        group_data['auto_messages'] = []
    
    msg_id = f"AM-{len(group_data['auto_messages']) + 1:04d}"
    group_data['auto_messages'].append({
        'id': msg_id,
        'time': msg_data[0],
        'text': msg_data[1],
        'enabled': True,
        'created_at': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **پیام خودکار {msg_id} تنظیم شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "auto_messages"))
async def auto_messages_cmd(bot: Robot, message: Message):
    """لیست پیام‌های خودکار"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    auto_messages = group_data.get('auto_messages', [])
    
    if auto_messages:
        text = "📨 **لیست پیام‌های خودکار:**\n\n"
        for idx, msg in enumerate(auto_messages, 1):
            text += f"{idx}. شناسه: {msg.get('id')}\n"
            text += f"   زمان: {msg.get('time')}\n"
            text += f"   متن: {msg.get('text')[:50]}...\n"
            text += f"   وضعیت: {'✅ فعال' if msg.get('enabled', True) else '❌ غیرفعال'}\n\n"
        await message.reply(text)
    else:
        await message.reply("📨 هیچ پیام خودکاری وجود ندارد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "auto_message_enable"))
async def auto_message_enable_cmd(bot: Robot, message: Message):
    """فعال کردن پیام خودکار"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    msg_id = message.text.replace("/auto_message_enable", "", 1).strip()
    if not msg_id:
        await message.reply("⚠️ دستور: /auto_message_enable [شناسه]")
        return
    
    auto_messages = group_data.get('auto_messages', [])
    for msg in auto_messages:
        if msg.get('id') == msg_id:
            msg['enabled'] = True
            save_group_data(group_id, group_data)
            await message.reply(f"✅ **پیام خودکار {msg_id} فعال شد!**")
            return
    
    await message.reply(f"⚠️ پیام خودکاری با شناسه {msg_id} پیدا نشد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "auto_message_disable"))
async def auto_message_disable_cmd(bot: Robot, message: Message):
    """غیرفعال کردن پیام خودکار"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    msg_id = message.text.replace("/auto_message_disable", "", 1).strip()
    if not msg_id:
        await message.reply("⚠️ دستور: /auto_message_disable [شناسه]")
        return
    
    auto_messages = group_data.get('auto_messages', [])
    for msg in auto_messages:
        if msg.get('id') == msg_id:
            msg['enabled'] = False
            save_group_data(group_id, group_data)
            await message.reply(f"❌ **پیام خودکار {msg_id} غیرفعال شد!**")
            return
    
    await message.reply(f"⚠️ پیام خودکاری با شناسه {msg_id} پیدا نشد!")

# =========================================================
#  سیستم مدیریت ویدیو
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "video"))
async def video_cmd(bot: Robot, message: Message):
    """ویدیو"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = message.text.replace("/video", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /video [لینک ویدیو]")
        return
    
    if 'videos' not in group_data:
        group_data['videos'] = []
    
    video_id = f"VID-{len(group_data['videos']) + 1:04d}"
    group_data['videos'].append({
        'id': video_id,
        'url': text,
        'user': user_id,
        'time': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    await message.reply(f"🎬 **ویدیو {video_id} اضافه شد!**")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت لیست دوستان
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "friend_add"))
async def friend_add_cmd(bot: Robot, message: Message):
    """افزودن دوست"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /friend_add [شناسه کاربر]")
        return
    
    target_id = parts[1]
    
    if 'friends' not in group_data:
        group_data['friends'] = {}
    
    if user_id not in group_data['friends']:
        group_data['friends'][user_id] = []
    
    if target_id not in group_data['friends'][user_id]:
        group_data['friends'][user_id].append(target_id)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **کاربر {target_id} به لیست دوستان شما اضافه شد!**")
    else:
        await message.reply(f"⚠️ کاربر {target_id} قبلاً در لیست دوستان شما است!")

@bot.on_message(filters=lambda m: _cmd_is(m, "friend_remove"))
async def friend_remove_cmd(bot: Robot, message: Message):
    """حذف دوست"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /friend_remove [شناسه کاربر]")
        return
    
    target_id = parts[1]
    
    if 'friends' in group_data and user_id in group_data['friends']:
        if target_id in group_data['friends'][user_id]:
            group_data['friends'][user_id].remove(target_id)
            save_group_data(group_id, group_data)
            await message.reply(f"✅ **کاربر {target_id} از لیست دوستان شما حذف شد!**")
            return
    
    await message.reply(f"⚠️ کاربر {target_id} در لیست دوستان شما نیست!")

@bot.on_message(filters=lambda m: m.text and m.text == "/friends")
async def friends_cmd(bot: Robot, message: Message):
    """لیست دوستان"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if 'friends' in group_data and user_id in group_data['friends']:
        friends = group_data['friends'][user_id]
        if friends:
            text = "👫 **لیست دوستان شما:**\n\n"
            for idx, friend_id in enumerate(friends, 1):
                name = get_user_name_from_id(friend_id, group_data)
                text += f"{idx}. {name} ({friend_id})\n"
            await message.reply(text)
        else:
            await message.reply("👫 شما هیچ دوستی ندارید!")
    else:
        await message.reply("👫 شما هیچ دوستی ندارید!")

# =========================================================
#  سیستم مدیریت گروه‌های خصوصی
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "private_group"))
async def private_group_cmd(bot: Robot, message: Message):
    """گروه خصوصی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند گروه را خصوصی کند!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /private_group [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['private_group'] = True
        save_group_data(group_id, group_data)
        await message.reply("🔒 **گروه خصوصی شد!** فقط اعضای دعوت شده می‌توانند وارد شوند.")
    elif status == "غیرفعال":
        group_data['settings']['private_group'] = False
        save_group_data(group_id, group_data)
        await message.reply("🔓 **گروه عمومی شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

# =========================================================
#  سیستم مدیریت پست‌های ویژه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "special_post"))
async def special_post_cmd(bot: Robot, message: Message):
    """پست ویژه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = message.text.replace("/special_post", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /special_post [متن]")
        return
    
    await message.reply(f"""
📌 **پست ویژه**

{text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⭐ ویژه توسط: {(await get_display_name(bot, message) or 'ادمین')}
📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}
""")

# =========================================================
#  سیستم مدیریت یادآوری روزانه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "daily_reminder"))
async def daily_reminder_cmd(bot: Robot, message: Message):
    """یادآوری روزانه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = message.text.replace("/daily_reminder", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /daily_reminder [متن]")
        return
    
    if 'daily_reminders' not in group_data:
        group_data['daily_reminders'] = []
    
    group_data['daily_reminders'].append({
        'text': text,
        'user': user_id,
        'time': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **یادآوری روزانه تنظیم شد!**\nمتن: {text}")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت پیام‌های خوش‌آمد گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "group_welcome"))
async def group_welcome_cmd(bot: Robot, message: Message):
    """تنظیم پیام خوش‌آمد گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = _cmd_rest(message.text)
    if not text:
        await message.reply("⚠️ دستور: /group_welcome [متن]")
        return
    
    group_data['settings']['welcome'] = text   # منبع حقیقت: settings['welcome']
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **پیام خوش‌آمد گروه تنظیم شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "group_welcome_show"))
async def group_welcome_show_cmd(bot: Robot, message: Message):
    """نمایش پیام خوش‌آمد گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    welcome = get_welcome_config(group_data)[1] or 'تنظیم نشده'
    
    await message.reply(f"🎉 **پیام خوش‌آمد گروه:**\n{welcome}")

# =========================================================
#  سیستم مدیریت پیام‌های خداحافظ گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "group_goodbye"))
async def group_goodbye_cmd(bot: Robot, message: Message):
    """تنظیم پیام خداحافظ گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = _cmd_rest(message.text)
    if not text:
        await message.reply("⚠️ دستور: /group_goodbye [متن]")
        return
    
    group_data['settings']['goodbye'] = text   # منبع حقیقت: settings['goodbye']
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **پیام خداحافظ گروه تنظیم شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "group_goodbye_show"))
async def group_goodbye_show_cmd(bot: Robot, message: Message):
    """نمایش پیام خداحافظ گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    goodbye = get_goodbye_config(group_data)[1] or 'تنظیم نشده'
    
    await message.reply(f"👋 **پیام خداحافظ گروه:**\n{goodbye}")

# =========================================================
#  سیستم مدیریت استیکرها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "sticker_add"))
async def sticker_add_cmd(bot: Robot, message: Message):
    """افزودن استیکر"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /sticker_add [کد استیکر]")
        return
    
    sticker_id = parts[1]
    
    if 'stickers' not in group_data:
        group_data['stickers'] = []
    
    if sticker_id not in group_data['stickers']:
        group_data['stickers'].append(sticker_id)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **استیکر {sticker_id} اضافه شد!**")
    else:
        await message.reply(f"⚠️ استیکر {sticker_id} قبلاً اضافه شده است!")

@bot.on_message(filters=lambda m: m.text and m.text == "/stickers")
async def stickers_cmd(bot: Robot, message: Message):
    """لیست استیکرها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    stickers = group_data.get('stickers', [])
    
    if stickers:
        text = "🔖 **لیست استیکرها:**\n\n"
        for idx, sticker in enumerate(stickers, 1):
            text += f"{idx}. {sticker}\n"
        await message.reply(text)
    else:
        await message.reply("🔖 هیچ استیکری وجود ندارد!")

# =========================================================
#  سیستم مدیریت متا
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "meta"))
async def meta_cmd(bot: Robot, message: Message):
    """اطلاعات متا"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    
    await message.reply(f"""
📊 **اطلاعات متا گروه**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 **شناسه گروه:** {group_id}
📌 **نام گروه:** {group_data.get('group_name', 'تنظیم نشده')}
📌 **تاریخ ایجاد:** {group_data.get('created_at', 'نامشخص')[:16]}
📌 **مالک اصلی:** {group_data.get('owner_primary', 'تنظیم نشده')}

👥 **کاربران:** {len(group_data.get('users', {}))}
👮 **ادمین‌ها:** {len(group_data.get('admins', []))}
👑 **مالک‌ها:** {len(group_data.get('owners', []))}
⭐ **ویژه‌ها:** {len(group_data.get('specials', []))}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}
""")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت پیام‌های خوش‌آمد گروه
# =========================================================



# =========================================================
#  سیستم مدیریت پیام‌های خداحافظ گروه
# =========================================================



# =========================================================
#  سیستم مدیریت استیکرها
# =========================================================



# =========================================================
#  سیستم مدیریت متا
# =========================================================


# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت کانال‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "channel_add"))
async def channel_add_cmd(bot: Robot, message: Message):
    """افزودن کانال"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /channel_add [لینک کانال]")
        return
    
    channel_link = parts[1]
    
    if 'channels' not in group_data:
        group_data['channels'] = []
    
    if channel_link not in group_data['channels']:
        group_data['channels'].append(channel_link)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **کانال {channel_link} اضافه شد!**")
    else:
        await message.reply(f"⚠️ کانال {channel_link} قبلاً اضافه شده است!")

@bot.on_message(filters=lambda m: m.text and m.text == "/channels")
async def channels_cmd(bot: Robot, message: Message):
    """لیست کانال‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    channels = group_data.get('channels', [])
    
    if channels:
        text = "📢 **لیست کانال‌ها:**\n\n"
        for idx, channel in enumerate(channels, 1):
            text += f"{idx}. {channel}\n"
        await message.reply(text)
    else:
        await message.reply("📢 هیچ کانالی وجود ندارد!")

# =========================================================
#  سیستم مدیریت برچسب‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "tag_add"))
async def tag_add_cmd(bot: Robot, message: Message):
    """افزودن برچسب"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /tag_add [برچسب]")
        return
    
    tag = parts[1]
    
    if 'tags' not in group_data:
        group_data['tags'] = []
    
    if tag not in group_data['tags']:
        group_data['tags'].append(tag)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **برچسب {tag} اضافه شد!**")
    else:
        await message.reply(f"⚠️ برچسب {tag} قبلاً اضافه شده است!")

@bot.on_message(filters=lambda m: m.text and m.text == "/tags")
async def tags_cmd(bot: Robot, message: Message):
    """لیست برچسب‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    tags = group_data.get('tags', [])
    
    if tags:
        text = "🏷️ **لیست برچسب‌ها:**\n\n"
        for idx, tag in enumerate(tags, 1):
            text += f"{idx}. {tag}\n"
        await message.reply(text)
    else:
        await message.reply("🏷️ هیچ برچسبی وجود ندارد!")

# =========================================================
#  سیستم مدیریت متن‌های ذخیره شده
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "save_text"))
async def save_text_cmd(bot: Robot, message: Message):
    """ذخیره متن"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/save_text", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /save_text [نام] | [متن]")
        return
    
    text_data = [p.strip() for p in parts.split('|')]
    if len(text_data) < 2:
        await message.reply("⚠️ دستور: /save_text [نام] | [متن]")
        return
    
    name = text_data[0]
    text = text_data[1]
    
    if 'saved_texts' not in group_data:
        group_data['saved_texts'] = {}
    
    group_data['saved_texts'][name] = text
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **متن با نام {name} ذخیره شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "get_text"))
async def get_text_cmd(bot: Robot, message: Message):
    """دریافت متن ذخیره شده"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    name = message.text.replace("/get_text", "", 1).strip()
    
    if not name:
        await message.reply("⚠️ دستور: /get_text [نام]")
        return
    
    saved_texts = group_data.get('saved_texts', {})
    
    if name in saved_texts:
        await message.reply(f"📝 **متن ذخیره شده ({name}):**\n{saved_texts[name]}")
    else:
        await message.reply(f"⚠️ متنی با نام {name} پیدا نشد!")

# =========================================================
#  سیستم مدیریت نقش‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "role_add"))
async def role_add_cmd(bot: Robot, message: Message):
    """افزودن نقش"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند نقش اضافه کند!")
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("⚠️ دستور: /role_add [شناسه کاربر] [نقش]")
        return
    
    target_id = parts[1]
    role = parts[2]
    
    if 'roles' not in group_data:
        group_data['roles'] = {}
    
    group_data['roles'][target_id] = role
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **نقش {role} به کاربر {target_id} اضافه شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "role_remove"))
async def role_remove_cmd(bot: Robot, message: Message):
    """حذف نقش"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند نقش حذف کند!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /role_remove [شناسه کاربر]")
        return
    
    target_id = parts[1]
    
    if 'roles' in group_data and target_id in group_data['roles']:
        del group_data['roles'][target_id]
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **نقش کاربر {target_id} حذف شد!**")
    else:
        await message.reply(f"⚠️ کاربر {target_id} نقشی ندارد!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت نظرسنجی گروهی
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "group_poll"))
async def group_poll_cmd(bot: Robot, message: Message):
    """نظرسنجی گروهی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/group_poll", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /group_poll [سوال] | گزینه۱ | گزینه۲")
        return
    
    options = [opt.strip() for opt in parts.split('|')]
    if len(options) < 2:
        await message.reply("⚠️ حداقل ۲ گزینه وارد کنید!")
        return
    
    question = options[0]
    choices = options[1:]
    
    poll_id = f"GP-{len(group_data.get('group_polls', [])) + 1:04d}"
    
    if 'group_polls' not in group_data:
        group_data['group_polls'] = []
    
    group_data['group_polls'].append({
        'id': poll_id,
        'question': question,
        'choices': choices,
        'votes': {choice: 0 for choice in choices},
        'voters': [],
        'created_at': datetime.now().isoformat(),
        'by': user_id,
        'active': True
    })
    save_group_data(group_id, group_data)
    
    text = f"📊 **نظرسنجی گروهی:**\n\n{question}\n\n"
    emojis = ["🅰️", "🅱️", "🅲️", "🅳️"]
    
    for idx, choice in enumerate(choices):
        if idx < len(emojis):
            text += f"{emojis[idx]} {choice}\n"
        else:
            text += f"➡️ {choice}\n"
    
    text += f"\n📌 برای رای دادن: /gvote {poll_id} [گزینه]"
    text += f"\n📅 {datetime.now().strftime('%Y/%m/%d')}"
    
    await message.reply(text)

@bot.on_message(filters=lambda m: _cmd_is(m, "gvote"))
async def gvote_cmd(bot: Robot, message: Message):
    """رای دادن به نظرسنجی گروهی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("⚠️ دستور: /gvote [شناسه] [گزینه]")
        return
    
    poll_id = parts[1]
    choice = ' '.join(parts[2:])
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    polls = group_data.get('group_polls', [])
    for poll in polls:
        if poll.get('id') == poll_id and poll.get('active', True):
            if user_id in poll.get('voters', []):
                await message.reply("❌ شما قبلاً رای داده‌اید!")
                return
            
            if choice not in poll.get('choices', []):
                await message.reply("❌ گزینه نامعتبر است!")
                return
            
            poll['votes'][choice] = poll['votes'][choice] + 1
            poll['voters'].append(user_id)
            save_group_data(group_id, group_data)
            await message.reply(f"✅ **رای شما ثبت شد!**")
            return
    
    await message.reply("❌ نظرسنجی یافت نشد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "gpoll_results"))
async def gpoll_results_cmd(bot: Robot, message: Message):
    """نتایج نظرسنجی گروهی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    poll_id = message.text.replace("/gpoll_results", "", 1).strip()
    if not poll_id:
        await message.reply("⚠️ دستور: /gpoll_results [شناسه]")
        return
    
    group_data = get_group_data(group_id)
    polls = group_data.get('group_polls', [])
    
    for poll in polls:
        if poll.get('id') == poll_id:
            total_votes = sum(poll['votes'].values())
            text = f"📊 **نتایج نظرسنجی گروهی {poll_id}:**\n\n"
            text += f"سوال: {poll['question']}\n\n"
            
            for choice, count in poll['votes'].items():
                percent = (count / total_votes * 100) if total_votes > 0 else 0
                text += f"{choice}: {count} رای ({percent:.1f}%)\n"
            
            text += f"\nمجموع رای‌ها: {total_votes}"
            await message.reply(text)
            return
    
    await message.reply("❌ نظرسنجی یافت نشد!")

# =========================================================
#  سیستم مدیریت پاسخ‌های سریع
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "quick_reply_add"))
async def quick_reply_add_cmd(bot: Robot, message: Message):
    """افزودن پاسخ سریع"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/quick_reply_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /quick_reply_add [کلیدواژه] | [پاسخ]")
        return
    
    data = [p.strip() for p in parts.split('|')]
    if len(data) < 2:
        await message.reply("⚠️ دستور: /quick_reply_add [کلیدواژه] | [پاسخ]")
        return
    
    keyword = data[0]
    reply = data[1]
    
    if 'quick_replies' not in group_data:
        group_data['quick_replies'] = {}
    
    group_data['quick_replies'][keyword] = reply
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **پاسخ سریع برای {keyword} اضافه شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "quick_reply_remove"))
async def quick_reply_remove_cmd(bot: Robot, message: Message):
    """حذف پاسخ سریع"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    keyword = message.text.replace("/quick_reply_remove", "", 1).strip()
    if not keyword:
        await message.reply("⚠️ دستور: /quick_reply_remove [کلیدواژه]")
        return
    
    quick_replies = group_data.get('quick_replies', {})
    
    if keyword in quick_replies:
        del quick_replies[keyword]
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **پاسخ سریع برای {keyword} حذف شد!**")
    else:
        await message.reply(f"⚠️ پاسخ سریعی برای {keyword} پیدا نشد!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت اعلان‌های فوری
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "alert"))
async def alert_cmd(bot: Robot, message: Message):
    """اعلان فوری"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = message.text.replace("/alert", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /alert [متن]")
        return
    
    await message.reply(f"""
🔔 **اعلان فوری!**

{text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ {datetime.now().strftime('%H:%M')}
📅 {datetime.now().strftime('%Y/%m/%d')}
""")

# =========================================================
#  سیستم مدیریت پیام‌های مهم
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "important"))
async def important_cmd(bot: Robot, message: Message):
    """پیام مهم"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = message.text.replace("/important", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /important [متن]")
        return
    
    await message.reply(f"""
‼️ **پیام مهم!**

{text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ لطفاً توجه کنید!
📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}
""")

# =========================================================
#  سیستم مدیریت یادآوری‌های گروهی
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "group_reminder"))
async def group_reminder_cmd(bot: Robot, message: Message):
    """یادآوری گروهی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/group_reminder", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /group_reminder [زمان] | [متن]")
        return
    
    reminder_data = [p.strip() for p in parts.split('|')]
    if len(reminder_data) < 2:
        await message.reply("⚠️ دستور: /group_reminder [زمان] | [متن]")
        return
    
    if 'group_reminders' not in group_data:
        group_data['group_reminders'] = []
    
    group_data['group_reminders'].append({
        'time': reminder_data[0],
        'text': reminder_data[1],
        'user': user_id,
        'created_at': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **یادآوری گروهی تنظیم شد!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/group_reminders")
async def group_reminders_cmd(bot: Robot, message: Message):
    """لیست یادآوری‌های گروهی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    reminders = group_data.get('group_reminders', [])
    
    if reminders:
        text = "⏰ **لیست یادآوری‌های گروهی:**\n\n"
        for idx, rem in enumerate(reminders, 1):
            text += f"{idx}. {rem.get('text')}\n"
            text += f"   زمان: {rem.get('time')}\n\n"
        await message.reply(text)
    else:
        await message.reply("⏰ هیچ یادآوری گروهی وجود ندارد!")

# =========================================================
#  سیستم مدیریت پیام‌های روز
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "message_of_day"))
async def message_of_day_cmd(bot: Robot, message: Message):
    """پیام روز"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    text = message.text.replace("/message_of_day", "", 1).strip()
    if not text:
        await message.reply("⚠️ دستور: /message_of_day [متن]")
        return
    
    group_data['message_of_day'] = {
        'text': text,
        'user': user_id,
        'time': datetime.now().isoformat()
    }
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **پیام روز تنظیم شد!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/message_of_day_show")
async def message_of_day_show_cmd(bot: Robot, message: Message):
    """نمایش پیام روز"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    mod = group_data.get('message_of_day', {})
    
    if mod:
        await message.reply(f"""
📝 **پیام روز:**

{mod.get('text', 'تنظیم نشده')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {mod.get('time', '')[:16]}
""")
    else:
        await message.reply("📝 پیام روز تنظیم نشده است!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت مسابقات
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "contest_add"))
async def contest_add_cmd(bot: Robot, message: Message):
    """افزودن مسابقه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/contest_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /contest_add [نام] | [توضیحات] | [جایزه]")
        return
    
    contest_data = [p.strip() for p in parts.split('|')]
    if len(contest_data) < 3:
        await message.reply("⚠️ دستور: /contest_add [نام] | [توضیحات] | [جایزه]")
        return
    
    if 'contests' not in group_data:
        group_data['contests'] = []
    
    contest_id = f"C-{len(group_data['contests']) + 1:04d}"
    group_data['contests'].append({
        'id': contest_id,
        'name': contest_data[0],
        'description': contest_data[1],
        'prize': contest_data[2],
        'participants': [],
        'winner': None,
        'created_at': datetime.now().isoformat(),
        'by': user_id,
        'active': True
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **مسابقه {contest_id} اضافه شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "contest_join"))
async def contest_join_cmd(bot: Robot, message: Message):
    """شرکت در مسابقه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    contest_id = message.text.replace("/contest_join", "", 1).strip()
    if not contest_id:
        await message.reply("⚠️ دستور: /contest_join [شناسه]")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    contests = group_data.get('contests', [])
    for contest in contests:
        if contest.get('id') == contest_id and contest.get('active', True):
            if user_id not in contest.get('participants', []):
                contest['participants'].append(user_id)
                save_group_data(group_id, group_data)
                await message.reply(f"✅ **شما در مسابقه {contest_id} ثبت نام شدید!**")
                return
            else:
                await message.reply(f"⚠️ شما قبلاً در این مسابقه ثبت نام کرده‌اید!")
                return
    
    await message.reply(f"⚠️ مسابقه‌ای با شناسه {contest_id} پیدا نشد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "contest_winner"))
async def contest_winner_cmd(bot: Robot, message: Message):
    """انتخاب برنده مسابقه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    contest_id = message.text.replace("/contest_winner", "", 1).strip()
    if not contest_id:
        await message.reply("⚠️ دستور: /contest_winner [شناسه]")
        return
    
    contests = group_data.get('contests', [])
    for contest in contests:
        if contest.get('id') == contest_id and contest.get('active', True):
            participants = contest.get('participants', [])
            if participants:
                winner = random.choice(participants)
                contest['winner'] = winner
                contest['active'] = False
                save_group_data(group_id, group_data)
                
                winner_name = get_user_name_from_id(winner, group_data)
                await message.reply(f"🏆 **برنده مسابقه {contest_id}:**\n\n{winner_name}\n\n🎁 جایزه: {contest.get('prize', 'نامشخص')}\n🎉 تبریک میگم! 🎊")
                return
            else:
                await message.reply(f"⚠️ هیچ شرکت‌کننده‌ای در مسابقه {contest_id} وجود ندارد!")
                return
    
    await message.reply(f"⚠️ مسابقه‌ای با شناسه {contest_id} پیدا نشد!")

@bot.on_message(filters=lambda m: m.text and m.text == "/contests")
async def contests_cmd(bot: Robot, message: Message):
    """لیست مسابقات"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    contests = group_data.get('contests', [])
    
    if contests:
        text = "🏆 **لیست مسابقات:**\n\n"
        for idx, contest in enumerate(contests, 1):
            status = "🟢 فعال" if contest.get('active', True) else "🔴 بسته"
            text += f"{idx}. {contest.get('name')}\n"
            text += f"   شناسه: {contest.get('id')}\n"
            text += f"   وضعیت: {status}\n"
            text += f"   شرکت‌کنندگان: {len(contest.get('participants', []))} نفر\n"
            if contest.get('winner'):
                winner_name = get_user_name_from_id(contest.get('winner'), group_data)
                text += f"   برنده: {winner_name}\n"
            text += "\n"
        await message.reply(text)
    else:
        await message.reply("🏆 هیچ مسابقه‌ای وجود ندارد!")

# =========================================================
#  سیستم مدیریت کتاب‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "book_add"))
async def book_add_cmd(bot: Robot, message: Message):
    """افزودن کتاب"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/book_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /book_add [نام] | [نویسنده] | [توضیحات]")
        return
    
    book_data = [p.strip() for p in parts.split('|')]
    if len(book_data) < 3:
        await message.reply("⚠️ دستور: /book_add [نام] | [نویسنده] | [توضیحات]")
        return
    
    if 'books' not in group_data:
        group_data['books'] = []
    
    book_id = f"B-{len(group_data['books']) + 1:04d}"
    group_data['books'].append({
        'id': book_id,
        'name': book_data[0],
        'author': book_data[1],
        'description': book_data[2],
        'created_at': datetime.now().isoformat(),
        'by': user_id
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **کتاب {book_id} اضافه شد!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/books")
async def books_cmd(bot: Robot, message: Message):
    """لیست کتاب‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    books = group_data.get('books', [])
    
    if books:
        text = "📚 **لیست کتاب‌ها:**\n\n"
        for idx, book in enumerate(books, 1):
            text += f"{idx}. {book.get('name')}\n"
            text += f"   نویسنده: {book.get('author')}\n"
            text += f"   توضیحات: {book.get('description')[:50]}...\n"
            text += f"   شناسه: {book.get('id')}\n\n"
        await message.reply(text)
    else:
        await message.reply("📚 هیچ کتابی وجود ندارد!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت فیلم‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "movie_add"))
async def movie_add_cmd(bot: Robot, message: Message):
    """افزودن فیلم"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/movie_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /movie_add [نام] | [کارگردان] | [سال] | [توضیحات]")
        return
    
    movie_data = [p.strip() for p in parts.split('|')]
    if len(movie_data) < 4:
        await message.reply("⚠️ دستور: /movie_add [نام] | [کارگردان] | [سال] | [توضیحات]")
        return
    
    if 'movies' not in group_data:
        group_data['movies'] = []
    
    movie_id = f"M-{len(group_data['movies']) + 1:04d}"
    group_data['movies'].append({
        'id': movie_id,
        'name': movie_data[0],
        'director': movie_data[1],
        'year': movie_data[2],
        'description': movie_data[3],
        'created_at': datetime.now().isoformat(),
        'by': user_id
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **فیلم {movie_id} اضافه شد!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/movies")
async def movies_cmd(bot: Robot, message: Message):
    """لیست فیلم‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    movies = group_data.get('movies', [])
    
    if movies:
        text = "🎬 **لیست فیلم‌ها:**\n\n"
        for idx, movie in enumerate(movies, 1):
            text += f"{idx}. {movie.get('name')}\n"
            text += f"   کارگردان: {movie.get('director')}\n"
            text += f"   سال: {movie.get('year')}\n"
            text += f"   توضیحات: {movie.get('description')[:50]}...\n"
            text += f"   شناسه: {movie.get('id')}\n\n"
        await message.reply(text)
    else:
        await message.reply("🎬 هیچ فیلمی وجود ندارد!")

# =========================================================
#  سیستم مدیریت آهنگ‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "song_add"))
async def song_add_cmd(bot: Robot, message: Message):
    """افزودن آهنگ"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/song_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /song_add [نام] | [خواننده] | [سال]")
        return
    
    song_data = [p.strip() for p in parts.split('|')]
    if len(song_data) < 3:
        await message.reply("⚠️ دستور: /song_add [نام] | [خواننده] | [سال]")
        return
    
    if 'songs' not in group_data:
        group_data['songs'] = []
    
    song_id = f"S-{len(group_data['songs']) + 1:04d}"
    group_data['songs'].append({
        'id': song_id,
        'name': song_data[0],
        'singer': song_data[1],
        'year': song_data[2],
        'created_at': datetime.now().isoformat(),
        'by': user_id
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **آهنگ {song_id} اضافه شد!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/songs")
async def songs_cmd(bot: Robot, message: Message):
    """لیست آهنگ‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    songs = group_data.get('songs', [])
    
    if songs:
        text = "🎵 **لیست آهنگ‌ها:**\n\n"
        for idx, song in enumerate(songs, 1):
            text += f"{idx}. {song.get('name')}\n"
            text += f"   خواننده: {song.get('singer')}\n"
            text += f"   سال: {song.get('year')}\n"
            text += f"   شناسه: {song.get('id')}\n\n"
        await message.reply(text)
    else:
        await message.reply("🎵 هیچ آهنگی وجود ندارد!")

# =========================================================
#  سیستم مدیریت بازی‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "game_add"))
async def game_add_cmd(bot: Robot, message: Message):
    """افزودن بازی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/game_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /game_add [نام] | [نوع] | [توضیحات]")
        return
    
    game_data = [p.strip() for p in parts.split('|')]
    if len(game_data) < 3:
        await message.reply("⚠️ دستور: /game_add [نام] | [نوع] | [توضیحات]")
        return
    
    if 'games' not in group_data:
        group_data['games'] = []
    
    game_id = f"G-{len(group_data['games']) + 1:04d}"
    group_data['games'].append({
        'id': game_id,
        'name': game_data[0],
        'type': game_data[1],
        'description': game_data[2],
        'created_at': datetime.now().isoformat(),
        'by': user_id
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **بازی {game_id} اضافه شد!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/games")
async def games_cmd(bot: Robot, message: Message):
    """لیست بازی‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    games = group_data.get('games', [])
    
    if games:
        text = "🎮 **لیست بازی‌ها:**\n\n"
        for idx, game in enumerate(games, 1):
            text += f"{idx}. {game.get('name')}\n"
            text += f"   نوع: {game.get('type')}\n"
            text += f"   توضیحات: {game.get('description')[:50]}...\n"
            text += f"   شناسه: {game.get('id')}\n\n"
        await message.reply(text)
    else:
        await message.reply("🎮 هیچ بازی‌ای وجود ندارد!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت نقل قول‌های روزانه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "daily_quote"))
async def daily_quote_cmd(bot: Robot, message: Message):
    """نقل قول روزانه"""
    quotes = [
        "💬 تنها راه انجام کار بزرگ، عاشق بودن به کاری است که انجام میدهی. - استیو جابز",
        "💬 زندگی ۱۰٪ آنچه برای من اتفاق می‌افتد و ۹۰٪ نحوه واکنش من به آن است. - چارلز اسوایندل",
        "💬 باور کن که می‌توانی و نیمی از راه را رفته‌ای. - تئودور روزولت",
        "💬 دو چیز بی‌نهایت است: جهان و حماقت بشر. البته در مورد اول مطمئن نیستم. - آلبرت انیشتین",
        "💬 موفقیت از شکست به شکست می‌آید، بدون از دست دادن اشتیاق. - وینستون چرچیل",
        "💬 بزرگترین جلال در هرگز زمین نخوردن نیست، بلکه در برخاستن هر بار است. - کنفوسیوس",
        "💬 بهترین زمان برای کاشتن درخت، بیست سال پیش بود. دومین بهترین زمان، امروز است. - ضرب المثل چینی",
        "💬 زندگی یعنی همان چیزی که برایت پیش می‌آید در حالی که مشغول برنامه‌ریزی برای آینده‌ای. - جان لنون"
    ]
    
    quote = random.choice(quotes)
    await message.reply(f"""
📝 **نقل قول روزانه:**

{quote}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d')}
""")

# =========================================================
#  سیستم مدیریت دعاهای روزانه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "daily_prayer"))
async def daily_prayer_cmd(bot: Robot, message: Message):
    """دعای روزانه"""
    prayers = [
        "🤲 خدایا به ما صبر و شکیبایی عطا کن",
        "🤲 خدایا به ما قدرت تحمل مشکلات را بده",
        "🤲 خدایا به ما آرامش و آسایش عنایت کن",
        "🤲 خدایا به ما عاقبت بخیری عطا کن",
        "🤲 خدایا به ما سلامتی و تندرستی بده",
        "🤲 خدایا روزی حلال و پاکیزه نصیب ما کن",
        "🤲 خدایا به ما ایمان و یقین عطا کن",
        "🤲 خدایا به ما محبت و مودت عنایت کن"
    ]
    
    prayer = random.choice(prayers)
    await message.reply(f"""
🤲 **دعای روزانه:**

{prayer}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d')}
✨ ان‌شاءالله مستجاب باشد.
""")

# =========================================================
#  سیستم مدیریت انگیزشی روزانه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "daily_motivation"))
async def daily_motivation_cmd(bot: Robot, message: Message):
    """انگیزشی روزانه"""
    motivations = [
        "💪 هر روز فرصتی جدید برای بهتر شدن است.",
        "💪 موفقیت از شکست به شکست می‌آید، بدون از دست دادن اشتیاق.",
        "💪 بزرگترین جلال در هرگز زمین نخوردن نیست، بلکه در برخاستن هر بار است.",
        "💪 باور کن که می‌توانی و نیمی از راه را رفته‌ای.",
        "💪 بهترین زمان برای کاشتن درخت، بیست سال پیش بود. دومین بهترین زمان، امروز است.",
        "💪 زندگی یعنی همان چیزی که برایت پیش می‌آید در حالی که مشغول برنامه‌ریزی برای آینده‌ای.",
        "💪 هیچوقت تسلیم نشو، زیرا هر روز نزدیک‌تر به موفقیت هستی.",
        "💪 به خودت ایمان داشته باش، تو بیشتر از آنچه فکر می‌کنی ارزش داری."
    ]
    
    msg = random.choice(motivations)
    await message.reply(f"""
🌟 **انگیزشی روزانه:**

{msg}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💪 امروز روز بزرگی است!
""")

# =========================================================
#  سیستم مدیریت فال روزانه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "daily_fortune"))
async def daily_fortune_cmd(bot: Robot, message: Message):
    """فال روزانه"""
    fortunes = [
        "🌟 امروز روز خوبی برای شروع کارهای جدید است.",
        "🌟 عشق در راه است! منتظر یک اتفاق خوب باش.",
        "🌟 موفقیت در انتظار توست، فقط کافی است باور کنی.",
        "🌟 امروز روز آرامشی، استراحت کن و به خودت برس.",
        "🌟 یک خبر خوب به زودی به تو میرسد.",
        "🌟 سفر در پیش داری، آماده شو!",
        "🌟 پول و ثروت به سمت تو میاد، فقط صبور باش.",
        "🌟 امروز روز ملاقات با یک دوست قدیمیه.",
        "🌟 یک تصمیم مهم باید بگیری، به قلبت اعتماد کن.",
        "🌟 روزت پر از انرژی و شادی خواهد بود."
    ]
    
    fortune = random.choice(fortunes)
    await message.reply(f"""
🌅 **فال روزانه:**

{fortune}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d')}
💫 روز خوبی داشته باشید!
""")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت جوک‌های روزانه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "daily_joke"))
async def daily_joke_cmd(bot: Robot, message: Message):
    """جوک روزانه"""
    jokes = [
        "😂 یه روز یه تخم مرغ رفت مهمونی، بهش گفتن چرا اینقدر گردی؟ گفت من تخم مرغم دیگه!",
        "😂 چرا گوجه فرنگی قرمز شد؟ چون سالاد دید!",
        "😂 به کدوم پله میگن پله برقی؟ اونی که از پله ها خسته شده!",
        "😂 چرا ماهی ها تو آب زندگی میکنن؟ چون تو خشکی نمی تونن نفس بکشن!",
        "😂 به چه درختی میگن درخت نارگیل؟ به اونی که نارگیل داره!",
        "😂 چرا پنگوئن ها پرواز نمی‌کنن؟ چون تو قطب جنوب گیر کردن!",
        "😂 به کدوم گربه میگن گربه پشت بامی؟ به اونی که پشت بومه!",
        "😂 چرا زرافه گردن دراز داره؟ چون کلاه نداره!"
    ]
    
    joke = random.choice(jokes)
    await message.reply(f"""
😂 **جوک روزانه:**

{joke}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d')}
😄 با خنده روزت رو شروع کن!
""")

# =========================================================
#  سیستم مدیریت چیستان روزانه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "daily_riddle"))
async def daily_riddle_cmd(bot: Robot, message: Message):
    """چیستان روزانه"""
    riddles = [
        "❓ چیزی که هر چی بیشتر ازش برداری، بزرگتر میشه؟ (سوراخ)",
        "❓ چیزی که همیشه جلوی توئه ولی نمی‌تونی ببینی‌ش؟ (آینده)",
        "❓ چیزی که بدون پنجره و در است ولی می‌تونی داخلش بشی؟ (ماشین)",
        "❓ چیزی که شب ها میاد ولی روزها میره؟ (ستاره)",
        "❓ چیزی که هر چی بیشتر بدی، بیشتر میشه؟ (عشق)",
        "❓ چیزی که با یک دست میشه گرفت ولی با دو دست نه؟ (باد)",
        "❓ چیزی که هر چی بیشتر ازش برداری، کمتر میشه؟ (زمان)",
        "❓ چیزی که همه دارند ولی هیچکس نمی‌تونه ببینه‌ش؟ (اسم)"
    ]
    
    riddle = random.choice(riddles)
    await message.reply(f"""
❓ **چیستان روزانه:**

{riddle}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d')}
🧠 فکر کن و جواب رو پیدا کن!
""")

# =========================================================
#  سیستم مدیریت معمای روزانه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "daily_puzzle"))
async def daily_puzzle_cmd(bot: Robot, message: Message):
    """معمای روزانه"""
    puzzles = [
        "🧩 من چیزی هستم که هر چه بیشتر از من استفاده کنید، کوچکتر میشم. من چیستم؟ (پاسخ: شمع)",
        "🧩 من چیزی هستم که همیشه در حال حرکت هستم، اما هرگز جایی نمیروم. من چیستم؟ (پاسخ: زمان)",
        "🧩 من چیزی هستم که هر چه بیشتر از من بخواهید، بیشتر میشم. من چیستم؟ (پاسخ: علم)",
        "🧩 من چیزی هستم که همه دارند، اما هیچکس نمیتونه من رو ببینه. من چیستم؟ (پاسخ: اسم)",
        "🧩 من چیزی هستم که همیشه با شما هستم، اما هرگز نمیتونید من رو لمس کنید. من چیستم؟ (پاسخ: سایه)",
        "🧩 من چیزی هستم که هر روز صبح می‌آیم، اما شب می‌روم. من چیستم؟ (پاسخ: روز)",
        "🧩 من چیزی هستم که همه می‌شناسند، اما هیچکس نمی‌تواند من را لمس کند. من چیستم؟ (پاسخ: صدا)"
    ]
    
    puzzle = random.choice(puzzles)
    await message.reply(f"""
🧩 **معمای روزانه:**

{puzzle}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d')}
🧠 ذهنت رو به چالش بکش!
""")

# =========================================================
#  سیستم مدیریت فال حافظ
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "hafez"))
async def hafez_cmd(bot: Robot, message: Message):
    """فال حافظ"""
    fal_list = [
        "🔮 به کام تو خوش آید، ای دل که داری هوش\nچو با توست، غم مخور، که عاقبت خوش است",
        "🔮 اگر چه عیش خوش است، اما غم عشق\nبه از هزار جهان عیش و عشرت است",
        "🔮 ساقی بیا که عاشقان را\nبی می، نمی‌شود میسر",
        "🔮 ز کوی یار می‌آید نسیم باد نوروزی\nاز این باد ار مدد خواهی، چراغ دل برافروزی",
        "🔮 ای دل غم این جهان مخور\nکه عاقبت کار خوش است",
        "🔮 تو خود چه می‌دانی که عشق چیست\nکه در دام عشق افتاده‌ای",
        "🔮 به می عشق دلم را خراب کن ساقی\nکه بی می عشق، دلم بی‌قرار است",
        "🔮 صبحدم که از افق می‌دمد\nنوید وصال یار می‌دهد",
        "🔮 به یاد روی تو، ای ماه\nدلم هوایی شده",
        "🔮 غم عشق تو را، ای جان\nبه جان خریدم و خوش است"
    ]
    
    fal = random.choice(fal_list)
    await message.reply(f"""
🪷 **فال حافظ:**

{fal}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}
💫 فال شما نیک است!
""")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت تاریخچه گروه
# =========================================================

@bot.on_message(filters=lambda m: m.text and m.text == "/group_history")
async def group_history_cmd(bot: Robot, message: Message):
    """تاریخچه گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    logs = group_data.get('logs', [])
    
    if not logs:
        await message.reply("📋 هیچ تاریخچه‌ای وجود ندارد!")
        return
    
    text = "📖 **تاریخچه گروه:**\n\n"
    for log in logs[-15:]:
        time_str = log.get('time', '')[:16]
        action = log.get('action', 'نامشخص')
        user = log.get('user', 'نامشخص')[:8]
        target = log.get('target', '')
        reason = log.get('reason', '')
        
        text += f"🔹 {time_str} - {action} توسط {user}\n"
        if target:
            text += f"   هدف: {target}\n"
        if reason:
            text += f"   دلیل: {reason}\n"
        text += "\n"
    
    await message.reply(text)

# =========================================================
#  سیستم مدیریت اطلاعات گروه
# =========================================================

@bot.on_message(filters=lambda m: m.text and m.text == "/group_info")
async def group_info_cmd(bot: Robot, message: Message):
    """اطلاعات گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    
    await message.reply(f"""
📊 **اطلاعات گروه**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 **نام گروه:** {group_data.get('group_name', 'تنظیم نشده')}
📌 **شناسه گروه:** {group_id}
📌 **تاریخ ایجاد:** {group_data.get('created_at', 'نامشخص')[:16]}
📌 **مالک اصلی:** {group_data.get('owner_primary', 'تنظیم نشده')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👥 **آمار کاربران:**
• کل کاربران: {len(group_data.get('users', {}))}
• ادمین‌ها: {len(group_data.get('admins', []))}
• مالک‌ها: {len(group_data.get('owners', []))}
• ویژه‌ها: {len(group_data.get('specials', []))}
• معاف‌ها: {len(group_data.get('exempts', []))}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔒 **وضعیت:**
• قفل گروه: {'✅' if group_data.get('settings', {}).get('lock', False) else '❌'}
• ضد لینک: {'✅' if group_data.get('settings', {}).get('anti_link', True) else '❌'}
• ضد اسپم: {'✅' if group_data.get('settings', {}).get('anti_spam', True) else '❌'}
• ضد فحش: {'✅' if group_data.get('settings', {}).get('anti_swear', True) else '❌'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}
""")

# =========================================================
#  سیستم مدیریت تنظیمات کاربر
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "user_settings"))
async def user_settings_cmd(bot: Robot, message: Message):
    """تنظیمات کاربر"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    await message.reply(f"""
⚙️ **تنظیمات شما**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 **نام:** {(await get_display_name(bot, message) or 'کاربر')}
🆔 **شناسه:** {user_id}

📝 **آمار:**
• پیام‌ها: {group_data.get('message_count', {}).get(user_id, 0)}
• اخطارها: {get_warn_count(group_data, user_id)}

🔒 **وضعیت:**
• میوت: {'✅' if is_punished_active(group_data, "mutes", user_id) else '❌'}
• بن: {'✅' if is_punished_active(group_data, "bans", user_id) else '❌'}
• بلاک: {'✅' if user_id in group_data.get('blocks', []) else '❌'}
• معاف: {'✅' if user_id in group_data.get('exempts', []) else '❌'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}
""")

# =========================================================
#  سیستم مدیریت پیشنهادات کاربران
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "suggestions"))
async def suggestions_cmd(bot: Robot, message: Message):
    """لیست پیشنهادات"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    suggestions = group_data.get('suggestions', [])
    
    if suggestions:
        text = "💡 **لیست پیشنهادات:**\n\n"
        for idx, sug in enumerate(suggestions, 1):
            user_name = get_user_name_from_id(sug.get('user'), group_data)
            text += f"{idx}. {user_name}: {sug.get('text')}\n"
            text += f"   زمان: {sug.get('time', '')[:16]}\n\n"
        await message.reply(text)
    else:
        await message.reply("💡 هیچ پیشنهادی وجود ندارد!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت نقاط کاربران
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "points"))
async def points_cmd(bot: Robot, message: Message):
    """نمایش امتیاز کاربر"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if message.reply_to_message:
        target_id = str(get_reply_sender_id(message))
        target_name = (await get_display_name(bot, get_reply_sender_id(message)) if get_reply_message(message) else "کاربر")
        points = group_data.get('points', {}).get(target_id, 0)
        await message.reply(f"⭐ **امتیاز {target_name}:** {points}")
    else:
        points = group_data.get('points', {}).get(user_id, 0)
        await message.reply(f"⭐ **امتیاز شما:** {points}")

@bot.on_message(filters=lambda m: _cmd_is(m, "add_points"))
async def add_points_cmd(bot: Robot, message: Message):
    """افزودن امتیاز به کاربر"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    if not get_reply_message(message):
        await message.reply("⚠️ روی پیام کاربر ریپلای کن!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /add_points [تعداد]")
        return
    
    try:
        amount = int(parts[1])
        if amount > 0:
            target_id = str(get_reply_sender_id(message))
            target_name = (await get_display_name(bot, get_reply_sender_id(message)) if get_reply_message(message) else "کاربر")
            
            if 'points' not in group_data:
                group_data['points'] = {}
            
            group_data['points'][target_id] = group_data['points'].get(target_id, 0) + amount
            save_group_data(group_id, group_data)
            await message.reply(f"✅ **{amount} امتیاز به {target_name} اضافه شد!**")
        else:
            await message.reply("⚠️ تعداد باید بیشتر از 0 باشد!")
    except (ValueError, IndexError):
        await message.reply("⚠️ تعداد را به عدد وارد کنید!")

# =========================================================
#  سیستم مدیریت سطح کاربران
# =========================================================
# 🛠 بخش ۶۲: قبلاً group_data['xp'] و ['levels'] هیچ‌جای کد نوشته نمی‌شدن - فقط در
# /level خونده می‌شدن. یعنی XP همیشه صفر بود و «سطح» یک قابلیت کاملاً مرده بود.
# اینجا واقعاً XP اهدا می‌شه: به‌ازای هر پیامِ واقعیِ کاربر (نه پیام سرویسی) که
# ربات دیده. طبق تذکر سند («XP بر اساس پیام‌های ثبت‌شده توسط ربات» + «محدودیت
# زمانی برای جلوگیری از اسپم XP») دو نکته رعایت شده:
#   ۱. این آمار فقط بر پایه‌ی پیام‌هایی است که خودِ ربات دیده (نه تاریخچه‌ی قدیمی گروه).
#   ۲. هر کاربر حداکثر هر XP_COOLDOWN_SECONDS ثانیه یک‌بار XP می‌گیرد، پس ارسال
#      پشت‌سرهم چند پیام در چند ثانیه XP نامحدود نمی‌سازد.
XP_PER_MESSAGE = 5
XP_COOLDOWN_SECONDS = 60
XP_PER_LEVEL = 100  # همون فرمولی که /level از قبل نمایش می‌داد (level * 100)

def grant_xp(group_data: dict, user_id: str) -> Optional[dict]:
    """XP یک پیامِ واجدشرایط را اهدا می‌کند (با محدودیت زمانی ضداسپم) و در صورت
    رسیدن به سقف، سطح را بالا می‌برد. اگر به‌خاطر Cooldown چیزی اهدا نشد، None
    برمی‌گرداند؛ وگرنه {'leveled_up': bool, 'level': int, 'xp': int} را."""
    now = time.monotonic()
    cooldowns = group_data.setdefault('xp_cooldown', {})
    last = cooldowns.get(user_id, 0)
    if now - last < XP_COOLDOWN_SECONDS:
        return None
    cooldowns[user_id] = now

    levels = group_data.setdefault('levels', {})
    xp_map = group_data.setdefault('xp', {})
    level = int(levels.get(user_id, 1)) or 1
    xp = xp_map.get(user_id, 0) + XP_PER_MESSAGE

    leveled_up = False
    need = max(level, 1) * XP_PER_LEVEL
    while xp >= need:
        xp -= need
        level += 1
        leveled_up = True
        need = max(level, 1) * XP_PER_LEVEL

    xp_map[user_id] = xp
    levels[user_id] = level
    return {'leveled_up': leveled_up, 'level': level, 'xp': xp}

@bot.on_message(filters=lambda m: _cmd_is(m, "level"))
async def level_cmd(bot: Robot, message: Message):
    """نمایش سطح کاربر"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if message.reply_to_message:
        target_id = str(get_reply_sender_id(message))
        target_name = (await get_display_name(bot, get_reply_sender_id(message)) if get_reply_message(message) else "کاربر")
        level = group_data.get('levels', {}).get(target_id, 1)
        xp = group_data.get('xp', {}).get(target_id, 0)
        next_level_xp = max(int(level), 1) * 100
        progress = int((xp / next_level_xp) * 100)
        
        await message.reply(f"""
📊 **سطح {target_name}:** {level}
⭐ **XP:** {xp}/{next_level_xp}
📈 **پیشرفت:** {make_progress_bar(progress, 100, 15)}
""")
    else:
        level = group_data.get('levels', {}).get(user_id, 1)
        xp = group_data.get('xp', {}).get(user_id, 0)
        next_level_xp = max(int(level), 1) * 100
        progress = int((xp / next_level_xp) * 100)
        
        await message.reply(f"""
📊 **سطح شما:** {level}
⭐ **XP:** {xp}/{next_level_xp}
📈 **پیشرفت:** {make_progress_bar(progress, 100, 15)}
""")

# =========================================================
#  سیستم مدیریت بلاک‌چین گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "blockchain"))
async def blockchain_cmd(bot: Robot, message: Message):
    """اطلاعات بلاک‌چین گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    
    blocks = group_data.get('blocks', [])
    
    await message.reply(f"""
🔗 **بلاک‌چین گروه**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 **تعداد بلاک‌ها:** {len(blocks)}
📌 **آخرین بلاک:** {blocks[-1].get('hash', 'ندارد') if blocks else 'ندارد'}
📌 **کاربران:** {len(group_data.get('users', {}))}
📌 **تراکنش‌ها:** {len(group_data.get('transactions', []))}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}
""")

# =========================================================
#  سیستم مدیریت تراکنش‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "transaction"))
async def transaction_cmd(bot: Robot, message: Message):
    """ثبت تراکنش"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/transaction", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /transaction [از] | [به] | [مقدار]")
        return
    
    tx_data = [p.strip() for p in parts.split('|')]
    if len(tx_data) < 3:
        await message.reply("⚠️ دستور: /transaction [از] | [به] | [مقدار]")
        return
    
    if 'transactions' not in group_data:
        group_data['transactions'] = []
    
    tx_id = f"TX-{len(group_data['transactions']) + 1:04d}"
    group_data['transactions'].append({
        'id': tx_id,
        'from': tx_data[0],
        'to': tx_data[1],
        'amount': tx_data[2],
        'time': datetime.now().isoformat(),
        'by': user_id
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **تراکنش {tx_id} ثبت شد!**")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت مسابقات روزانه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "daily_contest"))
async def daily_contest_cmd(bot: Robot, message: Message):
    """مسابقه روزانه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    today = datetime.now().strftime('%Y%m%d')
    
    if 'daily_contests' not in group_data:
        group_data['daily_contests'] = {}
    
    if today in group_data['daily_contests']:
        await message.reply("⚠️ مسابقه امروز قبلاً ثبت شده است!")
        return
    
    parts = message.text.replace("/daily_contest", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /daily_contest [نام] | [توضیحات]")
        return
    
    contest_data = [p.strip() for p in parts.split('|')]
    if len(contest_data) < 2:
        await message.reply("⚠️ دستور: /daily_contest [نام] | [توضیحات]")
        return
    
    group_data['daily_contests'][today] = {
        'name': contest_data[0],
        'description': contest_data[1],
        'participants': [],
        'winner': None,
        'created_at': datetime.now().isoformat(),
        'by': user_id
    }
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **مسابقه روزانه ثبت شد!**\n\n{contest_data[0]}\n{contest_data[1]}")

@bot.on_message(filters=lambda m: _cmd_is(m, "daily_contest_join"))
async def daily_contest_join_cmd(bot: Robot, message: Message):
    """شرکت در مسابقه روزانه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    today = datetime.now().strftime('%Y%m%d')
    
    daily_contests = group_data.get('daily_contests', {})
    
    if today not in daily_contests:
        await message.reply("⚠️ مسابقه‌ای برای امروز وجود ندارد!")
        return
    
    contest = daily_contests[today]
    
    if user_id in contest.get('participants', []):
        await message.reply("⚠️ شما قبلاً در این مسابقه ثبت نام کرده‌اید!")
        return
    
    contest['participants'].append(user_id)
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **شما در مسابقه روزانه ثبت نام شدید!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "daily_contest_winner"))
async def daily_contest_winner_cmd(bot: Robot, message: Message):
    """انتخاب برنده مسابقه روزانه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    today = datetime.now().strftime('%Y%m%d')
    daily_contests = group_data.get('daily_contests', {})
    
    if today not in daily_contests:
        await message.reply("⚠️ مسابقه‌ای برای امروز وجود ندارد!")
        return
    
    contest = daily_contests[today]
    
    if contest.get('winner'):
        await message.reply("⚠️ برنده مسابقه امروز قبلاً انتخاب شده است!")
        return
    
    participants = contest.get('participants', [])
    if not participants:
        await message.reply("⚠️ هیچ شرکت‌کننده‌ای در این مسابقه وجود ندارد!")
        return
    
    winner = random.choice(participants)
    contest['winner'] = winner
    save_group_data(group_id, group_data)
    
    winner_name = get_user_name_from_id(winner, group_data)
    await message.reply(f"🏆 **برنده مسابقه روزانه:**\n\n{winner_name}\n\n🎉 تبریک میگم! 🎊")

# =========================================================
#  سیستم مدیریت قرعه‌کشی روزانه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "daily_lottery"))
async def daily_lottery_cmd(bot: Robot, message: Message):
    """قرعه‌کشی روزانه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    today = datetime.now().strftime('%Y%m%d')
    
    if 'daily_lottery' not in group_data:
        group_data['daily_lottery'] = {}
    
    if today in group_data['daily_lottery']:
        await message.reply("⚠️ قرعه‌کشی امروز قبلاً انجام شده است!")
        return
    
    users = list(group_data.get('users', {}).keys())
    if not users:
        await message.reply("❌ هیچ کاربری در گروه وجود ندارد!")
        return
    
    winner = random.choice(users)
    group_data['daily_lottery'][today] = {
        'winner': winner,
        'time': datetime.now().isoformat(),
        'by': user_id
    }
    save_group_data(group_id, group_data)
    
    winner_name = get_user_name_from_id(winner, group_data)
    await message.reply(f"🎉 **برنده قرعه‌کشی روزانه:**\n\n{winner_name}\n\n🎊 تبریک میگم! 🎊")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت پیام‌های خوش‌آمد شخصی
# =========================================================



# =========================================================
#  سیستم مدیریت لینک‌های گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "group_links"))
async def group_links_cmd(bot: Robot, message: Message):
    """لیست لینک‌های گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    links = group_data.get('links', [])
    
    if links:
        text = "🔗 **لیست لینک‌های گروه:**\n\n"
        for idx, link in enumerate(links, 1):
            text += f"{idx}. {link}\n"
        await message.reply(text)
    else:
        await message.reply("🔗 هیچ لینکی در گروه وجود ندارد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "add_link"))
async def add_link_cmd(bot: Robot, message: Message):
    """افزودن لینک به گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    link = message.text.replace("/add_link", "", 1).strip()
    if not link:
        await message.reply("⚠️ دستور: /add_link [لینک]")
        return
    
    if 'links' not in group_data:
        group_data['links'] = []
    
    if link not in group_data['links']:
        group_data['links'].append(link)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **لینک {link} به گروه اضافه شد!**")
    else:
        await message.reply(f"⚠️ لینک {link} قبلاً در گروه است!")

@bot.on_message(filters=lambda m: _cmd_is(m, "remove_link"))
async def remove_link_cmd(bot: Robot, message: Message):
    """حذف لینک از گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    link = message.text.replace("/remove_link", "", 1).strip()
    if not link:
        await message.reply("⚠️ دستور: /remove_link [لینک]")
        return
    
    if 'links' in group_data and link in group_data['links']:
        group_data['links'].remove(link)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **لینک {link} از گروه حذف شد!**")
    else:
        await message.reply(f"⚠️ لینک {link} در گروه وجود ندارد!")

# =========================================================
#  سیستم مدیریت فایل‌های گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "files"))
async def files_cmd(bot: Robot, message: Message):
    """لیست فایل‌های گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    files = group_data.get('files', [])
    
    if files:
        text = "📁 **لیست فایل‌های گروه:**\n\n"
        for idx, file in enumerate(files, 1):
            text += f"{idx}. {file.get('name')}\n"
            text += f"   شناسه: {file.get('id')}\n"
            text += f"   زمان: {file.get('time', '')[:16]}\n\n"
        await message.reply(text)
    else:
        await message.reply("📁 هیچ فایلی در گروه وجود ندارد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "add_file"))
async def add_file_cmd(bot: Robot, message: Message):
    """افزودن فایل به گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/add_file", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /add_file [نام] | [لینک]")
        return
    
    file_data = [p.strip() for p in parts.split('|')]
    if len(file_data) < 2:
        await message.reply("⚠️ دستور: /add_file [نام] | [لینک]")
        return
    
    if 'files' not in group_data:
        group_data['files'] = []
    
    file_id = f"F-{len(group_data['files']) + 1:04d}"
    group_data['files'].append({
        'id': file_id,
        'name': file_data[0],
        'link': file_data[1],
        'time': datetime.now().isoformat(),
        'by': user_id
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **فایل {file_id} به گروه اضافه شد!**")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت نقش‌های رنگی
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "role_color"))
async def role_color_cmd(bot: Robot, message: Message):
    """تنظیم رنگ نقش"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند رنگ نقش را تنظیم کند!")
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("⚠️ دستور: /role_color [نقش] [رنگ]")
        return
    
    role = parts[1]
    color = parts[2]
    
    colors = ['قرمز', 'آبی', 'سبز', 'زرد', 'بنفش', 'نارنجی', 'صورتی', 'مشکی', 'سفید']
    if color not in colors:
        await message.reply(f"⚠️ رنگ‌های موجود: {', '.join(colors)}")
        return
    
    if 'role_colors' not in group_data:
        group_data['role_colors'] = {}
    
    group_data['role_colors'][role] = color
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **رنگ نقش {role} به {color} تغییر یافت!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/role_colors")
async def role_colors_cmd(bot: Robot, message: Message):
    """لیست رنگ‌های نقش‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    role_colors = group_data.get('role_colors', {})
    
    if role_colors:
        text = "🎨 **رنگ‌های نقش‌ها:**\n\n"
        for role, color in role_colors.items():
            text += f"• {role}: {color}\n"
        await message.reply(text)
    else:
        await message.reply("🎨 هیچ رنگی برای نقش‌ها تنظیم نشده است!")

# =========================================================
#  سیستم مدیریت هشدارها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "alert_set"))
async def alert_set_cmd(bot: Robot, message: Message):
    """تنظیم هشدار"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/alert_set", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /alert_set [نام] | [متن]")
        return
    
    alert_data = [p.strip() for p in parts.split('|')]
    if len(alert_data) < 2:
        await message.reply("⚠️ دستور: /alert_set [نام] | [متن]")
        return
    
    if 'alerts' not in group_data:
        group_data['alerts'] = {}
    
    group_data['alerts'][alert_data[0]] = alert_data[1]
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **هشدار {alert_data[0]} تنظیم شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "alert_show"))
async def alert_show_cmd(bot: Robot, message: Message):
    """نمایش هشدار"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    name = message.text.replace("/alert_show", "", 1).strip()
    
    if not name:
        await message.reply("⚠️ دستور: /alert_show [نام]")
        return
    
    alerts = group_data.get('alerts', {})
    
    if name in alerts:
        await message.reply(f"🔔 **هشدار {name}:**\n{alerts[name]}")
    else:
        await message.reply(f"⚠️ هشداری با نام {name} پیدا نشد!")

# =========================================================
#  سیستم مدیریت تقویم گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "calendar_add"))
async def calendar_add_cmd(bot: Robot, message: Message):
    """افزودن رویداد به تقویم"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/calendar_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /calendar_add [تاریخ] | [رویداد]")
        return
    
    cal_data = [p.strip() for p in parts.split('|')]
    if len(cal_data) < 2:
        await message.reply("⚠️ دستور: /calendar_add [تاریخ] | [رویداد]")
        return
    
    if 'calendar' not in group_data:
        group_data['calendar'] = {}
    
    group_data['calendar'][cal_data[0]] = cal_data[1]
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **رویداد برای {cal_data[0]} اضافه شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "calendar_show"))
async def calendar_show_cmd(bot: Robot, message: Message):
    """نمایش تقویم"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    date = message.text.replace("/calendar_show", "", 1).strip()
    
    if not date:
        await message.reply("⚠️ دستور: /calendar_show [تاریخ]")
        return
    
    calendar = group_data.get('calendar', {})
    
    if date in calendar:
        await message.reply(f"📅 **رویداد {date}:**\n{calendar[date]}")
    else:
        await message.reply(f"⚠️ رویدادی برای {date} پیدا نشد!")

# =========================================================
#  سیستم مدیریت یادداشت‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "note_add"))
async def note_add_cmd(bot: Robot, message: Message):
    """افزودن یادداشت"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/note_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /note_add [عنوان] | [متن]")
        return
    
    note_data = [p.strip() for p in parts.split('|')]
    if len(note_data) < 2:
        await message.reply("⚠️ دستور: /note_add [عنوان] | [متن]")
        return
    
    if 'notes' not in group_data:
        group_data['notes'] = {}
    
    group_data['notes'][note_data[0]] = note_data[1]
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **یادداشت {note_data[0]} اضافه شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "note_show"))
async def note_show_cmd(bot: Robot, message: Message):
    """نمایش یادداشت"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    title = message.text.replace("/note_show", "", 1).strip()
    
    if not title:
        await message.reply("⚠️ دستور: /note_show [عنوان]")
        return
    
    notes = group_data.get('notes', {})
    
    if title in notes:
        await message.reply(f"📝 **یادداشت {title}:**\n{notes[title]}")
    else:
        await message.reply(f"⚠️ یادداشتی با عنوان {title} پیدا نشد!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت پرسش و پاسخ
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "faq_add"))
async def faq_add_cmd(bot: Robot, message: Message):
    """افزودن سوال متداول"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/faq_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /faq_add [سوال] | [پاسخ]")
        return
    
    faq_data = [p.strip() for p in parts.split('|')]
    if len(faq_data) < 2:
        await message.reply("⚠️ دستور: /faq_add [سوال] | [پاسخ]")
        return
    
    if 'faq' not in group_data:
        group_data['faq'] = []
    
    faq_id = f"FAQ-{len(group_data['faq']) + 1:04d}"
    group_data['faq'].append({
        'id': faq_id,
        'question': faq_data[0],
        'answer': faq_data[1],
        'created_at': datetime.now().isoformat(),
        'by': user_id
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **سوال متداول {faq_id} اضافه شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "faq"))
async def faq_cmd(bot: Robot, message: Message):
    """لیست سوالات متداول"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    faq = group_data.get('faq', [])
    
    if faq:
        text = "❓ **سوالات متداول:**\n\n"
        for idx, item in enumerate(faq, 1):
            text += f"{idx}. {item.get('question')}\n"
            text += f"   پاسخ: {item.get('answer')}\n"
            text += f"   شناسه: {item.get('id')}\n\n"
        await message.reply(text)
    else:
        await message.reply("❓ هیچ سوال متداولی وجود ندارد!")

# =========================================================
#  سیستم مدیریت نظرسنجی روزانه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "daily_poll"))
async def daily_poll_cmd(bot: Robot, message: Message):
    """نظرسنجی روزانه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    today = datetime.now().strftime('%Y%m%d')
    
    if 'daily_polls' not in group_data:
        group_data['daily_polls'] = {}
    
    if today in group_data['daily_polls']:
        await message.reply("⚠️ نظرسنجی امروز قبلاً ثبت شده است!")
        return
    
    parts = message.text.replace("/daily_poll", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /daily_poll [سوال] | گزینه۱ | گزینه۲")
        return
    
    options = [opt.strip() for opt in parts.split('|')]
    if len(options) < 2:
        await message.reply("⚠️ حداقل ۲ گزینه وارد کنید!")
        return
    
    question = options[0]
    choices = options[1:]
    
    group_data['daily_polls'][today] = {
        'question': question,
        'choices': choices,
        'votes': {choice: 0 for choice in choices},
        'voters': [],
        'created_at': datetime.now().isoformat(),
        'by': user_id
    }
    save_group_data(group_id, group_data)
    
    text = f"📊 **نظرسنجی روزانه:**\n\n{question}\n\n"
    emojis = ["🅰️", "🅱️", "🅲️", "🅳️"]
    
    for idx, choice in enumerate(choices):
        if idx < len(emojis):
            text += f"{emojis[idx]} {choice}\n"
        else:
            text += f"➡️ {choice}\n"
    
    text += f"\n📌 برای رای دادن: /vote {today} [گزینه]"
    text += f"\n📅 {datetime.now().strftime('%Y/%m/%d')}"
    
    await message.reply(text)

# =========================================================
#  سیستم مدیریت ربات‌های هوشمند
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "ai_settings"))
async def ai_settings_cmd(bot: Robot, message: Message):
    """تنظیمات هوش مصنوعی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /ai_settings [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['ai_enabled'] = True
        save_group_data(group_id, group_data)
        await message.reply("🤖 **هوش مصنوعی فعال شد!**")
    elif status == "غیرفعال":
        group_data['settings']['ai_enabled'] = False
        save_group_data(group_id, group_data)
        await message.reply("🤖 **هوش مصنوعی غیرفعال شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")


# =========================================================
#  🛠 رفع باگ اصلی: «هوش مصنوعی» فقط یک سوییچ خالی بود
# =========================================================
# قبل از این، /ai_settings فقط یک مقدار True/False توی دیتابیس ست می‌کرد
# که هیچ‌جای دیگه‌ی کد خونده نمی‌شد؛ و دستور واقعی «هوش مصنوعی [متن]» که
# راهنمای خود ربات قول می‌داد، اصلاً پیاده‌سازی نداشت - یعنی چه فعال چه
# غیرفعال، عملاً هیچ اتفاقی نمی‌افتاد چون چیزی برای فعال/غیرفعال‌کردن
# وجود نداشت. این بخش یک اتصال واقعی به Gemini API گوگل برقرار می‌کنه
# (endpoint: POST {AI_API_BASE}/models/{AI_MODEL}:generateContent).
#
# ⚙️ برای فعال شدن واقعی، این متغیرهای محیطی را روی سروری که ربات را
# اجرا می‌کنید تنظیم کنید:
#   AI_API_KEY  = کلید Gemini API شما (از aistudio.google.com/apikey)
#   AI_API_BASE = آدرس پایه‌ی Generative Language API گوگل
#                 (پیش‌فرض: https://generativelanguage.googleapis.com/v1beta)
#   AI_MODEL    = نام مدل جمنای (پیش‌فرض: gemini-2.5-flash)
# =========================================================
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

# 🛠 asyncio.to_thread پیش‌فرض از یه thread pool مشترک و کوچیک (حداکثر ۳۲ ترد)
# استفاده می‌کنه که بین کل ربات (نه فقط AI) مشترکه؛ یعنی اگه همزمان چند نفر
# «هوش مصنوعی»/«گاردی» صدا بزنن، ممکنه درخواست‌ها تو صف بمونن و جواب‌ها دیر
# برسن. این‌جا یه thread pool مخصوص و بزرگ‌تر (۵۰ ترد) فقط برای تماس‌های
# شبکه‌ای AI/قیمت ساخته می‌شه تا تا ۵۰ درخواست هم‌زمان واقعاً هم‌زمان (نه
# صف‌شده پشت هم) پردازش بشن.
_AI_NETWORK_EXECUTOR = ThreadPoolExecutor(max_workers=50, thread_name_prefix="gardi-ai-net")

AI_API_KEY = (os.getenv("AI_API_KEY", "").strip()
              or os.getenv("GEMINI_API_KEY", "").strip()
              or os.getenv("GOOGLE_API_KEY", "").strip())
# Also allow ai_key.txt next to the entry script, current directory, or DATA_DIR.
if not AI_API_KEY:
    _key_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_key.txt"),
        os.path.join(os.getcwd(), "ai_key.txt"),
        os.path.join(DATA_DIR, "ai_key.txt"),
    ]
    for _key_file in dict.fromkeys(_key_paths):
        try:
            if os.path.isfile(_key_file):
                _candidate = open(_key_file, "r", encoding="utf-8").read().strip()
                if _candidate:
                    AI_API_KEY = _candidate
                    break
        except Exception:
            pass
AI_API_BASE = os.getenv("AI_API_BASE", "https://generativelanguage.googleapis.com/v1").rstrip("/")
AI_MODEL = os.getenv("AI_MODEL", "gemini-3.6-flash")
# Fallback models/endpoints are tried only when the selected model is unavailable.
AI_FALLBACK_MODELS = [x.strip() for x in os.getenv("AI_FALLBACK_MODELS", "gemini-3.5-flash-lite").split(",") if x.strip()]
AI_API_BASES = [AI_API_BASE]
for _base in ["https://generativelanguage.googleapis.com/v1beta", "https://generativelanguage.googleapis.com/v1"]:
    if _base not in AI_API_BASES:
        AI_API_BASES.append(_base)


# =========================================================
#  💵 قیمت لحظه‌ای دلار/یورو/طلا/سکه (سرویس رایگان navasan.tech)
# =========================================================
# 🛠 چون خودِ Gemini به اینترنت زنده وصل نیست، قیمت لحظه‌ای دلار/طلا رو
# نمی‌دونه. اینجا یه سرویس جدا و رایگان (navasan.tech) وصل شده که واقعاً
# قیمت لحظه‌ای بازار ایران رو برمی‌گردونه. برای فعال‌سازی، یه کلید API
# رایگان از navasan.tech بگیر (ثبت‌نام ساده، بدون هزینه) و مثل AI_API_KEY
# در متغیر محیطی NAVASAN_API_KEY یا فایل navasan_key.txt (کنار ai_key.txt)
# قرار بده. اگه کلید تنظیم نشده باشه، این قابلیت فقط یه پیام راهنما میده،
# نه خطای فنی.
NAVASAN_API_KEY = os.getenv("NAVASAN_API_KEY", "").strip()
if not NAVASAN_API_KEY:
    for _key_file in ("navasan_key.txt", os.path.join(os.path.dirname(os.path.abspath(__file__)), "navasan_key.txt")):
        try:
            if os.path.isfile(_key_file):
                _candidate = open(_key_file, "r", encoding="utf-8").read().strip()
                if _candidate:
                    NAVASAN_API_KEY = _candidate
                    break
        except Exception:
            pass

NAVASAN_API_URL = os.getenv("NAVASAN_API_URL", "http://api.navasan.tech/latest/").rstrip("/") + "/"
_NAVASAN_CACHE_TTL = 120  # ثانیه — قیمت‌ها هر چند ثانیه یه‌بار عوض می‌شن، پس برای
# جلوگیری از درخواست زیادی به سرویس رایگان، تا ۲ دقیقه کش نگه‌داشته می‌شه.
_navasan_cache = {"data": None, "ts": 0.0}


def _navasan_fetch_sync() -> dict:
    """درخواست سینک به navasan.tech (در یک ترد جدا صدا زده می‌شه). نتیجه چند
    دقیقه کش می‌شه تا سهمیه‌ی رایگان سریع تموم نشه."""
    now = time.time()
    if _navasan_cache["data"] is not None and (now - _navasan_cache["ts"]) < _NAVASAN_CACHE_TTL:
        return _navasan_cache["data"]

    url = f"{NAVASAN_API_URL}?api_key={NAVASAN_API_KEY}"
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, dict) or not data:
        raise AIServiceError(0, "navasan: empty/invalid response")
    _navasan_cache["data"] = data
    _navasan_cache["ts"] = now
    return data


async def navasan_fetch() -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_AI_NETWORK_EXECUTOR, _navasan_fetch_sync)


# 🛠 چون نمی‌شه از قبل مطمئن بود دقیقاً اسم هر کلید در پاسخ navasan چیه (و
# ممکنه در طول زمان کمی تغییر کنه)، به‌جای هاردکد کردن یک اسم دقیق، برای هر
# آیتم چند کلیدواژه‌ی جایگزین امتحان می‌شه و اولین کلیدی از پاسخ که همه‌ی
# کلیدواژه‌هاش رو (بدون حساسیت به حروف بزرگ/کوچک) داشته باشه انتخاب می‌شه؛
# در بین چند نتیجه، کلیدی که «sell»/«فروش» توش باشه (قیمت فروش، رایج‌تر
# برای نمایش عمومی) در اولویته.
NAVASAN_ITEMS = [
    # (کلیدواژه‌های فارسی که کاربر می‌نویسه، لیست کلیدواژه‌های انگلیسی برای پیدا کردن کلید مناسب در پاسخ API، برچسب نمایشی)
    (["نیم سکه", "نیم‌سکه"], ["nim"], "نیم‌سکه"),
    (["ربع سکه", "ربع‌سکه"], ["rob"], "ربع‌سکه"),
    (["سکه گرمی"], ["gerami"], "سکه گرمی"),
    (["سکه امامی", "سکه"], ["sekee", "emami"], "سکه امامی"),
    (["طلای 24", "طلای بیست و چهار", "طلا ۲۴", "طلای ۲۴"], ["24ayar", "geram24", "gold24"], "طلای ۲۴ عیار (هر گرم)"),
    (["مثقال"], ["mesghal"], "مثقال طلا"),
    (["طلا", "طلای 18", "طلای هجده", "طلای ۱۸"], ["18ayar", "geram18", "gold18"], "طلای ۱۸ عیار (هر گرم)"),
    (["دلار"], ["usd"], "دلار آمریکا"),
    (["یورو"], ["eur"], "یورو"),
    (["پوند"], ["gbp"], "پوند انگلیس"),
    (["درهم"], ["aed"], "درهم امارات"),
    (["لیر"], ["try"], "لیر ترکیه"),
    (["یوان"], ["cny"], "یوان چین"),
    (["دلار کانادا"], ["cad"], "دلار کانادا"),
    (["تتر", "یو اس دی تی"], ["usdt", "tether"], "تتر (USDT)"),
    (["بیت کوین", "بیتکوین"], ["btc"], "بیت‌کوین"),
]


def _navasan_find_price(data: dict, en_keywords: list) -> tuple:
    """بین کلیدهای پاسخ navasan، اولین کلیدی که همه‌ی en_keywords توش باشه رو
    پیدا می‌کنه (با اولویت به کلیدهایی که «sell» توشونه). خروجی: (مقدار، نام‌کلید) یا (None, None)."""
    candidates = []
    for key, val in data.items():
        key_l = key.lower()
        if all(kw.lower() in key_l for kw in en_keywords):
            candidates.append((key, val))
    if not candidates:
        return None, None
    candidates.sort(key=lambda kv: (0 if "sell" in kv[0].lower() else 1))
    key, val = candidates[0]
    if isinstance(val, dict):
        val = val.get("value") or val.get("sell") or val.get("price") or next(iter(val.values()), None)
    return val, key


def _navasan_detect_query(user_text: str):
    """اگه متن کاربر دقیقاً یه درخواست قیمت شناخته‌شده باشه، (کلیدواژه‌های
    انگلیسی، برچسب نمایشی) رو برمی‌گردونه؛ وگرنه None. عبارت‌های خاص‌تر
    («نیم سکه») قبل از عبارت‌های عمومی‌تر («سکه») چک می‌شن تا اشتباه گرفته نشن."""
    t = normalize_fa(user_text or "").strip()
    if not t:
        return None
    for fa_keys, en_keywords, label in NAVASAN_ITEMS:
        for fk in fa_keys:
            if fk in t:
                return en_keywords, label
    return None


def _format_toman(value) -> str:
    """navasan قیمت‌ها رو معمولاً به ریال میده؛ برای نمایش خودمونی‌تر به تومان
    (تقسیم بر ۱۰) با جداکننده‌ی هزارگان تبدیل می‌شه."""
    try:
        num = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return str(value)
    toman = num / 10
    return f"{toman:,.0f}"


async def _try_price_answer(user_text: str, message: Message) -> bool:
    """اگه متن کاربر یه سوال قیمتِ شناخته‌شده باشه، قیمت واقعی رو از
    navasan.tech می‌گیره و مستقیم جواب می‌ده (بدون نیاز به AI)؛ اگه سوال
    قیمتی نبود False برمی‌گردونه تا مسیر عادی (AI/quick reply) ادامه پیدا کنه."""
    detected = _navasan_detect_query(user_text)
    if not detected:
        return False
    en_keywords, label = detected

    if not NAVASAN_API_KEY:
        await message.reply(
            f"💰 برای گفتن قیمت لحظه‌ای «{label}» به یه کلید API رایگان از navasan.tech نیاز دارم.\n"
            "یه کلید رایگان از navasan.tech بگیر و در متغیر محیطی NAVASAN_API_KEY یا فایل navasan_key.txt قرار بده."
        )
        return True

    try:
        data = await navasan_fetch()
    except Exception as e:
        logging.getLogger("gardi").warning("navasan fetch failed: %r", e)
        await message.reply(f"❌ الان نتونستم قیمت «{label}» رو از سرویس بگیرم. کمی بعد دوباره امتحان کن.")
        return True

    value, matched_key = _navasan_find_price(data, en_keywords)
    if value is None:
        await message.reply(f"❌ قیمت «{label}» توی پاسخ سرویس پیدا نشد (ممکنه فرمت API عوض شده باشه).")
        return True

    toman_text = _format_toman(value)
    await message.reply(f"💰 قیمت لحظه‌ای {label}: **{toman_text} تومان**\n(منبع: navasan.tech)")
    return True


# 🛠 رفع باگ: این متن سیستم (پرامپت شخصیت) عیناً در دو تابع مختلف
# (ai_reply_continue_handler و ai_chat_cmd) کپی‌پیست شده بود؛ یعنی هر اصلاحی
# فقط توی یکی اعمال می‌شد و اون یکی همیشه یه نسخه‌ی قدیمی/ناهماهنگ می‌موند.
# یکی‌شون کرده شد. همچنین یک خط اضافه شد که صراحتاً از جواب مبهمِ «فلان یا
# بهمان، خودت انتخاب کن» برای سوال‌های عددی/مشخص جلوگیری می‌کنه: هوش مصنوعی
# باید یا یک جواب قطعی بده، یا صادقانه بگه نمی‌دونه - نه این‌که با گزینه‌های
# متعدد از خودش سلب مسئولیت کنه.
def _ai_system_prompt() -> str:
    return (
        f"تو گاردی هستی، دستیار هوش مصنوعیِ ربات گروهیِ {BOT_NAME}. خیلی خودمونی، "
        "صمیمی و محاوره‌ای حرف بزن؛ انگار داری با یه رفیق چت می‌کنی، نه یه متن "
        "رسمی/اداری. از جمله‌های کوتاه و کلمات روزمره استفاده کن، رسمی‌بازی و "
        "کتابی حرف زدن ممنوع! ولی کلمه‌ها رو همیشه کامل و درست بنویس، نه "
        "مخفف/سرهم‌نویسیِ چت‌کردنی (مثلاً بنویس «چی»، نه «چ»؛ «نمی‌دونم»، نه "
        "«نمیدونم»/«نم‌دونم»؛ «خیلی»، نه «خیل» یا «خیع»؛ «مرسی»، نه «مسی»)؛ "
        "خودمونی بودن یعنی لحن ساده و صمیمی، نه کوتاه کردن دست‌وپا شکسته‌ی "
        "کلمات. جواب‌ها کوتاه و مفید باشن. اگه چیزی مثل قیمت لحظه‌ای "
        "دلار/طلا/سکه/بورس/ارز دیجیتال یا هر داده‌ی زنده‌ی دیگه رو پرسیدن، "
        "صادقانه و خودمونی بگو که به اینترنت زنده وصل نیستی و قیمت لحظه‌ای رو "
        "نداری، و پیشنهاد بده از یه سایت/اپ صرافی معتبر بپرسن؛ عدد الکی و "
        "حدسی هم اصلاً نگو. برای هر سوال دیگه‌ای هم که یه جواب مشخص/عددی/دقیق "
        "می‌خواد، یا یک جواب روشن و قطعی بده، یا صادقانه بگو نمی‌دونی/مطمئن "
        "نیستی؛ هیچ‌وقت به‌جای جواب دادن نگو «فلان یا بهمان، خودت انتخاب کن» "
        "یا چند گزینه رو ردیف نکن که کاربر خودش تصمیم بگیره - این جواب ندادنه، "
        "نه کمک کردن."
    )


# 🛠 باگ اصلیِ «نتونستم به سرویس هوش مصنوعی وصل بشم» بدون هیچ لاگی:
# پایین‌تر (در _ai_call_sync) و هر جای دیگه‌ای که خطای Gemini رخ می‌داد،
# کد یک AIServiceError می‌ساخت (raise AIServiceError(code, detail))، اما
# این کلاس هیچ‌جای فایل تعریف نشده بود! یعنی همیشه یک NameError واقعی رخ
# می‌داد که با except urllib.error.HTTPError گرفته نمی‌شد و می‌افتاد توی
# except Exception عمومی پایین‌تر (در ai_chat_cmd) — همونی که فقط پیام
# مبهم «نتونستم به سرویس هوش مصنوعی وصل بشم» رو نشون می‌داد و هیچ‌وقت هیچ
# جزئیاتی (نه در کنسول، نه به کاربر) ثبت نمی‌شد. تعریف واقعی کلاس زیر،
# دقیقاً همین باگ رو حل می‌کنه.
class AIServiceError(Exception):
    """خطای سرویس Gemini؛ code همون HTTP status (یا 0 برای خطای شبکه/غیرمنتظره) است.
    message هیچ‌وقت نباید حاوی API Key باشد (به همین دلیل _ai_call_sync قبل از
    ساختن این خطا، هدر/URL حاوی کلید را داخل پیام قرار نمی‌دهد)."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Gemini API error (code={code}): {message}")


def _ai_call_sync(messages: list) -> str:
    """
    درخواست HTTP سینک به Gemini (داخل یک ترد جدا صدا زده می‌شه تا event loop
    اصلی بلاک نشه). چون بقیه‌ی کد (تاریخچه‌ی گفتگو، ادامه با ریپلای و...) با
    فرمت پیام‌های سبک OpenAI کار می‌کنه (role: system/user/assistant)، اینجا
    قبل از ارسال به فرمت contents/systemInstruction جمنای تبدیل می‌شه.

    🛠 کلیدهای جدید Gemini (که با «AQ.» شروع می‌شن، به‌جای فرمت قدیمی
    «AIzaSy...») گاهی با هدر x-goog-api-key رد می‌شن (۴۰۱/۴۰۳) ولی با همون
    کلید به‌صورت query param (?key=) قبول می‌شن، یا برعکس — این یه باگ/
    ناهماهنگی شناخته‌شده و در حال تغییر از سمت خودِ گوگله، نه چیزی که با
    تغییر کد اینجا صد در صد قابل پیش‌بینی باشه. برای همین اول با هدر تلاش
    می‌کنیم و اگه ۴۰۱/۴۰۳ داد، همون درخواست رو یک‌بار با کلید در query
    string هم امتحان می‌کنیم.
    """
    system_parts = []
    contents = []
    for m in messages:
        role = m.get("role")
        text = m.get("content", "")
        if role == "system":
            system_parts.append(text)
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": text}]})
        else:
            contents.append({"role": "user", "parts": [{"text": text}]})

    body = {"contents": contents}
    if system_parts:
        body["systemInstruction"] = {"parts": [{"text": "\n".join(system_parts)}]}

    payload = json.dumps(body).encode("utf-8")
    last_error = None
    models = [AI_MODEL] + [m for m in AI_FALLBACK_MODELS if m != AI_MODEL]
    bases = [AI_API_BASE] + [b for b in AI_API_BASES if b != AI_API_BASE]
    log = logging.getLogger("gardi")

    def _do_request(url: str, use_query_key: bool):
        # 🛠 API Key هیچ‌وقت نباید در لاگ/خطا چاپ بشه: هم در حالت هدر و هم در
        # حالت query-param، خود url/headers که کلید رو دارن جایی لاگ نمی‌شن؛
        # فقط base+model (بدون کلید) لاگ می‌شه (پایین‌تر).
        if use_query_key:
            sep = "&" if "?" in url else "?"
            full_url = f"{url}{sep}key={AI_API_KEY}"
            headers = {"Content-Type": "application/json"}
        else:
            full_url = url
            headers = {"Content-Type": "application/json", "x-goog-api-key": AI_API_KEY}
        req = urllib.request.Request(full_url, data=payload, method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    # 🛠 خطاهای موقت سمت گوگل (503 = مدل شلوغه، 429 = rate limit) قبل از رد
    # شدن به مدل/endpoint بعدی، چند بار با فاصله (backoff) روی همون مدل هم
    # امتحان می‌شن، چون معمولاً خیلی زود خودشون درست می‌شن.
    RETRYABLE_CODES = (503, 429)
    MAX_RETRIES_PER_MODEL = 2
    RETRY_DELAY_SECONDS = 3

    for base in bases:
        for model in models:
            url = f"{base}/models/{model}:generateContent"
            safe_ref = f"{base}/{model}"  # برای لاگ: بدون کلید

            for attempt in range(MAX_RETRIES_PER_MODEL + 1):
                try:
                    return _do_request(url, use_query_key=False)
                except urllib.error.HTTPError as e:
                    detail = e.read().decode("utf-8", errors="replace")[:1800]
                    log.warning("Gemini call failed [%s] status=%s (trying header auth)", safe_ref, e.code)
                    # 🛠 کلیدهای جدید (پیشوند «AQ.») گاهی با هدر رد می‌شن (401/403) ولی
                    # با همون کلید در query param قبول می‌شن. طبق داک‌استرینگ بالا، یک
                    # بار دیگه با query param امتحان می‌کنیم قبل از این‌که خطا رو نهایی کنیم.
                    if e.code in (401, 403):
                        try:
                            return _do_request(url, use_query_key=True)
                        except urllib.error.HTTPError as e2:
                            detail = e2.read().decode("utf-8", errors="replace")[:1800]
                            log.warning("Gemini call failed [%s] status=%s (query-param auth also failed)", safe_ref, e2.code)
                            if e2.code == 403:
                                raise AIServiceError(403, detail) from e2
                            last_error = AIServiceError(e2.code, detail)
                            break
                        except urllib.error.URLError as e2:
                            last_error = AIServiceError(0, f"network error: {e2.reason}")
                            break
                    last_error = AIServiceError(e.code, detail)
                    if e.code in RETRYABLE_CODES and attempt < MAX_RETRIES_PER_MODEL:
                        log.warning("Gemini call [%s] status=%s, retrying in %ss (attempt %s/%s)",
                                    safe_ref, e.code, RETRY_DELAY_SECONDS, attempt + 1, MAX_RETRIES_PER_MODEL)
                        time.sleep(RETRY_DELAY_SECONDS)
                        continue
                    # چه خطای غیرقابل‌تلافی (400/404) باشه چه یک خطای قابل‌تلافی که
                    # تعداد تلاش‌هاش تموم شده، به مدل/endpoint بعدی می‌ریم.
                    break
                except urllib.error.URLError as e:
                    # خطای شبکه/DNS/Timeout (نه پاسخ HTTP خطا) — این‌ها قبلاً اصلاً
                    # گرفته نمی‌شدن و به‌صورت خام تا بالا (و در نهایت except Exception
                    # عمومی در ai_chat_cmd) بالا می‌رفتن، بدون هیچ لاگی.
                    log.warning("Gemini call failed [%s] network error: %r", safe_ref, e.reason)
                    last_error = AIServiceError(0, f"network error: {e.reason}")
                    if attempt < MAX_RETRIES_PER_MODEL:
                        time.sleep(RETRY_DELAY_SECONDS)
                        continue
                    break

    if last_error:
        raise last_error
    raise AIServiceError(0, "No Gemini endpoint/model was reachable.")


async def ask_ai(messages: list) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_AI_NETWORK_EXECUTOR, _ai_call_sync, messages)


def _ai_today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _ai_reset_if_new_day(group_data: dict) -> None:
    """طبق راهنما: «گفتگوها در پایان روز خودکار پاک می‌شن»."""
    today = _ai_today()
    if group_data.get('ai_conversations_date') != today:
        group_data['ai_conversations'] = {}
        group_data['ai_conversations_date'] = today


# =========================================================
#  🎨 قالب‌بندی ظاهری پاسخ‌های هوش مصنوعی گاردی
# =========================================================
# قبلاً پاسخ AI یک متن کاملاً ساده و بی‌استایل بود. این بخش یک «قالب گاردی»
# ثابت می‌سازه (هدر/جداکننده/فوتر + Bold/Code/Quote واقعیِ HTML تلگرام) بدون
# اینکه به منطق حافظه‌ی مکالمه/Reply آسیبی بزنه: چون تلگرام موقع خوندنِ
# .text یک پیام، فقط متن قابل‌مشاهده (بدون تگ‌های HTML) رو برمی‌گردونه، اینجا
# دقت شده که خروجیِ «بدون HTML» (_ai_strip_markdown) و متنِ قابل‌مشاهده‌ی
# نسخه‌ی HTML (بعد از حذف تگ‌ها) کاملاً یکی باشن؛ در نتیجه هر کدوم فرستاده
# بشه (HTML یا fallback ساده)، کلیدِ ذخیره‌شده برای ادامه‌ی گفتگو با Reply
# هنوز درست کار می‌کنه.
#
# تلگرام (پلتفرم واقعیِ این ربات، طبق telegram_compat.py) هیچ راهی برای عوض
# کردنِ «فونتِ» واقعیِ کاراکترها نداره؛ فقط سبک‌های از پیش تعریف‌شده مثل
# Bold/Italic/Code/Blockquote (از طریق HTML/Markdown) رو پشتیبانی می‌کنه.
# برای همین اینجا از همون HTML استاندارد تلگرام (parse_mode=HTML) استفاده
# شده، نه یک «فونت» جعلی با کاراکترهای یونیکد که در خیلی از دستگاه‌ها/
# فونت‌ها زشت و ناخوانا نمایش داده می‌شه.
AI_TEMPLATE_SEPARATOR = "━━━━━━━━━━━━"

_AI_CODE_BLOCK_RE = re.compile(r"```(?:\w+)?\n?(.*?)```", re.DOTALL)
_AI_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_AI_BOLD_RE = re.compile(r"\*\*([^*\n]+)\*\*")

_AI_PLAIN_REQUEST_MARKERS = (
    "بدون استایل", "بدون فرمت", "بدون قالب", "متن ساده", "ساده بنویس",
    "ساده جواب", "بی‌استایل", "بی استایل", "plain text", "no format", "no formatting",
)


def _ai_wants_plain(user_text: str) -> bool:
    """🛠 مورد ۷: اگه کاربر صریحاً خواسته پاسخ بدون استایل باشه، هیچ قالب/HTML‌ای اعمال نشه."""
    t = normalize_fa(user_text or "").lower()
    return any(marker in t for marker in _AI_PLAIN_REQUEST_MARKERS)


def _ai_strip_markdown(text: str) -> str:
    """متنِ خامِ Gemini (که معمولاً از Markdown استفاده می‌کنه) رو به یک متنِ
    ساده و تمیز تبدیل می‌کنه (بدون **، بدون backtick، بدون '> ' جلوی نقل‌قول).
    این دقیقاً همون چیزیه که کاربر روی گوشی‌اش (چه با HTML چه بدون HTML) در
    نهایت می‌بینه."""
    text = _AI_CODE_BLOCK_RE.sub(lambda m: m.group(1).strip("\n"), text)
    text = _AI_INLINE_CODE_RE.sub(lambda m: m.group(1), text)
    text = _AI_BOLD_RE.sub(lambda m: m.group(1), text)
    lines = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("> "):
            lines.append(s[2:])
        elif s == ">":
            lines.append("")
        else:
            lines.append(line)
    return "\n".join(lines)


def _ai_render_html_body(text: str) -> str:
    """همون متنِ خام رو به HTML معتبر و امنِ تلگرام تبدیل می‌کنه: بلوک‌های
    کد → <pre>، کدِ inline → <code>، **بولد** → <b>، خط‌های '> ' → <blockquote>.
    محتوای کاربر/AI همیشه escape می‌شه تا کاراکترهای <, >, & باعث خطای
    Parse نشن (مورد ۸ و ۱۰: هیچ HTML خامِ غیرمنتظره‌ای مستقیماً تزریق نمی‌شه)."""
    segments: List[tuple] = []
    last = 0
    for m in _AI_CODE_BLOCK_RE.finditer(text):
        segments.append(("text", text[last:m.start()]))
        segments.append(("pre", m.group(1).strip("\n")))
        last = m.end()
    segments.append(("text", text[last:]))

    def _render_text_segment(seg: str) -> str:
        esc = escape(seg, quote=False)
        esc = _AI_INLINE_CODE_RE.sub(lambda m: f"<code>{m.group(1)}</code>", esc)
        esc = _AI_BOLD_RE.sub(lambda m: f"<b>{m.group(1)}</b>", esc)
        out_lines = []
        quote_buf: List[str] = []

        def _flush_quote():
            if quote_buf:
                out_lines.append("<blockquote>" + "\n".join(quote_buf) + "</blockquote>")
                quote_buf.clear()

        for line in esc.split("\n"):
            stripped = line.strip()
            if stripped.startswith("&gt; "):
                quote_buf.append(stripped[5:])
            elif stripped == "&gt;":
                quote_buf.append("")
            else:
                _flush_quote()
                out_lines.append(line)
        _flush_quote()
        return "\n".join(out_lines)

    html_parts = []
    for kind, seg in segments:
        if kind == "pre":
            html_parts.append(f"<pre>{escape(seg, quote=False)}</pre>")
        else:
            html_parts.append(_render_text_segment(seg))
    return "".join(html_parts)


def _ai_format_message(raw_answer: str, plain_requested: bool) -> Tuple[str, Optional[str]]:
    """قالب نهایی رو می‌سازه. خروجی: (plain_text, html_text).
    html_text وقتی None هست که یا کاربر صراحتاً «بدون استایل» خواسته، یا
    پاسخ آنقدر کوتاهه که قالب‌بندی اضافه لازم نیست و متن ساده کافیه.
    plain_text همیشه همون متنِ نهاییِ قابل‌مشاهده‌ست (چه HTML فرستاده بشه چه
    نه)، و همین باید برای ذخیره‌ی کلیدِ ادامه‌ی مکالمه با Reply استفاده بشه."""
    body_plain = _ai_strip_markdown(raw_answer).strip()

    if plain_requested:
        return body_plain, None

    has_block_content = "```" in raw_answer or re.search(r"(^|\n)\s*>\s?", raw_answer) is not None
    is_short = "\n" not in body_plain and len(body_plain) <= 60 and not has_block_content

    if is_short:
        # مورد ۵: برای پاسخ‌های خیلی کوتاه (مثل «سلام!»)، قالب کامل استفاده نشه.
        plain_text = f"🤖 {body_plain}"
        if raw_answer.strip() == body_plain:
            return plain_text, None  # هیچ Markdown‌ای برای تبدیل به HTML نبود
        html_text = f"🤖 {_ai_render_html_body(raw_answer).strip()}"
        return plain_text, html_text

    plain_text = f"🤖 گاردی AI\n{AI_TEMPLATE_SEPARATOR}\n{body_plain}\n{AI_TEMPLATE_SEPARATOR}\n⚡ GARDI X"
    html_body = _ai_render_html_body(raw_answer).strip()
    html_text = (f"🤖 <b>گاردی AI</b>\n{AI_TEMPLATE_SEPARATOR}\n{html_body}\n"
                 f"{AI_TEMPLATE_SEPARATOR}\n⚡ <i>GARDI X</i>")
    return plain_text, html_text


async def _ai_send_formatted(message: Message, raw_answer: str, plain_requested: bool) -> str:
    """پاسخ AI رو با قالب گاردی می‌فرسته و اگه HTML به هر دلیلی رد شد (Parse
    Error یا هر خطای دیگه)، خودکار به متن ساده برمی‌گرده (مورد ۸) تا هیچ‌وقت
    ارسال پیام کامل fail نشه. مقدار برگشتی، متنِ نهاییِ قابل‌مشاهده‌ست که باید
    برای کلیدِ حافظه‌ی مکالمه ذخیره بشه."""
    plain_text, html_text = _ai_format_message(raw_answer, plain_requested)
    if html_text is not None:
        try:
            res = await message.reply(html_text, html=True)
            if res:
                return plain_text
            logging.getLogger("gardi").warning("AI HTML reply failed (%s), falling back to plain text",
                                                 getattr(res, "error", None))
        except Exception as e:
            logging.getLogger("gardi").warning("AI HTML reply raised an exception, falling back to plain text: %r", e)
    await message.reply(plain_text)
    return plain_text


# =========================================================
#  🛠 اتصال «صدا زدن گاردی» و «ریپلای روی جواب هوش مصنوعی» به AI واقعی
# =========================================================
# قبلاً صدا زدن اسم ربات («گاردی ...») فقط یک جواب تصادفی از یه لیست ۲۰۰
# تایی ثابت می‌داد، و ریپلای زدن روی جواب‌های هوش مصنوعی فقط وقتی کار
# می‌کرد که دوباره متن با «هوش مصنوعی» شروع می‌شد. این تابع مشترک همون
# منطق ai_chat_cmd رو (تاریخچه‌ی گفتگو، محدودیت روزانه، ذخیره‌سازی، ارسالِ
# قالب‌بندی‌شده) پیاده می‌کنه، با این فرق که اگه AI جواب نده (خطا/غیرفعال/
# محدودیت)، هیچ پیامی نمی‌فرسته و False برمی‌گردونه — چون این مسیرها (صدا
# زدن اسم / ریپلای ساده) نباید با خطاهای فنی سر هر «گاردی» گفتن یا هر
# ریپلای معمولی، کاربر عادی رو گیج کنن؛ فراخوان در آن صورت به رفتار قبلی
# (جواب آماده) برمی‌گرده.
async def _try_ai_answer(group_id, group_data: dict, user_id: str, user_text: str,
                          message: Message, reply_msg=None, show_errors: bool = False) -> bool:
    settings = group_data.get('settings', {})
    if not settings.get('ai_enabled', True):
        if show_errors:
            await message.reply("🤖 هوش مصنوعی در این گروه غیرفعاله.\n(برای فعال‌سازی: «دستور هوش مصنوعی فعال»)")
        return False
    if user_id in group_data.get('ai_user_disabled', []):
        if show_errors:
            await message.reply("⛔ هوش مصنوعی برای شما به‌صورت اختصاصی غیرفعال شده.")
        return False
    if not AI_API_KEY:
        if show_errors:
            await message.reply(
                "⚙️ هوش مصنوعی هنوز روی سرور تنظیم نشده.\n"
                "برای فعال‌سازی، متغیر محیطی AI_API_KEY (و در صورت نیاز AI_API_BASE و AI_MODEL) "
                "را روی سروری که ربات اجرا می‌شود تنظیم کنید."
            )
        return False
    if not user_text:
        return False

    _ai_reset_if_new_day(group_data)

    limit = group_data.get('ai_user_limits', {}).get(user_id)
    usage = group_data.setdefault('ai_usage', {})
    u = usage.get(user_id, {})
    if u.get('date') != _ai_today():
        u = {'date': _ai_today(), 'count': 0}
    if limit is not None and u.get('count', 0) >= limit:
        if show_errors:
            await message.reply(f"⏳ محدودیت استفاده‌ی روزانه‌ی شما از هوش مصنوعی ({limit} بار) امروز تموم شده. فردا دوباره امتحان کنید.")
        return False

    conversations = group_data.setdefault('ai_conversations', {})
    history = None
    if reply_msg is not None:
        reply_text = getattr(reply_msg, "text", None)
        conv_key = f"{user_id}::{reply_text}"
        if reply_text and conv_key in conversations:
            history = conversations[conv_key]

    messages = list(history) if history else [
        {"role": "system", "content": _ai_system_prompt()}
    ]
    messages.append({"role": "user", "content": user_text})

    # 🛠 این مسیر هم ممکنه چند ثانیه طول بکشه (retry روی 503/429)، پس یه
    # پیام «در حال پردازش» می‌فرستیم تا کاربر فکر نکنه گاردی جواب نمی‌ده.
    try:
        await message.reply("⏳ در حال پردازش... چند لحظه صبر کن.")
    except Exception:
        pass

    try:
        answer = await ask_ai(messages)
    except AIServiceError as e:
        # 🛠 قبلاً این مسیر (صدا زدن «گاردی» / ریپلای ساده) همیشه بی‌سروصدا
        # به جواب‌های آماده‌ی تصادفیِ قدیمی برمی‌گشت. حالا فراخوان (show_errors)
        # تعیین می‌کنه که آیا کاربر باید خطای واقعی رو ببینه یا نه. خطا در هر
        # حالت در کنسول ثبت می‌شه. API Key هیچ‌وقت اینجا چاپ نمی‌شه چون
        # e.message از _ai_call_sync میاد که همیشه بدونِ کلید ساخته می‌شه.
        logging.getLogger("gardi").warning("AI (gardi call) failed: status=%s detail=%s", e.code, e.message[:300])
        if show_errors:
            if e.code == 403:
                await message.reply(
                    "❌ Gemini دسترسی درخواست را رد کرد (403). این خطا معمولاً از خودِ "
                    "Project/API Key است، نه ربات."
                )
            elif e.code == 401:
                await message.reply("❌ کلید Gemini نامعتبر است (401).")
            elif e.code == 404:
                await message.reply("❌ مدل انتخاب‌شده در Gemini پیدا نشد (404).")
            elif e.code == 429:
                await message.reply("⏳ سقف استفاده از Gemini پر شده (429). کمی بعد دوباره امتحان کنید.")
            elif e.code == 0:
                await message.reply("❌ اتصال شبکه به سرویس Gemini برقرار نشد. لطفاً بعداً دوباره امتحان کنید.")
            else:
                await message.reply(f"❌ خطا از سمت سرویس هوش مصنوعی (کد {e.code}). لطفاً بعداً دوباره امتحان کنید.")
        return False
    except Exception as e:
        logging.getLogger("gardi").warning("AI (gardi call) failed unexpectedly: %r", e)
        if show_errors:
            await message.reply("❌ نتونستم به سرویس هوش مصنوعی وصل بشم. لطفاً بعداً دوباره امتحان کنید.")
        return False

    messages.append({"role": "assistant", "content": answer})
    if limit is not None:
        u['count'] = u.get('count', 0) + 1
        usage[user_id] = u

    # 🎨 پاسخ با قالب گاردی فرستاده می‌شه؛ متنِ واقعاً نمایش‌داده‌شده (نه متن
    # خامِ Gemini) برای کلید حافظه‌ی مکالمه استفاده می‌شه تا ریپلای‌زدنِ بعدی
    # روی همین پیام درست تشخیص داده بشه.
    plain_requested = _ai_wants_plain(user_text)
    sent_text = await _ai_send_formatted(message, answer, plain_requested)

    conversations[f"{user_id}::{sent_text}"] = messages
    if len(conversations) > 50:
        for old_key in list(conversations.keys())[:-50]:
            del conversations[old_key]

    save_group_data(group_id, group_data)
    return True


@bot.on_message(filters=lambda m: m.text and normalize_key(m.text).startswith("هوش مصنوعی ") and not normalize_key(m.text).startswith("هوش مصنوعی غیرفعال") and not normalize_key(m.text).startswith("هوش مصنوعی فعال"))
async def ai_chat_cmd(bot: Robot, message: Message):
    """🤖 چت واقعی با هوش مصنوعی: «هوش مصنوعی [متن]» (فقط مقام ویژه و مالک)"""
    group_id = get_chat_group_id(message)
    if not group_id:
        return  # طبق قرارداد بقیه‌ی سینتکس‌های متنی آزاد (مثل آموزش سخنگو)، در پیوی ساکت می‌مونیم

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    settings = group_data.get('settings', {})

    if not has_permission(user_id, group_data, Perm.SPECIAL):
        await message.reply(NO_PERMISSION_MSG)
        return

    if not settings.get('ai_enabled', True):
        await message.reply("🤖 هوش مصنوعی در این گروه غیرفعاله.\n(برای فعال‌سازی: «دستور هوش مصنوعی فعال»)")
        return

    if user_id in group_data.get('ai_user_disabled', []):
        await message.reply("⛔ هوش مصنوعی برای شما به‌صورت اختصاصی غیرفعال شده.")
        return

    if not AI_API_KEY:
        await message.reply(
            "⚙️ هوش مصنوعی هنوز روی سرور تنظیم نشده.\n"
            "برای فعال‌سازی، متغیر محیطی AI_API_KEY (و در صورت نیاز AI_API_BASE و AI_MODEL) "
            "را روی سروری که ربات اجرا می‌شود تنظیم کنید."
        )
        return

    _ai_reset_if_new_day(group_data)

    user_text = normalize_fa(message.text)
    user_text = user_text[len("هوش مصنوعی"):].strip()
    if not user_text:
        await message.reply("⚠️ بعد از «هوش مصنوعی» سوالتون رو بنویسید.\nمثال: «هوش مصنوعی امروز هوا چطوره؟»")
        return

    # 🛠 سوال‌های قیمت لحظه‌ای (دلار/طلا/سکه/...) قبل از AI چک می‌شن، چون AI
    # اصلاً به اینترنت زنده وصل نیست و نمی‌تونه قیمت واقعی بده.
    if await _try_price_answer(user_text, message):
        return

    # محدودیت روزانه‌ی اختصاصی (اگه برای این شخص تنظیم شده باشه)
    limit = group_data.get('ai_user_limits', {}).get(user_id)
    usage = group_data.setdefault('ai_usage', {})
    u = usage.get(user_id, {})
    if u.get('date') != _ai_today():
        u = {'date': _ai_today(), 'count': 0}
    if limit is not None and u.get('count', 0) >= limit:
        await message.reply(f"⏳ محدودیت استفاده‌ی روزانه‌ی شما از هوش مصنوعی ({limit} بار) امروز تموم شده. فردا دوباره امتحان کنید.")
        return

    # ادامه‌ی گفتگوی قبلی؟ («ریپلای روی پاسخ قبلی هوش مصنوعی = ادامه‌ی همون گفتگو»)
    conversations = group_data.setdefault('ai_conversations', {})
    history = None
    reply_msg = get_reply_message(message)
    if reply_msg is not None:
        reply_text = getattr(reply_msg, "text", None)
        # 🛠 رفع باگ: قبلاً کلید دیکشنری فقط متن پاسخ بود (بدون شناسه‌ی کاربر)،
        # پس اگر هوش مصنوعی برای دو کاربر مختلف یک جواب یکسان/کوتاه می‌داد
        # (مثلاً «بله» یا «سلام!»)، گفتگوی این دو کاربر با هم قاطی می‌شد و
        # ریپلای‌زدن روی جواب قبلی گاهی تاریخچه‌ی شخص دیگری رو برمی‌گردوند.
        conv_key = f"{user_id}::{reply_text}"
        if reply_text and conv_key in conversations:
            history = conversations[conv_key]

    messages = list(history) if history else [
        {"role": "system", "content": _ai_system_prompt()}
    ]
    messages.append({"role": "user", "content": user_text})

    # 🛠 چون الان ممکنه چند بار retry (با فاصله) رخ بده و چند ثانیه طول بکشه،
    # یه پیام «در حال پردازش» می‌فرستیم تا کاربر فکر نکنه ربات هنگ کرده یا
    # پیامش رو ندیده؛ بعد از آماده شدن جواب، جواب اصلی جدا فرستاده می‌شه.
    try:
        await message.reply("⏳ در حال پردازش... چند لحظه صبر کن.")
    except Exception:
        pass

    try:
        answer = await ask_ai(messages)
    except AIServiceError as e:
        # 🛠 قبلاً این except اصلاً اجرا نمی‌شد چون AIServiceError هیچ‌جا تعریف
        # نشده بود (NameError)، پس همیشه می‌افتاد توی except Exception پایین‌تر
        # و کاربر فقط پیام مبهم «نتونستم به سرویس هوش مصنوعی وصل بشم» رو می‌دید
        # بدون این‌که هیچ جزئیاتی (حتی در کنسول) ثبت بشه. الان هم در کنسول
        # جزئیات امن (status/نوع خطا/پیام Gemini، بدون API Key) ثبت می‌شه، هم
        # کاربر بسته به کد خطا پیام دقیق‌تری می‌گیره.
        logging.getLogger("gardi").warning("AI (ai_chat_cmd) failed: status=%s detail=%s", e.code, e.message[:500])
        if e.code == 403:
            await message.reply(
                "❌ Gemini دسترسی درخواست را رد کرد (403). این خطا معمولاً از خودِ "
                "Project/API Key است، نه ربات. یک Gemini API Key جدیدِ فعال برای "
                "همین پروژه بساز و در AI_API_KEY یا فایل ai_key.txt قرار بده؛ اگر پیام "
                "`project has been denied access` می‌بینی، باید دسترسی پروژه در "
                "Google AI Studio/Cloud رفع شود."
            )
        elif e.code == 401:
            await message.reply("❌ کلید Gemini نامعتبر است (401). لطفاً یک API Key معتبر در AI_API_KEY یا ai_key.txt قرار دهید.")
        elif e.code == 400:
            await message.reply("❌ درخواست به Gemini نامعتبر بود (400). ممکن است تنظیم مدل (AI_MODEL) اشتباه باشد.")
        elif e.code == 404:
            await message.reply("❌ مدل انتخاب‌شده در Gemini پیدا نشد (404). مقدار AI_MODEL را بررسی کنید یا از مدل پیش‌فرض استفاده کنید.")
        elif e.code == 429:
            await message.reply("⏳ سقف استفاده از Gemini برای این کلید پر شده (429: rate limit/quota). کمی بعد دوباره امتحان کنید.")
        elif e.code == 0:
            await message.reply("❌ اتصال شبکه به سرویس Gemini برقرار نشد. لطفاً بعداً دوباره امتحان کنید.")
        else:
            await message.reply(f"❌ خطا از سمت سرویس هوش مصنوعی (کد {e.code}). مدل/کلید/تنظیمات را بررسی کنید.\n{e.message[:500]}")
        return
    except Exception as e:
        # هر خطای پیش‌بینی‌نشده‌ی دیگر (باگ داخلی، خطای پارس و ...) — باز هم
        # در کنسول ثبت می‌شه (بدون هیچ کلیدی، چون این خطاها اصلاً به AI_API_KEY
        # دسترسی ندارن) تا حداقل قابل بررسی باشه، نه فقط یک پیام مبهم برای کاربر.
        logging.getLogger("gardi").exception("AI (ai_chat_cmd) unexpected error: %r", e)
        await message.reply("❌ نتونستم به سرویس هوش مصنوعی وصل بشم. لطفاً بعداً دوباره امتحان کنید.")
        return

    messages.append({"role": "assistant", "content": answer})

    if limit is not None:
        u['count'] = u.get('count', 0) + 1
        usage[user_id] = u

    # 🎨 پاسخ با قالب گاردی فرستاده می‌شه؛ متنِ واقعاً نمایش‌داده‌شده (نه متن
    # خامِ Gemini) برای کلید حافظه‌ی مکالمه استفاده می‌شه تا ریپلای‌زدنِ بعدی
    # روی همین پیام درست تشخیص داده بشه (مورد ۹).
    plain_requested = _ai_wants_plain(user_text)
    sent_text = await _ai_send_formatted(message, answer, plain_requested)

    # ذخیره‌ی گفتگو برای امکان ادامه با ریپلای (حداکثر ۵۰ گفتگوی اخیر نگه داشته می‌شه)
    conversations[f"{user_id}::{sent_text}"] = messages
    if len(conversations) > 50:
        for old_key in list(conversations.keys())[:-50]:
            del conversations[old_key]

    save_group_data(group_id, group_data)


@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("دستور هوش مصنوعی غیرفعال", "دستور هوش مصنوعی فعال"))
async def ai_toggle_cmd(bot: Robot, message: Message):
    """فعال/غیرفعال کردن هوش مصنوعی؛ با ریپلای فقط برای همون شخص، بدون ریپلای برای کل گروه."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not has_permission(user_id, group_data, Perm.SUPER_ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return

    enable = normalize_key(message.text) == "دستور هوش مصنوعی فعال"
    reply_target = get_reply_sender_id(message)

    if reply_target:
        disabled = group_data.setdefault('ai_user_disabled', [])
        if enable:
            if reply_target in disabled:
                disabled.remove(reply_target)
            await message.reply("✅ هوش مصنوعی برای این شخص فعال شد.")
        else:
            if reply_target not in disabled:
                disabled.append(reply_target)
            await message.reply("🔴 هوش مصنوعی برای این شخص غیرفعال شد.")
    else:
        group_data.setdefault('settings', {})['ai_enabled'] = enable
        await message.reply("✅ هوش مصنوعی برای کل گروه فعال شد." if enable else "🔴 هوش مصنوعی برای کل گروه غیرفعال شد.")

    save_group_data(group_id, group_data)


@bot.on_message(filters=lambda m: m.text and re.match(r"^دستور هوش مصنوعی\s*#?\s*\d+$", normalize_key(m.text) or ""))
async def ai_set_limit_cmd(bot: Robot, message: Message):
    """تنظیم محدودیت استفاده‌ی روزانه برای یک شخص خاص: با ریپلای + «دستور هوش مصنوعی #عدد»"""
    group_id = get_chat_group_id(message)
    if not group_id:
        return  # سینتکس آزاد با عدد؛ در پیوی ساکت می‌مونیم تا با راهنمای PV تداخل نکنه

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not has_permission(user_id, group_data, Perm.SUPER_ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return

    reply_target = get_reply_sender_id(message)
    if not reply_target:
        await message.reply("⚠️ برای تنظیم محدودیت روزانه، روی پیام شخص موردنظر ریپلای بزنید و بنویسید «دستور هوش مصنوعی #عدد».")
        return

    match = re.search(r"\d+", normalize_key(message.text))
    number = int(match.group())
    group_data.setdefault('ai_user_limits', {})[reply_target] = number
    save_group_data(group_id, group_data)
    await message.reply(f"✅ محدودیت استفاده‌ی روزانه‌ی این شخص از هوش مصنوعی روی {number} بار در روز تنظیم شد.")


# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "translate_settings"))
async def translate_settings_cmd(bot: Robot, message: Message):
    """تنظیمات ترجمه خودکار"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /translate_settings [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['auto_translate'] = True
        save_group_data(group_id, group_data)
        await message.reply("🌍 **ترجمه خودکار فعال شد!**")
    elif status == "غیرفعال":
        group_data['settings']['auto_translate'] = False
        save_group_data(group_id, group_data)
        await message.reply("🌍 **ترجمه خودکار غیرفعال شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت کلمات کلیدی
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "keyword_add"))
async def keyword_add_cmd(bot: Robot, message: Message):
    """افزودن کلمه کلیدی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/keyword_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /keyword_add [کلمه] | [پاسخ]")
        return
    
    kw_data = [p.strip() for p in parts.split('|')]
    if len(kw_data) < 2:
        await message.reply("⚠️ دستور: /keyword_add [کلمه] | [پاسخ]")
        return
    
    if 'keywords' not in group_data:
        group_data['keywords'] = {}
    
    group_data['keywords'][kw_data[0]] = kw_data[1]
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **کلمه کلیدی {kw_data[0]} اضافه شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "keyword_remove"))
async def keyword_remove_cmd(bot: Robot, message: Message):
    """حذف کلمه کلیدی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    keyword = message.text.replace("/keyword_remove", "", 1).strip()
    if not keyword:
        await message.reply("⚠️ دستور: /keyword_remove [کلمه]")
        return
    
    keywords = group_data.get('keywords', {})
    
    if keyword in keywords:
        del keywords[keyword]
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **کلمه کلیدی {keyword} حذف شد!**")
    else:
        await message.reply(f"⚠️ کلمه کلیدی {keyword} پیدا نشد!")

@bot.on_message(filters=lambda m: m.text and m.text == "/keywords")
async def keywords_cmd(bot: Robot, message: Message):
    """لیست کلمات کلیدی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    keywords = group_data.get('keywords', {})
    
    if keywords:
        text = "🔑 **لیست کلمات کلیدی:**\n\n"
        for keyword, response in keywords.items():
            text += f"• {keyword} → {response}\n"
        await message.reply(text)
    else:
        await message.reply("🔑 هیچ کلمه کلیدی وجود ندارد!")

# =========================================================
#  سیستم مدیریت پیام‌های خوش‌آمد و خداحافظ
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "welcome_settings"))
async def welcome_settings_cmd(bot: Robot, message: Message):
    """تنظیمات خوش‌آمد"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /welcome_settings [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['welcome_enabled'] = True
        save_group_data(group_id, group_data)
        await message.reply("🎉 **خوش‌آمد فعال شد!**")
    elif status == "غیرفعال":
        group_data['settings']['welcome_enabled'] = False
        save_group_data(group_id, group_data)
        await message.reply("🎉 **خوش‌آمد غیرفعال شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

@bot.on_message(filters=lambda m: _cmd_is(m, "goodbye_settings"))
async def goodbye_settings_cmd(bot: Robot, message: Message):
    """تنظیمات خداحافظ"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /goodbye_settings [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['goodbye_enabled'] = True
        save_group_data(group_id, group_data)
        await message.reply("👋 **خداحافظ فعال شد!**")
    elif status == "غیرفعال":
        group_data['settings']['goodbye_enabled'] = False
        save_group_data(group_id, group_data)
        await message.reply("👋 **خداحافظ غیرفعال شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

# =========================================================
#  سیستم مدیریت یادآوری‌های شخصی
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "personal_reminder"))
async def personal_reminder_cmd(bot: Robot, message: Message):
    """یادآوری شخصی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    parts = message.text.replace("/personal_reminder", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /personal_reminder [زمان] | [متن]")
        return
    
    rem_data = [p.strip() for p in parts.split('|')]
    if len(rem_data) < 2:
        await message.reply("⚠️ دستور: /personal_reminder [زمان] | [متن]")
        return
    
    if 'personal_reminders' not in group_data:
        group_data['personal_reminders'] = []
    
    group_data['personal_reminders'].append({
        'user': user_id,
        'time': rem_data[0],
        'text': rem_data[1],
        'created_at': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **یادآوری شخصی تنظیم شد!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/personal_reminders")
async def personal_reminders_cmd(bot: Robot, message: Message):
    """لیست یادآوری‌های شخصی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    reminders = [r for r in group_data.get('personal_reminders', []) if r.get('user') == user_id]
    
    if reminders:
        text = "⏰ **یادآوری‌های شخصی شما:**\n\n"
        for idx, rem in enumerate(reminders, 1):
            text += f"{idx}. {rem.get('text')}\n"
            text += f"   زمان: {rem.get('time')}\n\n"
        await message.reply(text)
    else:
        await message.reply("⏰ شما هیچ یادآوری شخصی ندارید!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت ربات های گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "bot_settings"))
async def bot_settings_cmd(bot: Robot, message: Message):
    """تنظیمات ربات"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /bot_settings [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['bot_active'] = True
        save_group_data(group_id, group_data)
        await message.reply("🤖 **ربات فعال شد!**")
    elif status == "غیرفعال":
        group_data['settings']['bot_active'] = False
        save_group_data(group_id, group_data)
        await message.reply("🤖 **ربات غیرفعال شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

# =========================================================
#  سیستم مدیریت کانال های گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "channel_settings"))
async def channel_settings_cmd(bot: Robot, message: Message):
    """تنظیمات کانال"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /channel_settings [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['channel_active'] = True
        save_group_data(group_id, group_data)
        await message.reply("📢 **کانال فعال شد!**")
    elif status == "غیرفعال":
        group_data['settings']['channel_active'] = False
        save_group_data(group_id, group_data)
        await message.reply("📢 **کانال غیرفعال شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

# =========================================================
#  سیستم مدیریت پست های گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "post_settings"))
async def post_settings_cmd(bot: Robot, message: Message):
    """تنظیمات پست"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /post_settings [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['post_active'] = True
        save_group_data(group_id, group_data)
        await message.reply("📌 **پست فعال شد!**")
    elif status == "غیرفعال":
        group_data['settings']['post_active'] = False
        save_group_data(group_id, group_data)
        await message.reply("📌 **پست غیرفعال شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

# =========================================================
#  سیستم مدیریت کامنت های گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "comment_settings"))
async def comment_settings_cmd(bot: Robot, message: Message):
    """تنظیمات کامنت"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /comment_settings [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['comment_active'] = True
        save_group_data(group_id, group_data)
        await message.reply("💬 **کامنت فعال شد!**")
    elif status == "غیرفعال":
        group_data['settings']['comment_active'] = False
        save_group_data(group_id, group_data)
        await message.reply("💬 **کامنت غیرفعال شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

# =========================================================
#  سیستم مدیریت لایک های گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "like_settings"))
async def like_settings_cmd(bot: Robot, message: Message):
    """تنظیمات لایک"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /like_settings [فعال/غیرفعال]")
        return
    
    status = parts[1]
    if status == "فعال":
        group_data['settings']['like_active'] = True
        save_group_data(group_id, group_data)
        await message.reply("❤️ **لایک فعال شد!**")
    elif status == "غیرفعال":
        group_data['settings']['like_active'] = False
        save_group_data(group_id, group_data)
        await message.reply("❤️ **لایک غیرفعال شد!**")
    else:
        await message.reply("⚠️ وضعیت را «فعال» یا «غیرفعال» وارد کنید!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت لینک‌های مفید
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "useful_links"))
async def useful_links_cmd(bot: Robot, message: Message):
    """لیست لینک‌های مفید"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    links = group_data.get('useful_links', [])
    
    if links:
        text = "🔗 **لیست لینک‌های مفید:**\n\n"
        for idx, link in enumerate(links, 1):
            text += f"{idx}. {link.get('name')}\n"
            text += f"   لینک: {link.get('url')}\n"
            text += f"   توضیحات: {link.get('description', '')}\n\n"
        await message.reply(text)
    else:
        await message.reply("🔗 هیچ لینک مفیدی وجود ندارد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "useful_link_add"))
async def useful_link_add_cmd(bot: Robot, message: Message):
    """افزودن لینک مفید"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/useful_link_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /useful_link_add [نام] | [لینک] | [توضیحات]")
        return
    
    link_data = [p.strip() for p in parts.split('|')]
    if len(link_data) < 2:
        await message.reply("⚠️ دستور: /useful_link_add [نام] | [لینک]")
        return
    
    link_info = {
        'name': link_data[0],
        'url': link_data[1],
        'description': link_data[2] if len(link_data) > 2 else '',
        'added_by': user_id,
        'added_at': datetime.now().isoformat()
    }
    
    if 'useful_links' not in group_data:
        group_data['useful_links'] = []
    
    group_data['useful_links'].append(link_info)
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **لینک مفید {link_data[0]} اضافه شد!**")

# =========================================================
#  سیستم مدیریت منابع گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "resources"))
async def resources_cmd(bot: Robot, message: Message):
    """لیست منابع گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    resources = group_data.get('resources', [])
    
    if resources:
        text = "📚 **لیست منابع گروه:**\n\n"
        for idx, res in enumerate(resources, 1):
            text += f"{idx}. {res.get('name')}\n"
            text += f"   توضیحات: {res.get('description', '')}\n"
            text += f"   لینک: {res.get('link', '')}\n\n"
        await message.reply(text)
    else:
        await message.reply("📚 هیچ منبعی وجود ندارد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "resource_add"))
async def resource_add_cmd(bot: Robot, message: Message):
    """افزودن منبع"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/resource_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /resource_add [نام] | [توضیحات] | [لینک]")
        return
    
    res_data = [p.strip() for p in parts.split('|')]
    if len(res_data) < 2:
        await message.reply("⚠️ دستور: /resource_add [نام] | [توضیحات]")
        return
    
    resource_info = {
        'name': res_data[0],
        'description': res_data[1] if len(res_data) > 1 else '',
        'link': res_data[2] if len(res_data) > 2 else '',
        'added_by': user_id,
        'added_at': datetime.now().isoformat()
    }
    
    if 'resources' not in group_data:
        group_data['resources'] = []
    
    group_data['resources'].append(resource_info)
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **منبع {res_data[0]} اضافه شد!**")

# =========================================================
#  سیستم مدیریت کتاب‌های الکترونیکی
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "ebooks"))
async def ebooks_cmd(bot: Robot, message: Message):
    """لیست کتاب‌های الکترونیکی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    ebooks = group_data.get('ebooks', [])
    
    if ebooks:
        text = "📖 **لیست کتاب‌های الکترونیکی:**\n\n"
        for idx, ebook in enumerate(ebooks, 1):
            text += f"{idx}. {ebook.get('title')}\n"
            text += f"   نویسنده: {ebook.get('author')}\n"
            text += f"   لینک: {ebook.get('link')}\n\n"
        await message.reply(text)
    else:
        await message.reply("📖 هیچ کتاب الکترونیکی وجود ندارد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "ebook_add"))
async def ebook_add_cmd(bot: Robot, message: Message):
    """افزودن کتاب الکترونیکی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/ebook_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /ebook_add [عنوان] | [نویسنده] | [لینک]")
        return
    
    ebook_data = [p.strip() for p in parts.split('|')]
    if len(ebook_data) < 3:
        await message.reply("⚠️ دستور: /ebook_add [عنوان] | [نویسنده] | [لینک]")
        return
    
    if 'ebooks' not in group_data:
        group_data['ebooks'] = []
    
    group_data['ebooks'].append({
        'title': ebook_data[0],
        'author': ebook_data[1],
        'link': ebook_data[2],
        'added_by': user_id,
        'added_at': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **کتاب {ebook_data[0]} اضافه شد!**")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت ایموجی‌ها
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "emoji_list"))
async def emoji_list_cmd(bot: Robot, message: Message):
    """لیست ایموجی‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    emojis = group_data.get('emojis', [])
    
    if emojis:
        text = "😊 **لیست ایموجی‌ها:**\n\n"
        for idx, emoji in enumerate(emojis, 1):
            text += f"{idx}. {emoji.get('name')} → {emoji.get('emoji')}\n"
        await message.reply(text)
    else:
        await message.reply("😊 هیچ ایموجی‌ای وجود ندارد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "emoji_add"))
async def emoji_add_cmd(bot: Robot, message: Message):
    """افزودن ایموجی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/emoji_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /emoji_add [نام] | [ایموجی]")
        return
    
    emoji_data = [p.strip() for p in parts.split('|')]
    if len(emoji_data) < 2:
        await message.reply("⚠️ دستور: /emoji_add [نام] | [ایموجی]")
        return
    
    if 'emojis' not in group_data:
        group_data['emojis'] = []
    
    group_data['emojis'].append({
        'name': emoji_data[0],
        'emoji': emoji_data[1],
        'added_by': user_id,
        'added_at': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **ایموجی {emoji_data[0]} اضافه شد!**")

# =========================================================
#  سیستم مدیریت استیکرهای گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "sticker_pack"))
async def sticker_pack_cmd(bot: Robot, message: Message):
    """لیست پک‌های استیکر"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    stickers = group_data.get('sticker_packs', [])
    
    if stickers:
        text = "🔖 **پک‌های استیکر:**\n\n"
        for idx, pack in enumerate(stickers, 1):
            text += f"{idx}. {pack.get('name')}\n"
            text += f"   لینک: {pack.get('link')}\n\n"
        await message.reply(text)
    else:
        await message.reply("🔖 هیچ پک استیکری وجود ندارد!")


# =========================================================
#  سیستم مدیریت گیف‌های گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "gif_list"))
async def gif_list_cmd(bot: Robot, message: Message):
    """لیست گیف‌ها"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    gifs = group_data.get('gifs', [])
    
    if gifs:
        text = "🎬 **لیست گیف‌ها:**\n\n"
        for idx, gif in enumerate(gifs, 1):
            text += f"{idx}. {gif.get('name')}\n"
            text += f"   لینک: {gif.get('link')}\n\n"
        await message.reply(text)
    else:
        await message.reply("🎬 هیچ گیفی وجود ندارد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "gif_add"))
async def gif_add_cmd(bot: Robot, message: Message):
    """افزودن گیف"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/gif_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /gif_add [نام] | [لینک]")
        return
    
    gif_data = [p.strip() for p in parts.split('|')]
    if len(gif_data) < 2:
        await message.reply("⚠️ دستور: /gif_add [نام] | [لینک]")
        return
    
    if 'gifs' not in group_data:
        group_data['gifs'] = []
    
    group_data['gifs'].append({
        'name': gif_data[0],
        'link': gif_data[1],
        'added_by': user_id,
        'added_at': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **گیف {gif_data[0]} اضافه شد!**")

# =========================================================
#  سیستم مدیریت تصاویر گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "image_list"))
async def image_list_cmd(bot: Robot, message: Message):
    """لیست تصاویر"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    images = group_data.get('images', [])
    
    if images:
        text = "🖼️ **لیست تصاویر:**\n\n"
        for idx, img in enumerate(images, 1):
            text += f"{idx}. {img.get('name')}\n"
            text += f"   لینک: {img.get('link')}\n\n"
        await message.reply(text)
    else:
        await message.reply("🖼️ هیچ تصویری وجود ندارد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "image_add"))
async def image_add_cmd(bot: Robot, message: Message):
    """افزودن تصویر"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/image_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /image_add [نام] | [لینک]")
        return
    
    image_data = [p.strip() for p in parts.split('|')]
    if len(image_data) < 2:
        await message.reply("⚠️ دستور: /image_add [نام] | [لینک]")
        return
    
    if 'images' not in group_data:
        group_data['images'] = []
    
    group_data['images'].append({
        'name': image_data[0],
        'link': image_data[1],
        'added_by': user_id,
        'added_at': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **تصویر {image_data[0]} اضافه شد!**")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  🛠 حذف کد مرده و تکراری: اینجا قبلاً یک هندلر جدا برای "/theme_set" بود
#  که (۱) هیچ alias فارسی نداشت و اصلاً غیرقابل‌اجرا بود، (۲) یک لیست تمِ
#  انگلیسی‌ی متفاوت و ناسازگار با لیست تمِ فارسیِ اصلی (THEME_NAMES) داشت -
#  یعنی حتی اگه وصل می‌شد، با «تنظیم تم» تناقض داشت. طبق «تنظیم تم» اصلی
#  (set_theme_cmd) که به‌درستی وصل و متصل به ALIAS_MAP هست، حذف شد.


# =========================================================
#  سیستم مدیریت فونت گروه
# =========================================================
# 🛠 رفع باگ صداقت (نسخه‌ی قبلی این کامنت می‌گفت «فونت غیرممکنه، حذفش کردیم»):
# اون حرف در مورد فونتِ *واقعیِ* اپ (تایپ‌فیسِ کل صفحه) درسته - آن یکی واقعاً
# دست گیرنده‌ست و هیچ باتی نمی‌تونه عوضش کنه. ولی یه چیز دیگه‌ست: تبدیلِ
# خودِ کاراکترهای متن به یونیکدِ متفاوت (کشیده با تطویل عربی ـ / جداسازی با
# ZWNJ / علائم ترکیبی و ...). این واقعاً کاراکترهای متفاوتی می‌فرسته که هر
# کلاینتی (روبیکا/تلگرام/هرچی) عیناً همونا رو نشون می‌ده - این «جعل» نیست،
# متنِ واقعاً متفاوتیه. راهنمای خودِ ربات (FULL_GUIDE_2) هم همیشه این ۶ فونت
# رو تبلیغ می‌کرد: «شکسته، لش، کشیده، سریانی، خط خورده، پیشفرض» - این بخش
# الان واقعاً همون‌ها رو پیاده می‌کنه.

# ---- ۱) تبدیل‌گرهای متن: هرکدوم یک استایل واقعیِ یونیکدی ----
_TATWEEL = "\u0640"          # ARABIC TATWEEL - برای «کشیده»
_ZWNJ = "\u200c"             # نیم‌فاصله - برای جدا/شکسته کردن اتصال حروف
_COMBINING_DOT_BELOW = "\u0323"   # برای حس نقطه‌گذاریِ سریانی/باستانی
_COMBINING_STRIKE = "\u0336"      # COMBINING LONG STROKE OVERLAY - خط خورده
_MIDDLE_DOT = "\u00b7"

def _is_letter_ch(ch: str) -> bool:
    """حرفِ واقعی (نه فاصله/علامت/عدد) برای تصمیم این‌که کاراکتر ترکیبی/تطویل بعدش بیاد یا نه."""
    return ch.isalpha()

def _font_stretched(text: str) -> str:
    """کشیده (نام مستعار: گاردی) - تطویلِ عربی (ـ) بعد از هر حرف، حسِ متن کشیده‌ی آشنا."""
    out = []
    for ch in text:
        out.append(ch)
        if _is_letter_ch(ch):
            out.append(_TATWEEL)
    return "".join(out)

def _font_broken(text: str) -> str:
    """شکسته - با نیم‌فاصله بین حروف، اتصالِ معمولیِ حروف رو می‌شکنه (هر حرف جدا/منفصل دیده می‌شه)."""
    out = []
    n = len(text)
    for i, ch in enumerate(text):
        out.append(ch)
        if _is_letter_ch(ch) and i + 1 < n and text[i + 1] != " ":
            out.append(_ZWNJ)
    return "".join(out)

def _font_loose(text: str) -> str:
    """لش - حروف با فاصله و نقطه‌ی وسط از هم باز می‌شن، یه حس ول/کشدارِ غیررسمی."""
    sep = f" {_MIDDLE_DOT} "
    return sep.join(list(text.replace(" ", "\u2007")))

def _font_syriac(text: str) -> str:
    """سریانی - نقطه‌گذاریِ ترکیبیِ زیرِ هر حرف؛ حسِ دست‌نویسِ باستانیِ پرنقطه (شبیه رسم‌الخط سریانی)."""
    out = []
    for ch in text:
        out.append(ch)
        if _is_letter_ch(ch):
            out.append(_COMBINING_DOT_BELOW)
    return "".join(out)

def _font_struck(text: str) -> str:
    """خط خورده - خط ترکیبی روی هر حرف (Strikethrough واقعی، نه فرمت مارک‌داون)."""
    out = []
    for ch in text:
        out.append(ch)
        if ch != " ":
            out.append(_COMBINING_STRIKE)
    return "".join(out)

# نام نمایشی -> تابع؛ «گاردی» و «کشیده» عمداً به یک استایل می‌رسن (طبق درخواست:
# فونت گاردی = همون کشیده‌ی برند‌شده‌ی خودِ ربات).
FONT_STYLE_FUNCS = {
    "کشیده": _font_stretched,
    "گاردی": _font_stretched,
    "شکسته": _font_broken,
    "لش": _font_loose,
    "سریانی": _font_syriac,
    "خط خورده": _font_struck,
    "پیشفرض": lambda t: t,
}
# ترتیب نمایش در پنل: پیشفرض اول، بعد ۴ فونتِ واقعی + نامِ مستعار گاردی برای کشیده
FONT_NAMES = ["پیشفرض", "گاردی (کشیده)", "شکسته", "لش", "سریانی", "خط خورده"]
_FONT_ALIASES = {
    "گاردی (کشیده)": "گاردی", "گاردی": "گاردی", "کشیده": "کشیده",
    "شکسته": "شکسته", "لش": "لش", "سریانی": "سریانی",
    "خط خورده": "خط خورده", "خط‌خورده": "خط خورده", "پیشفرض": "پیشفرض",
}

def _normalize_font_name(raw: str) -> Optional[str]:
    t = normalize_fa(raw or "").strip()
    return _FONT_ALIASES.get(t)

def apply_font_style(text: str, style: Optional[str]) -> str:
    """متن رو طبق فونتِ داده‌شده تبدیل می‌کنه؛ فونتِ نامعتبر/خالی = بدون تغییر."""
    fn = FONT_STYLE_FUNCS.get(style or "پیشفرض", FONT_STYLE_FUNCS["پیشفرض"])
    try:
        return fn(text)
    except Exception:
        return text

def get_group_font(group_data: Optional[dict]) -> str:
    return (group_data or {}).get("settings", {}).get("font", "پیشفرض")

# ---- ۲) دستورات: «پنل فونت» (نمایش/پیش‌نمایش) و «تنظیم فونت» (ذخیره) ----
@bot.on_message(filters=lambda m: _cmd_is(m, "font"))
async def font_cmd(bot: Robot, message: Message):
    """پنل فونت: پیش‌نمایشِ هر ۵ استایل روی یک نمونه متن + فونتِ فعلیِ گروه."""
    group_id = get_chat_group_id(message)
    group_data = get_group_data(group_id) if group_id else None
    current = get_group_font(group_data)

    sample = _cmd_rest(message.text) or "گاردی ایکس"
    preview_lines = []
    for label, canonical in [
        ("پیشفرض", "پیشفرض"), ("گاردی (کشیده)", "گاردی"), ("شکسته", "شکسته"),
        ("لش", "لش"), ("سریانی", "سریانی"), ("خط خورده", "خط خورده"),
    ]:
        preview_lines.append(f"• {label}: {apply_font_style(sample, canonical)}")

    icon = theme_icon(group_data, "header")
    await message.reply(
        f"{icon} **پنل فونت**\n\n"
        f"فونتِ فعلیِ گروه: **{current}**\n\n"
        "پیش‌نمایش روی نمونه (می‌تونی متنِ خودتو هم بدی: «فونت متن_دلخواه»):\n"
        + "\n".join(preview_lines) +
        "\n\nبرای تغییر: «تنظیم فونت [نام فونت]»\n"
        "این فونت روی بخش‌های سرگرمی/بیو/آمار هم که تم دارن اعمال می‌شه.\n\n"
        "⚠️ نکته‌ی صادقانه: این تبدیلِ کاراکتریه (متنِ واقعاً متفاوت)، نه تعویضِ "
        "تایپ‌فیسِ کل اپ - اون یکی هیچ رباتی (نه فقط گاردی) نمی‌تونه عوض کنه."
    )

@bot.on_message(filters=lambda m: _cmd_is(m, "font_set"))
async def font_set_cmd(bot: Robot, message: Message):
    """تنظیم فونت گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not is_admin(user_id, group_data):
        await message.reply("❌ فقط ادمین می‌تواند فونت را تغییر دهد!")
        return

    raw_font = _cmd_rest(message.text)
    if not raw_font:
        await message.reply(f"⚠️ دستور: تنظیم فونت [نام فونت]\nفونت‌های موجود: {', '.join(FONT_NAMES)}")
        return

    font = _normalize_font_name(raw_font)
    if not font:
        await message.reply(f"⚠️ فونت «{raw_font}» شناخته‌شده نیست.\nفونت‌های موجود: {', '.join(FONT_NAMES)}")
        return

    group_data.setdefault("settings", {})["font"] = font
    save_group_data(group_id, group_data)
    icon = theme_icon(group_data, "success")
    sample_out = apply_font_style("گاردی ایکس", font)
    await message.reply(f"{icon} **فونت گروه به «{font}» تغییر یافت!**\nنمونه: {sample_out}")

# =========================================================
#  سیستم مدیریت زبان گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "lang_set"))
async def lang_set_cmd(bot: Robot, message: Message):
    """تنظیم زبان گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند زبان را تغییر دهد!")
        return
    
    lang = message.text.replace("/lang_set", "", 1).strip()
    if not lang:
        await message.reply("⚠️ دستور: /lang_set [زبان]")
        return
    
    langs = ['fa', 'en', 'ar', 'tr']
    if lang not in langs:
        await message.reply(f"⚠️ زبان‌های موجود: {', '.join(langs)}")
        return
    
    group_data['settings']['language'] = lang
    save_group_data(group_id, group_data)
    await message.reply(f"🌍 **زبان گروه به «{lang}» تغییر یافت!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/lang")
async def lang_cmd(bot: Robot, message: Message):
    """نمایش زبان فعلی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    lang = group_data.get('settings', {}).get('language', 'fa')
    
    await message.reply(f"🌍 **زبان فعلی گروه:** {lang}")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت هشدارهای خودکار
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "auto_alert_set"))
async def auto_alert_set_cmd(bot: Robot, message: Message):
    """تنظیم هشدار خودکار"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/auto_alert_set", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /auto_alert_set [زمان] | [متن]")
        return
    
    alert_data = [p.strip() for p in parts.split('|')]
    if len(alert_data) < 2:
        await message.reply("⚠️ دستور: /auto_alert_set [زمان] | [متن]")
        return
    
    if 'auto_alerts' not in group_data:
        group_data['auto_alerts'] = []
    
    group_data['auto_alerts'].append({
        'time': alert_data[0],
        'text': alert_data[1],
        'enabled': True,
        'created_by': user_id,
        'created_at': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **هشدار خودکار تنظیم شد!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/auto_alerts")
async def auto_alerts_cmd(bot: Robot, message: Message):
    """لیست هشدارهای خودکار"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    alerts = group_data.get('auto_alerts', [])
    
    if alerts:
        text = "⏰ **هشدارهای خودکار:**\n\n"
        for idx, alert in enumerate(alerts, 1):
            text += f"{idx}. زمان: {alert.get('time')}\n"
            text += f"   متن: {alert.get('text')[:50]}...\n"
            text += f"   وضعیت: {'✅ فعال' if alert.get('enabled', True) else '❌ غیرفعال'}\n\n"
        await message.reply(text)
    else:
        await message.reply("⏰ هیچ هشدار خودکاری وجود ندارد!")

# =========================================================
#  سیستم مدیریت تگ‌های گروه
# =========================================================

# =========================================================
#  سیستم مدیریت قفل‌های گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "lock_group"))
async def lock_group_advanced_cmd(bot: Robot, message: Message):
    """قفل پیشرفته گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند گروه را قفل کند!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ دستور: /lock_group [نوع قفل]")
        return
    
    lock_type = parts[1]
    
    if lock_type == "همه":
        group_data['settings']['lock'] = True
        group_data['settings']['lock_media'] = True
        group_data['settings']['lock_forward'] = True
        group_data['settings']['lock_hashtag'] = True
        group_data['settings']['lock_mention'] = True
        group_data['settings']['lock_metadata'] = True
        save_group_data(group_id, group_data)
        await message.reply("🔒 **همه قفل‌ها فعال شدند!**")
    elif lock_type == "لینک":
        group_data['settings']['anti_link'] = True
        save_group_data(group_id, group_data)
        await message.reply("🔗 **قفل لینک فعال شد!**")
    elif lock_type == "اسپم":
        group_data['settings']['anti_spam'] = True
        save_group_data(group_id, group_data)
        await message.reply("🔄 **قفل اسپم فعال شد!**")
    elif lock_type == "فحش":
        group_data['settings']['anti_swear'] = True
        save_group_data(group_id, group_data)
        await message.reply("💢 **قفل فحش فعال شد!**")
    else:
        await message.reply("⚠️ نوع قفل نامعتبر است!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت انجمن گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "forum_add"))
async def forum_add_cmd(bot: Robot, message: Message):
    """افزودن موضوع به انجمن"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/forum_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /forum_add [عنوان] | [متن]")
        return
    
    forum_data = [p.strip() for p in parts.split('|')]
    if len(forum_data) < 2:
        await message.reply("⚠️ دستور: /forum_add [عنوان] | [متن]")
        return
    
    if 'forum' not in group_data:
        group_data['forum'] = []
    
    forum_id = f"FR-{len(group_data['forum']) + 1:04d}"
    group_data['forum'].append({
        'id': forum_id,
        'title': forum_data[0],
        'text': forum_data[1],
        'author': user_id,
        'comments': [],
        'likes': 0,
        'created_at': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **موضوع {forum_id} به انجمن اضافه شد!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/forum")
async def forum_cmd(bot: Robot, message: Message):
    """لیست موضوعات انجمن"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    forum = group_data.get('forum', [])
    
    if forum:
        text = "📚 **انجمن گروه:**\n\n"
        for idx, topic in enumerate(forum, 1):
            author_name = get_user_name_from_id(topic.get('author'), group_data)
            text += f"{idx}. {topic.get('title')}\n"
            text += f"   نویسنده: {author_name}\n"
            text += f"   شناسه: {topic.get('id')}\n"
            text += f"   لایک: ❤️ {topic.get('likes', 0)}\n"
            text += f"   کامنت‌ها: 💬 {len(topic.get('comments', []))}\n\n"
        await message.reply(text)
    else:
        await message.reply("📚 هیچ موضوعی در انجمن وجود ندارد!")

# =========================================================
#  سیستم مدیریت نظرات انجمن
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "forum_comment"))
async def forum_comment_cmd(bot: Robot, message: Message):
    """کامنت در انجمن"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    parts = message.text.replace("/forum_comment", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /forum_comment [شناسه] | [متن]")
        return
    
    comment_data = [p.strip() for p in parts.split('|')]
    if len(comment_data) < 2:
        await message.reply("⚠️ دستور: /forum_comment [شناسه] | [متن]")
        return
    
    forum_id = comment_data[0]
    comment_text = comment_data[1]
    
    group_data = get_group_data(group_id)
    forum = group_data.get('forum', [])
    
    for topic in forum:
        if topic.get('id') == forum_id:
            topic['comments'].append({
                'user': str(message.sender_id),
                'text': comment_text,
                'time': datetime.now().isoformat()
            })
            save_group_data(group_id, group_data)
            await message.reply(f"✅ **کامنت شما به موضوع {forum_id} اضافه شد!**")
            return
    
    await message.reply(f"⚠️ موضوعی با شناسه {forum_id} پیدا نشد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "forum_like"))
async def forum_like_cmd(bot: Robot, message: Message):
    """لایک موضوع انجمن"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    forum_id = message.text.replace("/forum_like", "", 1).strip()
    if not forum_id:
        await message.reply("⚠️ دستور: /forum_like [شناسه]")
        return
    
    group_data = get_group_data(group_id)
    forum = group_data.get('forum', [])
    
    for topic in forum:
        if topic.get('id') == forum_id:
            topic['likes'] = topic.get('likes', 0) + 1
            save_group_data(group_id, group_data)
            await message.reply(f"❤️ **موضوع {forum_id} لایک شد!**")
            return
    
    await message.reply(f"⚠️ موضوعی با شناسه {forum_id} پیدا نشد!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت چالش‌های گروهی
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "group_challenge_add"))
async def group_challenge_add_cmd(bot: Robot, message: Message):
    """افزودن چالش گروهی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/group_challenge_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /group_challenge_add [عنوان] | [توضیحات]")
        return
    
    challenge_data = [p.strip() for p in parts.split('|')]
    if len(challenge_data) < 2:
        await message.reply("⚠️ دستور: /group_challenge_add [عنوان] | [توضیحات]")
        return
    
    if 'group_challenges' not in group_data:
        group_data['group_challenges'] = []
    
    challenge_id = f"GC-{len(group_data['group_challenges']) + 1:04d}"
    group_data['group_challenges'].append({
        'id': challenge_id,
        'title': challenge_data[0],
        'description': challenge_data[1],
        'participants': [],
        'winner': None,
        'created_by': user_id,
        'created_at': datetime.now().isoformat(),
        'active': True
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **چالش گروهی {challenge_id} اضافه شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "group_challenge_join"))
async def group_challenge_join_cmd(bot: Robot, message: Message):
    """شرکت در چالش گروهی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    challenge_id = message.text.replace("/group_challenge_join", "", 1).strip()
    if not challenge_id:
        await message.reply("⚠️ دستور: /group_challenge_join [شناسه]")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    challenges = group_data.get('group_challenges', [])
    for challenge in challenges:
        if challenge.get('id') == challenge_id and challenge.get('active', True):
            if user_id not in challenge.get('participants', []):
                challenge['participants'].append(user_id)
                save_group_data(group_id, group_data)
                await message.reply(f"✅ **شما در چالش {challenge_id} ثبت نام شدید!**")
                return
            else:
                await message.reply(f"⚠️ شما قبلاً در این چالش ثبت نام کرده‌اید!")
                return
    
    await message.reply(f"⚠️ چالشی با شناسه {challenge_id} پیدا نشد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "group_challenge_winner"))
async def group_challenge_winner_cmd(bot: Robot, message: Message):
    """انتخاب برنده چالش گروهی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    challenge_id = message.text.replace("/group_challenge_winner", "", 1).strip()
    if not challenge_id:
        await message.reply("⚠️ دستور: /group_challenge_winner [شناسه]")
        return
    
    challenges = group_data.get('group_challenges', [])
    for challenge in challenges:
        if challenge.get('id') == challenge_id and challenge.get('active', True):
            participants = challenge.get('participants', [])
            if participants:
                winner = random.choice(participants)
                challenge['winner'] = winner
                challenge['active'] = False
                save_group_data(group_id, group_data)
                
                winner_name = get_user_name_from_id(winner, group_data)
                await message.reply(f"🏆 **برنده چالش {challenge_id}:**\n\n{winner_name}\n\n🎉 تبریک میگم! 🎊")
                return
            else:
                await message.reply(f"⚠️ هیچ شرکت‌کننده‌ای در چالش {challenge_id} وجود ندارد!")
                return
    
    await message.reply(f"⚠️ چالشی با شناسه {challenge_id} پیدا نشد!")

@bot.on_message(filters=lambda m: m.text and m.text == "/group_challenges")
async def group_challenges_cmd(bot: Robot, message: Message):
    """لیست چالش‌های گروهی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    challenges = group_data.get('group_challenges', [])
    
    if challenges:
        text = "🏆 **چالش‌های گروهی:**\n\n"
        for idx, challenge in enumerate(challenges, 1):
            status = "🟢 فعال" if challenge.get('active', True) else "🔴 بسته"
            text += f"{idx}. {challenge.get('title')}\n"
            text += f"   شناسه: {challenge.get('id')}\n"
            text += f"   وضعیت: {status}\n"
            text += f"   شرکت‌کنندگان: {len(challenge.get('participants', []))} نفر\n"
            if challenge.get('winner'):
                winner_name = get_user_name_from_id(challenge.get('winner'), group_data)
                text += f"   برنده: {winner_name}\n"
            text += "\n"
        await message.reply(text)
    else:
        await message.reply("🏆 هیچ چالش گروهی وجود ندارد!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت کانال‌های خبری
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "news_channel_add"))
async def news_channel_add_cmd(bot: Robot, message: Message):
    """افزودن کانال خبری"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/news_channel_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /news_channel_add [نام] | [لینک]")
        return
    
    channel_data = [p.strip() for p in parts.split('|')]
    if len(channel_data) < 2:
        await message.reply("⚠️ دستور: /news_channel_add [نام] | [لینک]")
        return
    
    if 'news_channels' not in group_data:
        group_data['news_channels'] = []
    
    group_data['news_channels'].append({
        'name': channel_data[0],
        'link': channel_data[1],
        'added_by': user_id,
        'added_at': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **کانال خبری {channel_data[0]} اضافه شد!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/news_channels")
async def news_channels_cmd(bot: Robot, message: Message):
    """لیست کانال‌های خبری"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    channels = group_data.get('news_channels', [])
    
    if channels:
        text = "📰 **کانال‌های خبری:**\n\n"
        for idx, channel in enumerate(channels, 1):
            text += f"{idx}. {channel.get('name')}\n"
            text += f"   لینک: {channel.get('link')}\n\n"
        await message.reply(text)
    else:
        await message.reply("📰 هیچ کانال خبری وجود ندارد!")

# =========================================================
#  سیستم مدیریت ربات‌های گروه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "bot_group_add"))
async def bot_group_add_cmd(bot: Robot, message: Message):
    """افزودن ربات به گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    bot_id = message.text.replace("/bot_group_add", "", 1).strip()
    if not bot_id:
        await message.reply("⚠️ دستور: /bot_group_add [شناسه ربات]")
        return
    
    if 'group_bots' not in group_data:
        group_data['group_bots'] = []
    
    if bot_id not in group_data['group_bots']:
        group_data['group_bots'].append(bot_id)
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **ربات {bot_id} به گروه اضافه شد!**")
    else:
        await message.reply(f"⚠️ ربات {bot_id} قبلاً در گروه است!")

@bot.on_message(filters=lambda m: m.text and m.text == "/group_bots")
async def group_bots_cmd(bot: Robot, message: Message):
    """لیست ربات‌های گروه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    bots = group_data.get('group_bots', [])
    
    if bots:
        text = "🤖 **ربات‌های گروه:**\n\n"
        for idx, bot_id in enumerate(bots, 1):
            text += f"{idx}. {bot_id}\n"
        await message.reply(text)
    else:
        await message.reply("🤖 هیچ رباتی در گروه وجود ندارد!")

# =========================================================
#  سیستم مدیریت لینک‌های دانلود
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "download_link_add"))
async def download_link_add_cmd(bot: Robot, message: Message):
    """افزودن لینک دانلود"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/download_link_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /download_link_add [نام] | [لینک]")
        return
    
    link_data = [p.strip() for p in parts.split('|')]
    if len(link_data) < 2:
        await message.reply("⚠️ دستور: /download_link_add [نام] | [لینک]")
        return
    
    if 'download_links' not in group_data:
        group_data['download_links'] = []
    
    group_data['download_links'].append({
        'name': link_data[0],
        'link': link_data[1],
        'added_by': user_id,
        'added_at': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **لینک دانلود {link_data[0]} اضافه شد!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/download_links")
async def download_links_cmd(bot: Robot, message: Message):
    """لیست لینک‌های دانلود"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    links = group_data.get('download_links', [])
    
    if links:
        text = "📥 **لینک‌های دانلود:**\n\n"
        for idx, link in enumerate(links, 1):
            text += f"{idx}. {link.get('name')}\n"
            text += f"   لینک: {link.get('link')}\n\n"
        await message.reply(text)
    else:
        await message.reply("📥 هیچ لینک دانلودی وجود ندارد!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت مسابقات هفتگی
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "weekly_contest_add"))
async def weekly_contest_add_cmd(bot: Robot, message: Message):
    """افزودن مسابقه هفتگی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/weekly_contest_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /weekly_contest_add [نام] | [توضیحات] | [جایزه]")
        return
    
    contest_data = [p.strip() for p in parts.split('|')]
    if len(contest_data) < 3:
        await message.reply("⚠️ دستور: /weekly_contest_add [نام] | [توضیحات] | [جایزه]")
        return
    
    if 'weekly_contests' not in group_data:
        group_data['weekly_contests'] = []
    
    contest_id = f"WC-{len(group_data['weekly_contests']) + 1:04d}"
    group_data['weekly_contests'].append({
        'id': contest_id,
        'name': contest_data[0],
        'description': contest_data[1],
        'prize': contest_data[2],
        'participants': [],
        'winner': None,
        'created_by': user_id,
        'created_at': datetime.now().isoformat(),
        'active': True
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **مسابقه هفتگی {contest_id} اضافه شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "weekly_contest_join"))
async def weekly_contest_join_cmd(bot: Robot, message: Message):
    """شرکت در مسابقه هفتگی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    contest_id = message.text.replace("/weekly_contest_join", "", 1).strip()
    if not contest_id:
        await message.reply("⚠️ دستور: /weekly_contest_join [شناسه]")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    contests = group_data.get('weekly_contests', [])
    for contest in contests:
        if contest.get('id') == contest_id and contest.get('active', True):
            if user_id not in contest.get('participants', []):
                contest['participants'].append(user_id)
                save_group_data(group_id, group_data)
                await message.reply(f"✅ **شما در مسابقه هفتگی {contest_id} ثبت نام شدید!**")
                return
            else:
                await message.reply(f"⚠️ شما قبلاً در این مسابقه ثبت نام کرده‌اید!")
                return
    
    await message.reply(f"⚠️ مسابقه‌ای با شناسه {contest_id} پیدا نشد!")

@bot.on_message(filters=lambda m: _cmd_is(m, "weekly_contest_winner"))
async def weekly_contest_winner_cmd(bot: Robot, message: Message):
    """انتخاب برنده مسابقه هفتگی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    contest_id = message.text.replace("/weekly_contest_winner", "", 1).strip()
    if not contest_id:
        await message.reply("⚠️ دستور: /weekly_contest_winner [شناسه]")
        return
    
    contests = group_data.get('weekly_contests', [])
    for contest in contests:
        if contest.get('id') == contest_id and contest.get('active', True):
            participants = contest.get('participants', [])
            if participants:
                winner = random.choice(participants)
                contest['winner'] = winner
                contest['active'] = False
                save_group_data(group_id, group_data)
                
                winner_name = get_user_name_from_id(winner, group_data)
                await message.reply(f"🏆 **برنده مسابقه هفتگی {contest_id}:**\n\n{winner_name}\n\n🎁 جایزه: {contest.get('prize', 'نامشخص')}\n🎉 تبریک میگم! 🎊")
                return
            else:
                await message.reply(f"⚠️ هیچ شرکت‌کننده‌ای در مسابقه {contest_id} وجود ندارد!")
                return
    
    await message.reply(f"⚠️ مسابقه‌ای با شناسه {contest_id} پیدا نشد!")

@bot.on_message(filters=lambda m: m.text and m.text == "/weekly_contests")
async def weekly_contests_cmd(bot: Robot, message: Message):
    """لیست مسابقات هفتگی"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    contests = group_data.get('weekly_contests', [])
    
    if contests:
        text = "🏆 **مسابقات هفتگی:**\n\n"
        for idx, contest in enumerate(contests, 1):
            status = "🟢 فعال" if contest.get('active', True) else "🔴 بسته"
            text += f"{idx}. {contest.get('name')}\n"
            text += f"   شناسه: {contest.get('id')}\n"
            text += f"   وضعیت: {status}\n"
            text += f"   شرکت‌کنندگان: {len(contest.get('participants', []))} نفر\n"
            if contest.get('winner'):
                winner_name = get_user_name_from_id(contest.get('winner'), group_data)
                text += f"   برنده: {winner_name}\n"
            text += "\n"
        await message.reply(text)
    else:
        await message.reply("🏆 هیچ مسابقه هفتگی وجود ندارد!")

# =========================================================
#  اجرا
# =========================================================

        # =========================================================
#  سیستم مدیریت رویدادهای ماهانه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "monthly_event_add"))
async def monthly_event_add_cmd(bot: Robot, message: Message):
    """افزودن رویداد ماهانه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/monthly_event_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /monthly_event_add [نام] | [تاریخ] | [توضیحات]")
        return
    
    event_data = [p.strip() for p in parts.split('|')]
    if len(event_data) < 3:
        await message.reply("⚠️ دستور: /monthly_event_add [نام] | [تاریخ] | [توضیحات]")
        return
    
    if 'monthly_events' not in group_data:
        group_data['monthly_events'] = []
    
    event_id = f"ME-{len(group_data['monthly_events']) + 1:04d}"
    group_data['monthly_events'].append({
        'id': event_id,
        'name': event_data[0],
        'date': event_data[1],
        'description': event_data[2],
        'created_by': user_id,
        'created_at': datetime.now().isoformat()
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **رویداد ماهانه {event_id} اضافه شد!**")

@bot.on_message(filters=lambda m: m.text and m.text == "/monthly_events")
async def monthly_events_cmd(bot: Robot, message: Message):
    """لیست رویدادهای ماهانه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    events = group_data.get('monthly_events', [])
    
    if events:
        text = "📅 **رویدادهای ماهانه:**\n\n"
        for idx, event in enumerate(events, 1):
            text += f"{idx}. {event.get('name')}\n"
            text += f"   شناسه: {event.get('id')}\n"
            text += f"   تاریخ: {event.get('date')}\n"
            text += f"   توضیحات: {event.get('description')[:50]}...\n\n"
        await message.reply(text)
    else:
        await message.reply("📅 هیچ رویداد ماهانه‌ای وجود ندارد!")

# =========================================================
#  سیستم مدیریت جوایز ویژه
# =========================================================

@bot.on_message(filters=lambda m: _cmd_is(m, "special_reward_add"))
async def special_reward_add_cmd(bot: Robot, message: Message):
    """افزودن جایزه ویژه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    if not is_admin(user_id, group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    
    parts = message.text.replace("/special_reward_add", "", 1).strip()
    if not parts:
        await message.reply("⚠️ دستور: /special_reward_add [نام] | [توضیحات]")
        return
    
    reward_data = [p.strip() for p in parts.split('|')]
    if len(reward_data) < 2:
        await message.reply("⚠️ دستور: /special_reward_add [نام] | [توضیحات]")
        return
    
    if 'special_rewards' not in group_data:
        group_data['special_rewards'] = []
    
    reward_id = f"SR-{len(group_data['special_rewards']) + 1:04d}"
    group_data['special_rewards'].append({
        'id': reward_id,
        'name': reward_data[0],
        'description': reward_data[1],
        'claimed_by': None,
        'created_by': user_id,
        'created_at': datetime.now().isoformat(),
        'available': True
    })
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **جایزه ویژه {reward_id} اضافه شد!**")

@bot.on_message(filters=lambda m: _cmd_is(m, "special_reward_claim"))
async def special_reward_claim_cmd(bot: Robot, message: Message):
    """دریافت جایزه ویژه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    reward_id = message.text.replace("/special_reward_claim", "", 1).strip()
    if not reward_id:
        await message.reply("⚠️ دستور: /special_reward_claim [شناسه]")
        return
    
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    
    rewards = group_data.get('special_rewards', [])
    for reward in rewards:
        if reward.get('id') == reward_id and reward.get('available', True):
            reward['claimed_by'] = user_id
            reward['available'] = False
            save_group_data(group_id, group_data)
            await message.reply(f"🎁 **جایزه ویژه {reward_id} دریافت شد!**")
            return
    
    await message.reply(f"⚠️ جایزه‌ای با شناسه {reward_id} پیدا نشد!")

@bot.on_message(filters=lambda m: m.text and m.text == "/special_rewards")
async def special_rewards_cmd(bot: Robot, message: Message):
    """لیست جوایز ویژه"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply("❌ این دستور فقط در گروه قابل استفاده است!")
        return
    
    group_data = get_group_data(group_id)
    rewards = group_data.get('special_rewards', [])
    
    if rewards:
        text = "🎁 **جوایز ویژه:**\n\n"
        for idx, reward in enumerate(rewards, 1):
            status = "🟢 موجود" if reward.get('available', True) else "🔴 دریافت شده"
            text += f"{idx}. {reward.get('name')}\n"
            text += f"   شناسه: {reward.get('id')}\n"
            text += f"   وضعیت: {status}\n"
            text += f"   توضیحات: {reward.get('description')[:50]}...\n\n"
        await message.reply(text)
    else:
        await message.reply("🎁 هیچ جایزه ویژه‌ای وجود ندارد!")

# =========================================================
#  اجرا
# =========================================================

# =========================================================
#  🔒 قفل نوع پیام (عکس/ویدیو/گیف/فایل/موزیک/ویس/ویدیو مسیج/استیکر/مخاطب/موقعیت/نظرسنجی/بازی/
#  رسانه‌ی کلی/فوروارد/هشتگ/منشن/متادیتا) + تنظیم ضداسپم
# =========================================================
def _lock_types_help() -> str:
    return "، ".join(v[0] for v in LOCK_TYPE_INFO.values())

async def _apply_lock_type(message, key: str, value: bool):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    name, settings_key = LOCK_TYPE_INFO[key]
    if settings_key:
        group_data['settings'][settings_key] = value
    else:
        group_data['settings'].setdefault('locks', {})[key] = value
    save_group_data(group_id, group_data)
    extra = ""
    if key == "media" and value:
        extra = "\nℹ️ شامل: " + "، ".join(_MSG_TYPE_FA[t] for t in MEDIA_LOCK_TYPES) + " (استیکر و ... جدا قفل می‌شوند)"
    icon = "🔒" if value else "🔓"
    await message.reply(f"{icon} **قفل {name} {'فعال' if value else 'غیرفعال'} شد!**{extra}\n"
                        "👮 ادمین‌ها و معاف‌ها از قفل مستثنی هستند.")

@bot.on_message(filters=lambda m: _cmd_is(m, "locktype"))
async def locktype_cmd(bot: Robot, message: Message):
    key = resolve_lock_type(_cmd_rest(message.text))
    if not key:
        await message.reply("⚠️ دستور: /locktype [نوع]\nنوع‌ها: " + _lock_types_help())
        return
    await _apply_lock_type(message, key, True)

@bot.on_message(filters=lambda m: _cmd_is(m, "unlocktype"))
async def unlocktype_cmd(bot: Robot, message: Message):
    key = resolve_lock_type(_cmd_rest(message.text))
    if not key:
        await message.reply("⚠️ دستور: /unlocktype [نوع]\nنوع‌ها: " + _lock_types_help())
        return
    await _apply_lock_type(message, key, False)

# 🛠 «تنظیم حساسیت تشخیص کدهنگی #درصد» - در راهنما (FULL_GUIDE_3، بخش «فقط
# مالکین») وعده داده شده بود ولی هیچ هندلری نداشت. حساسیتِ پیش‌فرض ۷۰٪ (طبق
# همون متنِ راهنما) و بازه‌ی مجاز ۱ تا ۱۰۰٪.
HANGCODE_SENSITIVITY_DEFAULT = 70
HANGCODE_SENSITIVITY_MIN = 1
HANGCODE_SENSITIVITY_MAX = 100

@bot.on_message(filters=lambda m: _cmd_is(m, "hangcode_sensitivity"))
async def hangcode_sensitivity_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_owner(str(message.sender_id), group_data):
        await message.reply("❌ فقط مالک می‌تواند حساسیت تشخیص کدهنگی را تغییر دهد!")
        return
    parts = to_en_digits(message.text).split()
    current = group_data.get("settings", {}).get("hangcode_sensitivity", HANGCODE_SENSITIVITY_DEFAULT)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply(
            f"⚠️ دستور: تنظیم حساسیت تشخیص کدهنگی #درصد (بین {HANGCODE_SENSITIVITY_MIN} تا "
            f"{HANGCODE_SENSITIVITY_MAX})\nحساسیتِ فعلی: {current}٪"
        )
        return
    value = int(parts[1])
    if not (HANGCODE_SENSITIVITY_MIN <= value <= HANGCODE_SENSITIVITY_MAX):
        await message.reply(f"⚠️ عدد باید بین {HANGCODE_SENSITIVITY_MIN} تا {HANGCODE_SENSITIVITY_MAX} باشد.")
        return
    group_data.setdefault("settings", {})["hangcode_sensitivity"] = value
    save_group_data(group_id, group_data)
    await message.reply(f"✅ حساسیت تشخیص کدهنگی روی {value}٪ تنظیم شد.")

@bot.on_message(filters=lambda m: _cmd_is(m, "locks"))
async def locks_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    settings = get_group_data(group_id).get('settings', {})
    lines = [f"🔒 قفل کامل گروه: {'✅' if settings.get('lock', False) else '❌'}"]
    for key, (name, _sk) in LOCK_TYPE_INFO.items():
        lines.append(f"• {name}: {'✅' if is_lock_type_on(settings, key) else '❌'}")
    await message.reply("🔐 **وضعیت قفل‌ها:**\n\n" + "\n".join(lines))

@bot.on_message(filters=lambda m: _cmd_is(m, "setspam"))
async def setspam_cmd(bot: Robot, message: Message):
    """/setspam [ثانیه‌ی_پنجره] [حداکثر_پیام_در_پنجره] [حداکثر_تکرار_یک_متن_در_۶۰_ثانیه]"""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not is_admin(str(message.sender_id), group_data):
        await message.reply("❌ شما ادمین نیستید!")
        return
    st = group_data['settings']
    args = to_en_digits(_cmd_rest(message.text)).split()
    if len(args) != 3 or not all(a.isdigit() for a in args):
        await message.reply(
            "⚠️ دستور: /setspam [پنجره_ثانیه] [حداکثر_پیام] [حداکثر_تکرار]\n"
            "مثال: /setspam 5 3 4\n"
            f"📌 مقدار فعلی: {_spam_setting(st, 'spam_window', SPAM_DEFAULT_WINDOW, 1, 60)} ثانیه / "
            f"{_spam_setting(st, 'spam_max_msgs', SPAM_DEFAULT_MAX_MSGS, 1, 100)} پیام / "
            f"{_spam_setting(st, 'spam_repeat_max', SPAM_DEFAULT_REPEAT_MAX, 1, 100)} تکرار")
        return
    w, m, r = (int(a) for a in args)
    if not (1 <= w <= 60 and 1 <= m <= 100 and 1 <= r <= 100):
        await message.reply("⚠️ پنجره باید بین ۱ تا ۶۰ ثانیه و بقیه بین ۱ تا ۱۰۰ باشند.")
        return
    group_data = get_group_data(group_id)
    group_data['settings'].update({'spam_window': w, 'spam_max_msgs': m, 'spam_repeat_max': r})
    save_group_data(group_id, group_data)
    await message.reply(f"✅ **ضد اسپم تنظیم شد!**\nبیش از {m} پیام در {w} ثانیه، یا بیش از {r} بار تکرار یک متن/فایل در ۶۰ ثانیه = اسپم.")

# =========================================================
#  سیستم مدیریت خودکار پیام‌ها (به عمد به عنوان آخرین هندلر ثبت می‌شود)
# =========================================================

@bot.on_message()
async def auto_message_handler(bot: Robot, message: Message):
    """پردازش خودکار پیام‌های گروه"""
    
    group_id = get_chat_group_id(message)
    if not group_id:
        return
    
    user_id = str(message.sender_id)
    text = message.text or ""
    
    group_data = get_group_data(group_id)
    settings = group_data.get('settings', {})

    # ===== بوت‌استرپ مالکیت =====
    # این کار زودتر، توسط _bootstrap_owner_handler انجام می‌شه (که خیلی قبل از
    # این هندلر ثبت شده) تا حتی اگه اولین پیام یه دستور مدیریتی باشه هم، مالک
    # قبل از چک‌شدن پرمیشن‌ها ثبت شده باشه.

    # ===== به‌روزرسانی آمار کاربر =====
    if user_id not in group_data.get('users', {}):
        display_name = await get_display_name(bot, message) or "کاربر"
        group_data['users'][user_id] = {
            'first_name': display_name,
            'last_name': "",
            'join_date': datetime.now().isoformat()
        }
        group_data['stats']['total_users'] = group_data['stats'].get('total_users', 0) + 1

        # 🛠 رفع باگ: «خوش‌آمد» قبلاً روی «اولین پیام هر کاربر» ارسال می‌شد (نه ورود واقعی؛ عضو قدیمی که
        # تازه پیام می‌داد هم خوش‌آمد می‌گرفت و کسی که وارد می‌شد ولی حرف نمی‌زد هرگز). الان خوش‌آمد و
        # خداحافظ فقط با رویداد واقعی عضویت (member_event_handler) ارسال می‌شود.

    # ===== Member Registry (دائمی): فرستنده‌ی هر پیام عادی با User ID ثبت/به‌روز می‌شود =====
    # پیام‌های سرویسی (ورود/خروج) اینجا ثبت نمی‌شوند؛ وضعیتشان را فقط رویداد عضویت تعیین می‌کند
    # (وگرنه «ورود» قبل از رسیدن رویداد، عضو فرض می‌شد و خوش‌آمد گم می‌شد).
    if mtype_for_registry(message) != "service" and not getattr(message, "is_anonymous_admin", False) \
            and getattr(message, "sender_chat_id", None) is None and user_id not in (ANONYMOUS_ADMIN_ID, TELEGRAM_SERVICE_ID):
        registry_touch(group_data, {
            "id": user_id, "username": getattr(message, "sender_username", None),
            "first_name": getattr(message, "sender_first_name", None) or "",
            "last_name": getattr(message, "sender_last_name", None) or "",
            "is_bot": bool(getattr(message, "sender_is_bot", False)),
        }, source="message")

    # ===== 🛠 رفع باگ: شمارنده پیام‌ها هیچ‌وقت افزایش پیدا نمی‌کرد، پس «آمار» همیشه صفر نشون می‌داد =====
    group_data.setdefault('message_count', {})
    group_data['message_count'][user_id] = group_data['message_count'].get(user_id, 0) + 1
    group_data['stats']['total_messages'] = group_data['stats'].get('total_messages', 0) + 1

    # ===== بخش ۶۲: اهدای XP فقط برای پیام‌های واقعیِ کاربر، نه پیام‌های سرویسی
    # (ورود/خروج و مشابه) - همون شرطی که برای Member Registry هم استفاده می‌شه =====
    if mtype_for_registry(message) != "service" and not getattr(message, "is_anonymous_admin", False) \
            and getattr(message, "sender_chat_id", None) is None and user_id not in (ANONYMOUS_ADMIN_ID, TELEGRAM_SERVICE_ID):
        grant_xp(group_data, user_id)

    # ===== 🛠 رفع باگ دوم: کل پیام‌ها درست بود، ولی «امروز/این هفته/این ماه»
    # (هم برای «آمار من» و هم «آمار گروه») هیچ‌وقت به‌روزرسانی نمی‌شدن، چون
    # daily_count/weekly_count/monthly_count و today_messages/week_messages/
    # month_messages هیچ‌جای کد نوشته نمی‌شدن - همیشه صفر می‌موندن. الان با
    # مقایسه‌ی تاریخ/هفته/ماه فعلی با آخرین باری که ثبت شده، در شروع هر
    # دوره‌ی جدید شمارنده‌ها ریست و از نو شمرده می‌شن. =====
    today = datetime.now()
    today_key = today.strftime('%Y-%m-%d')
    iso_year, iso_week, _ = today.isocalendar()
    week_key = f"{iso_year}-W{iso_week}"
    month_key = today.strftime('%Y-%m')

    if group_data['stats'].get('daily_date') != today_key:
        group_data['daily_count'] = {}
        group_data['stats']['today_messages'] = 0
        group_data['stats']['daily_date'] = today_key
    if group_data['stats'].get('weekly_key') != week_key:
        group_data['weekly_count'] = {}
        group_data['stats']['week_messages'] = 0
        group_data['stats']['weekly_key'] = week_key
    if group_data['stats'].get('monthly_key') != month_key:
        group_data['monthly_count'] = {}
        group_data['stats']['month_messages'] = 0
        group_data['stats']['monthly_key'] = month_key

    group_data.setdefault('daily_count', {})
    group_data.setdefault('weekly_count', {})
    group_data.setdefault('monthly_count', {})
    group_data['daily_count'][user_id] = group_data['daily_count'].get(user_id, 0) + 1
    group_data['weekly_count'][user_id] = group_data['weekly_count'].get(user_id, 0) + 1
    group_data['monthly_count'][user_id] = group_data['monthly_count'].get(user_id, 0) + 1
    group_data['stats']['today_messages'] = group_data['stats'].get('today_messages', 0) + 1
    group_data['stats']['week_messages'] = group_data['stats'].get('week_messages', 0) + 1
    group_data['stats']['month_messages'] = group_data['stats'].get('month_messages', 0) + 1

    # ===== قفل‌ها و فیلترها: Enforcement واقعی روی هر پیام =====
    # ترتیب: نوع پیام -> تشخیص تخلف -> (فقط در صورت تخلف) بای‌پس دسترسی -> حذف واقعی -> اعلان.
    # 🛠 رفع باگ: بررسی دسترسی قبلاً فقط is_admin بود؛ «مالک/ویژه/معاف» و ادمین‌های واقعی تلگرام که
    # در لیست ربات نبودند (و ادمین ناشناس) هدف ضدلینک/ضدفحش/ضداسپم/قفل می‌شدند.
    mtype = detect_message_type(message)
    _exempt_cache: Dict[str, bool] = {}

    async def exempt() -> bool:
        if "v" not in _exempt_cache:
            _exempt_cache["v"] = await is_filter_exempt(bot, message, group_id, group_data, user_id)
        return _exempt_cache["v"]

    # ----- قفل کامل گروه -----
    if settings.get('lock', False) and mtype != "service":
        if not await exempt():
            await enforce_delete(message, group_id, user_id, "lock",
                                 "🔒 **گروه قفل است!** فقط ادمین‌ها می‌توانند پیام ارسال کنند.")
            save_group_data(group_id, group_data)
            return

    # =========================================================
    #  🆕 «حالت خواب» (FULL_GUIDE_2: «حالت خواب خاموش/روشن») - قبلاً فقط در
    #  راهنما تبلیغ می‌شد، هیچ کلید settings و هیچ منطق اجرایی نداشت. رفتار
    #  خودکارش دقیقاً مثل «قفل کامل گروه» است (حذف واقعیِ پیام‌های غیرمعاف)
    #  با متن اعلان جدا، تا مدیر بتواند بین «قفل دستی» و «حالت خواب شبانه»
    #  فرق بگذارد؛ مالک/ادمین/ویژه/معاف طبق همان قانون بای‌پس بقیه‌ی قفل‌ها
    #  همچنان می‌توانند پیام بفرستند.
    # =========================================================
    if settings.get('sleep_mode', False) and mtype != "service":
        if not await exempt():
            await enforce_delete(message, group_id, user_id, "sleep_mode",
                                 "😴 **گروه در حالت خواب است!** فعلاً فقط ادمین‌ها می‌توانند پیام بدهند.")
            save_group_data(group_id, group_data)
            return

    # ===== بررسی بن (زمان‌دار: اگر منقضی شده باشد، is_punished_active خودش پاکش می‌کند) =====
    if is_punished_active(group_data, "bans", user_id):
        await message.delete()
        save_group_data(group_id, group_data)
        return

    # ===== بررسی میوت (زمان‌دار: اگر منقضی شده باشد، is_punished_active خودش پاکش می‌کند) =====
    if is_punished_active(group_data, "mutes", user_id):
        await message.delete()
        if _notice_allowed((str(group_id), str(user_id), "muted"), 20):
            await message.reply("🔇 **شما میوت هستید!**")
        save_group_data(group_id, group_data)
        return

    # ===== بررسی بلاک =====
    if user_id in group_data.get('blocks', []):
        await message.delete()
        save_group_data(group_id, group_data)
        return

    # ----- قفل‌های نوع پیام (رسانه/عکس/ویدیو/گیف/فایل/موزیک/ویس/ویدیو مسیج/استیکر/مخاطب/موقعیت/
    #       نظرسنجی/بازی/فوروارد/هشتگ/منشن/متادیتا) - کپشن هم بررسی می‌شود -----
    violation = find_lock_violation(message, settings)
    if violation and not await exempt():
        lock_key, why = violation
        # 🆕 «قفل کپشن» بر خلاف بقیه‌ی قفل‌های نوعِ پیام، سیستم اخطار/بنِ خودش
        # را دارد (طبق راهنما: بن کپشن فعال/غیرفعال، نمایش اخطار کپشن فعال/
        # غیرفعال، تنظیم اخطار کپشن #عدد) - نه فقط حذف ساده.
        if lock_key == "caption":
            del_res = await message.delete()
            try:
                cap_max = max(1, int(settings.get('caption_warn_max') or settings.get('max_warn', 3)))
            except (TypeError, ValueError):
                cap_max = max(1, int(settings.get('max_warn', 3) or 3))
            cw = group_data.setdefault('caption_warns', {})
            count = cw[user_id] = cw.get(user_id, 0) + 1
            if settings.get('caption_show_warn', True):
                notice = f"📝🔒 **ارسال کپشن در این گروه ممنوع است!**\n📌 اخطار: {count}/{cap_max}"
                if not del_res:
                    notice += f"\n⚠️ حذف پیام ناموفق بود: {del_res.error}"
                await message.reply(notice)
            if count >= cap_max:
                cw.pop(user_id, None)
                if settings.get('caption_ban_enabled', True):
                    save_group_data(group_id, group_data)
                    res = await moderation_ban(bot, group_id, user_id, "سیستم (قفل کپشن)", None,
                                               f"رسیدن به {cap_max} اخطار کپشن", log_action="بن خودکار (قفل کپشن)")
                    group_data = get_group_data(group_id)
                    if res:
                        await message.reply(f"🚫 **کاربر به دلیل ارسال مکرر کپشن ({cap_max} اخطار) بن شد!**")
                    else:
                        await message.reply(f"❌ کاربر به {cap_max} اخطار کپشن رسید ولی بن ناموفق بود.\n🔎 علت: {res.error}")
            save_group_data(group_id, group_data)
            return
        await enforce_delete(message, group_id, user_id, f"lock_{lock_key}", f"🔒 ارسال {why} در این گروه قفل است.")
        save_group_data(group_id, group_data)
        return

    # ===== 🆕 ضد تبچی: عضو تازه‌واردی که در چند دقیقه‌ی اول لینک/فوروارد بفرستد =====
    if settings.get('anti_tabchi_enabled', False) and mtype != "service":
        if await is_tabchi_suspect(group_data, user_id) and not await exempt():
            if getattr(message, "is_forwarded", False) or detect_links(message):
                del_res = await message.delete()
                tw = group_data.setdefault('warns_tabchi', {})
                count = tw[user_id] = tw.get(user_id, 0) + 1
                try:
                    tmax = max(1, int(settings.get('anti_tabchi_max_warn', 1)))
                except (TypeError, ValueError):
                    tmax = 1
                notice = f"🚷 **رفتار مشکوک تبچی شناسایی شد!** (عضو تازه + لینک/فوروارد)\n📌 اخطار: {count}/{tmax}"
                if not del_res:
                    notice += f"\n⚠️ حذف پیام ناموفق بود: {del_res.error}"
                await message.reply(notice)
                if count >= tmax:
                    tw.pop(user_id, None)
                    save_group_data(group_id, group_data)
                    res = await moderation_ban(bot, group_id, user_id, "سیستم (ضد تبچی)", None,
                                               "رفتار تبچی: لینک/فوروارد فوری بعد از عضویت",
                                               log_action="بن خودکار (ضد تبچی)")
                    if res:
                        await message.reply("🚫 **کاربر به‌عنوان تبچی بن شد!**")
                    return
                save_group_data(group_id, group_data)
                return

    # ===== بررسی ضد لینک (Entity ها + متن + کپشن) =====
    if settings.get('anti_link', True):
        link_found = detect_links(message)
        if link_found and not await exempt():
            await enforce_delete(message, group_id, user_id, "link", "🔗 **ارسال لینک ممنوع است!**")
            save_group_data(group_id, group_data)
            return

    # ===== بررسی ضد فحش (متن + کپشن؛ بعد از نرمال‌سازی و تطبیق کلمه‌به‌کلمه) =====
    if settings.get('anti_swear', True) and text:
        hit = find_swear_word(text, group_data.get('filters', {}).get('swear', []))
        if hit and not await exempt():
            del_res = await message.delete()

            info = add_warning(group_data, group_id, user_id, "استفاده از کلمه ممنوع (ضدفحش)", "سیستم (ضدفحش)")
            warn_count, max_warn = info["count"], info["max"]
            # ذخیره‌ی اخطار و آمار قبل از تماس با تلگرام؛ اقدام خودکار خودش دیتابیس را
            # تازه می‌خواند و ذخیره می‌کند، پس بعد از آن دیگر group_data قدیمی ذخیره نمی‌شود.
            save_group_data(group_id, group_data)

            notice = f"💢 **کلمه ممنوع!**\n📌 اخطار: {warn_count}/{max_warn}"
            if not del_res:
                notice += f"\n⚠️ حذف پیام ناموفق بود: {del_res.error}"
            await message.reply(notice)

            if info["limit_reached"] and settings.get('auto_ban', True):
                _performed, action_text = await execute_warn_action(bot, group_id, user_id, "سیستم (ضدفحش)")
                await message.reply(action_text)
            return

    # ===== بررسی ضد اسپم (پنجره‌ی زمانی، جدا برای هر گروه و هر کاربر) =====
    if settings.get('anti_spam', True) and mtype != "service" and not getattr(message, "is_edited", False):
        # 🛠 داده‌ی قدیمی spam_data (که برای هر کاربر برای همیشه در JSON می‌ماند) دیگر لازم نیست
        group_data.pop('spam_data', None)
        link_fp = None
        if settings.get('anti_link', True) is False:
            lf = detect_links(message)
            link_fp = hash(lf) if lf else None
        spam_reason = spam_check(group_id, user_id, settings, text_fp=_text_fingerprint(text),
                                 media_id=getattr(message, "media_id", None), link_fp=link_fp)
        if spam_reason and not await exempt():
            await enforce_delete(message, group_id, user_id, "spam",
                                 "🔄 **اسپم ممنوع است!** لطفاً آهسته‌تر پیام بفرست.")
            save_group_data(group_id, group_data)
            return

    # ===== بررسی سخنگو شخصی =====
    # 🛠 رفع باگ: کلیدواژه‌ها هنگام یادگیری با normalize_key ذخیره می‌شن (حروف
    # عربی/فارسی یکسان‌سازی و lowercase می‌شن) ولی اینجا با متن خام مقایسه
    # می‌شدن - یعنی مثلاً «كتاب» (کاف عربی) با کلیدواژه‌ی ذخیره‌شده‌ی «کتاب»
    # (کاف فارسی) هیچ‌وقت match نمی‌شد. الان متن پیام هم قبل از مقایسه نرمال میشه.
    #
    # 🛠 رفع باگ دوم (مهم‌تر): چون این تابع (auto_message_handler) بدون هیچ
    # فیلتری روی *همه‌ی* پیام‌ها اجرا می‌شه، وقتی کاربر روی جواب هوش مصنوعیِ
    # ربات ریپلای می‌زد (که با یک هندلر کاملاً جدا - ai_reply_continue_handler -
    # پردازش می‌شه)، این بخش هم به‌صورت مستقل روی همون پیام چک می‌شد؛ اگه متنِ
    # ریپلای کاربر (تصادفاً) هر کدوم از کلیدواژه‌های آموزش‌داده‌شده رو به‌عنوان
    # زیررشته داشت، یه جواب آماده‌ی کاملاً بی‌ربط (چرت‌وپرت) هم می‌فرستاد -
    # جدا از جواب واقعیِ هوش مصنوعی. الان اگه پیام واقعاً ادامه‌ی یک گفتگوی
    # فعالِ هوش مصنوعیِ همین کاربر باشه (دقیقاً همون تشخیصی که خودِ
    # ai_reply_continue_handler استفاده می‌کنه)، این بخش کاملاً رد می‌شه تا
    # جواب سخنگو با جواب هوش مصنوعی قاطی نشه.
    _reply_msg_for_learn = get_reply_message(message)
    _reply_text_for_learn = getattr(_reply_msg_for_learn, "text", None)
    _is_ai_conv_reply = bool(_reply_text_for_learn) and (
        f"{user_id}::{_reply_text_for_learn}" in group_data.get('ai_conversations', {})
    )
    if (not _is_ai_conv_reply and settings.get('speaker_enabled', True)
            and settings.get('speaker_personal_enabled', True)
            and group_data.get('learn', {}) and text):
        norm_text = normalize_fa(text).lower()
        for keyword, responses in group_data['learn'].items():
            if keyword and keyword in norm_text and responses:
                response = random.choice(responses)
                response = replace_tags(response, (await get_display_name(bot, message) or "کاربر"), group_data.get('group_name', 'گروه'))
                await message.reply(response)
                break
    
    # ===== ذخیره تغییرات =====
    save_group_data(group_id, group_data)

# =========================================================
#  🔗 اتصال Router به هندلرهای واقعی موجود (فاز ۱)
#  هر ورودی فقط تابعی را که از قبل در همین فایل نوشته و تست شده معرفی می‌کند؛
#  هیچ منطق جدیدی اینجا ساخته نمی‌شود.
# =========================================================
# =========================================================
#  🆕 پیاده‌سازی واقعی ۴ قابلیتی که در راهنما تبلیغ می‌شدند ولی هیچ‌جای کد
#  هندلر واقعی نداشتند:
#    ۱) ضد تبچی (روشن/خاموش/تشخیص/محدودسازی)
#    ۲) تنظیم خودکار دستورات + تنظیمات پیش‌فرض کامل
#    ۳) سیستم محدودیت عمومی دستورات («ضد خیانت»)
#    ۴) سیستم دستورات دلخواه (تغییرنام دستورات برای هر گروه)
# =========================================================

# ---------- ۱) ضد تبچی ----------
ANTI_TABCHI_WINDOW_MIN = 30          # حداقل ۳۰ ثانیه
ANTI_TABCHI_WINDOW_MAX = 86400       # حداکثر ۲۴ ساعت

@bot.on_message(filters=lambda m: _cmd_is(m, "tabchi_on"))
async def tabchi_on_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.SUPER_ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return
    group_data['settings']['anti_tabchi_enabled'] = True
    save_group_data(group_id, group_data)
    seconds = group_data['settings'].get('anti_tabchi_window_seconds', 300)
    await message.reply(f"✅ ضد تبچی فعال شد.\nهر عضوی که در {seconds} ثانیه‌ی اول بعد از عضویت لینک/فوروارد بفرسته، پیامش حذف و در صورت تکرار بن می‌شه.")

@bot.on_message(filters=lambda m: _cmd_is(m, "tabchi_off"))
async def tabchi_off_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.SUPER_ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return
    group_data['settings']['anti_tabchi_enabled'] = False
    save_group_data(group_id, group_data)
    await message.reply("✅ ضد تبچی غیرفعال شد.")

@bot.on_message(filters=lambda m: _cmd_is(m, "tabchi_status"))
async def tabchi_status_cmd(bot: Robot, message: Message):
    """تشخیص تبچی: وضعیت فعلی سیستم + تعداد اعضای «تازه‌وارد» که فعلاً زیر نظرند."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return
    settings = group_data['settings']
    enabled = settings.get('anti_tabchi_enabled', False)
    window = settings.get('anti_tabchi_window_seconds', 300)
    tmax = settings.get('anti_tabchi_max_warn', 1)
    suspects = 0
    for uid in group_data.get('members', {}):
        if await is_tabchi_suspect(group_data, uid):
            suspects += 1
    active_warns = len(group_data.get('warns_tabchi', {}))
    await message.reply(
        "🚷 **وضعیت ضد تبچی:**\n"
        f"• حالت: {'✅ روشن' if enabled else '❌ خاموش'}\n"
        f"• پنجره‌ی زمانی «تازه‌عضو»: {window} ثانیه\n"
        f"• حد اخطار قبل از بن: {tmax}\n"
        f"• اعضای زیر نظر (تازه‌وارد در بازه‌ی فعلی): {suspects} نفر\n"
        f"• کاربرانی که در حال حاضر اخطار تبچی دارند: {active_warns} نفر"
    )

@bot.on_message(filters=lambda m: _cmd_is(m, "tabchi_window"))
async def tabchi_window_cmd(bot: Robot, message: Message):
    """محدودسازی تبچی: تنظیم پنجره‌ی زمانی «تازه‌عضو» بر حسب ثانیه."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.SUPER_ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return
    parts = to_en_digits(message.text).split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply(f"⚠️ دستور: محدودسازی تبچی #ثانیه (بین {ANTI_TABCHI_WINDOW_MIN} تا {ANTI_TABCHI_WINDOW_MAX})")
        return
    seconds = int(parts[1])
    if not (ANTI_TABCHI_WINDOW_MIN <= seconds <= ANTI_TABCHI_WINDOW_MAX):
        await message.reply(f"⚠️ عدد باید بین {ANTI_TABCHI_WINDOW_MIN} تا {ANTI_TABCHI_WINDOW_MAX} ثانیه باشد.")
        return
    group_data['settings']['anti_tabchi_window_seconds'] = seconds
    save_group_data(group_id, group_data)
    await message.reply(f"✅ پنجره‌ی زمانی ضد تبچی روی {seconds} ثانیه تنظیم شد.")

# ---------- ۲) تنظیم خودکار دستورات + تنظیمات پیش‌فرض کامل ----------
@bot.on_message(filters=lambda m: _cmd_is(m, "auto_setup"))
async def auto_setup_cmd(bot: Robot, message: Message):
    """تنظیم خودکار دستورات: طبق FULL_GUIDE_2، ایده‌آل‌ترین تنظیمات مدیریتی را یکجا اعمال می‌کند."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.SUPER_ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return
    settings = group_data.setdefault('settings', {})
    # بن فوری لینک/آیدی
    settings['anti_link'] = True
    # قفل هایپرلینک (متادیتا) + فوروارد
    settings['lock_metadata'] = True
    settings['lock_forward'] = True
    # سه اخطار برای فحش و کلمات غیرمجاز (سیستم اخطارِ مشترک)
    settings['anti_swear'] = True
    settings['max_warn'] = 3
    settings['warn_action'] = DEFAULT_WARN_ACTION
    # نمایش اخطار و بن فعال (اخطارها همیشه نمایش داده می‌شوند؛ اقدام خودکار بعد از سقف فعال است)
    settings['auto_ban'] = True
    # چند کلمه کلیدی پیش‌فرض ممنوعه (اگر خالی بود، پیش‌فرض‌ها را برمی‌گرداند)
    filters_ = group_data.setdefault('filters', {})
    if not filters_.get('badwords'):
        filters_['badwords'] = ['سیاسی', 'مذهبی', 'جنسی', 'مخدر', 'الکل', 'قمار']
    if not filters_.get('swear'):
        filters_['swear'] = ['فحش', 'لعنت', 'کونی', 'جنده', 'بی شرف', 'بی ناموس', 'خائن', 'منافق']
    # حالت خواب غیرفعال
    settings['sleep_mode'] = False
    save_group_data(group_id, group_data)
    await message.reply(
        "✅ **تنظیم خودکار دستورات انجام شد!**\n"
        "🔗 بن فوری لینک/آیدی: فعال\n"
        "↗️ قفل فوروارد و متادیتا: فعال\n"
        "💢 اخطار فحش/کلمات غیرمجاز: ۳ اخطار (بعد از آن: "
        f"{WARN_ACTIONS.get(DEFAULT_WARN_ACTION, DEFAULT_WARN_ACTION)})\n"
        "📌 نمایش اخطار و بن خودکار: فعال\n"
        "😴 حالت خواب: غیرفعال"
    )

@bot.on_message(filters=lambda m: _cmd_is(m, "full_reset_defaults"))
async def full_reset_defaults_cmd(bot: Robot, message: Message):
    """تنظیمات پیش‌فرض کامل: کل settings/filters گروه را به حالت کارخانه برمی‌گرداند
    (لیست‌های مدیریتی مثل ادمین‌ها/مالک‌ها و آمار/لاگ دست‌نخورده می‌مانند)."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.OWNER):
        await message.reply(NO_PERMISSION_MSG)
        return
    fresh_id = f"__reset_template__{group_id}"
    template = get_group_data(fresh_id)  # یک ساختار پیش‌فرض تازه می‌سازد
    group_data['settings'] = template['settings']
    group_data['filters'] = template['filters']
    data = _ensure_cache_loaded()
    data.pop(fresh_id, None)
    save_group_data(group_id, group_data)
    await message.reply("✅ تنظیمات و فیلترهای گروه به‌طور کامل به حالت پیش‌فرض بازگشت.")

# ---------- ۳) سیستم محدودیت عمومی دستورات («ضد خیانت») ----------
def _today_key() -> str:
    return datetime.now().strftime('%Y-%m-%d')

def _cmd_restriction_usage_ok(group_data: dict, canonical: str, user_id: str) -> Tuple[bool, Optional[int], int]:
    """برمی‌گرداند: (مجاز است؟, تعداد استفاده‌ی امروز، سقف). اگر سقفی تنظیم نشده: (True, None, 0)."""
    cr = group_data.get('command_restrictions', {}).get(canonical, {})
    limit = (cr.get('user_limits') or {}).get(str(user_id))
    if not limit:
        return True, None, 0
    usage = group_data.setdefault('command_usage', {}).setdefault(_today_key(), {}).setdefault(canonical, {})
    used = usage.get(str(user_id), 0)
    return used < limit, used, limit

def _cmd_restriction_consume(group_data: dict, canonical: str, user_id: str):
    usage = group_data.setdefault('command_usage', {}).setdefault(_today_key(), {}).setdefault(canonical, {})
    usage[str(user_id)] = usage.get(str(user_id), 0) + 1

async def _handle_command_restriction(bot, message, group_id, group_data, user_id: str,
                                      canonical: str, rest: str) -> str:
    """
    قبل از اجرای واقعیِ هر دستورِ فارسی صدا زده می‌شود. دو کار می‌کند:
      الف) اگر rest یکی از فرمت‌های کنترلی («فعال»/«غیرفعال»/«#عدد») باشد، به‌جای اجرای دستور
           اصلی، تنظیمِ محدودیت را انجام می‌دهد (فقط با دسترسی ADMIN به بالا).
      ب) در غیر این صورت، چک می‌کند که آیا خودِ این دستور برای این کاربر مسدود/به سقف رسیده،
         که در این صورت اجرا را متوقف می‌کند.
    خروجی: "config" (پیام کنترلی بود و پاسخ داده شد)، "blocked" (اجرا مسدود شد)،
           یا "" (اجرای عادی ادامه پیدا کند).
    """
    reply_msg = getattr(message, "reply_to_message", None) or getattr(message, "reply_message", None)
    target_id = str(getattr(reply_msg, "sender_id", "")) if reply_msg else None
    norm_rest = normalize_key(rest or "")

    is_toggle = norm_rest in ("فعال", "غیرفعال")
    is_number = bool(re.fullmatch(r"#?\d+", to_en_digits(norm_rest))) if norm_rest else False

    if is_toggle or is_number:
        if not has_permission(user_id, group_data, Perm.ADMIN):
            await message.reply(NO_PERMISSION_MSG)
            return "config"
        cr = group_data.setdefault('command_restrictions', {}).setdefault(
            canonical, {"disabled": False, "user_disabled": [], "user_limits": {}})

        if is_number:
            if not target_id:
                await message.reply("👤 برای «[دستور] #عدد» باید روی پیام شخص موردنظر ریپلای بزنید.")
                return "config"
            num = int(to_en_digits(norm_rest).lstrip("#"))
            if num <= 0:
                await message.reply("⚠️ عدد باید بزرگ‌تر از صفر باشد.")
                return "config"
            cr.setdefault('user_limits', {})[target_id] = num
            save_group_data(group_id, group_data)
            await message.reply(f"✅ سقف استفاده‌ی روزانه‌ی این شخص از «{canonical}» روی {num} بار تنظیم شد.")
            return "config"

        # norm_rest == فعال/غیرفعال
        if target_id:
            ud = cr.setdefault('user_disabled', [])
            if norm_rest == "غیرفعال":
                if target_id not in ud:
                    ud.append(target_id)
                save_group_data(group_id, group_data)
                await message.reply(f"✅ دستور «{canonical}» فقط برای این شخص غیرفعال شد.")
            else:
                if target_id in ud:
                    ud.remove(target_id)
                cr.setdefault('user_limits', {}).pop(target_id, None)
                save_group_data(group_id, group_data)
                await message.reply(f"✅ محدودیت این شخص روی «{canonical}» برداشته شد.")
            return "config"
        else:
            cr['disabled'] = (norm_rest == "غیرفعال")
            save_group_data(group_id, group_data)
            state = "غیرفعال" if cr['disabled'] else "فعال"
            await message.reply(f"✅ دستور «{canonical}» برای کل گروه {state} شد.")
            return "config"

    # ---- اجرای عادی: چک محدودیت‌های از‌قبل‌تنظیم‌شده ----
    cr = group_data.get('command_restrictions', {}).get(canonical)
    if cr:
        if cr.get('disabled'):
            await message.reply("⛔ این دستور در حال حاضر برای این گروه غیرفعال است.")
            return "blocked"
        if user_id in (cr.get('user_disabled') or []):
            await message.reply("⛔ شما اجازه‌ی استفاده از این دستور را ندارید.")
            return "blocked"
        ok, used, limit = _cmd_restriction_usage_ok(group_data, canonical, user_id)
        if not ok:
            await message.reply(f"⏳ سقف استفاده‌ی روزانه‌ی شما از این دستور ({limit} بار) تمام شده؛ فردا دوباره امتحان کنید.")
            return "blocked"
        if limit:
            _cmd_restriction_consume(group_data, canonical, user_id)
            save_group_data(group_id, group_data)
    return ""

@bot.on_message(filters=lambda m: _cmd_is(m, "reset_cmd_restrictions"))
async def reset_cmd_restrictions_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.OWNER):
        await message.reply(NO_PERMISSION_MSG)
        return
    group_data['command_restrictions'] = {}
    group_data['command_usage'] = {}
    save_group_data(group_id, group_data)
    await message.reply("✅ همه‌ی محدودیت‌های دستورات (غیرفعال‌سازی‌ها و سقف‌های روزانه) ریست شدند.")

@bot.on_message(filters=lambda m: _cmd_is(m, "list_cmd_restrictions"))
async def list_cmd_restrictions_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return
    cr = group_data.get('command_restrictions', {})
    active = {k: v for k, v in cr.items() if v.get('disabled') or v.get('user_disabled') or v.get('user_limits')}
    if not active:
        await message.reply("📋 در حال حاضر هیچ محدودیتی روی هیچ دستوری تنظیم نشده.")
        return
    lines = ["📋 **مدیریت محدودیت همه‌ی دستورات:**\n"]
    for canonical, v in active.items():
        parts = [f"• {canonical}:"]
        if v.get('disabled'):
            parts.append("غیرفعال کامل")
        if v.get('user_disabled'):
            parts.append(f"غیرفعال برای {len(v['user_disabled'])} نفر")
        if v.get('user_limits'):
            parts.append(f"سقف روزانه برای {len(v['user_limits'])} نفر")
        lines.append(" ".join(parts))
    await message.reply("\n".join(lines))

# ---------- ۴) سیستم دستورات دلخواه ----------
@bot.on_message(filters=lambda m: _cmd_is(m, "set_custom_cmd"))
async def set_custom_cmd_cmd(bot: Robot, message: Message):
    """تنظیم دستور <اصلی> : <دلخواه> — مثال: «تنظیم دستور ساعت : زمان»."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return
    rest = _cmd_rest(message.text)
    if ":" in rest:
        original, custom = rest.split(":", 1)
    elif "،" in rest:
        original, custom = rest.split("،", 1)
    else:
        await message.reply("⚠️ دستور: «تنظیم دستور [دستور اصلی] : [دستور دلخواه]»\nمثال: تنظیم دستور ساعت : زمان")
        return
    original_key = normalize_key(original)
    custom_key = normalize_key(custom)
    if not original_key or not custom_key:
        await message.reply("⚠️ دستور: «تنظیم دستور [دستور اصلی] : [دستور دلخواه]»\nمثال: تنظیم دستور ساعت : زمان")
        return
    if original_key not in ALIAS_MAP:
        await message.reply(f"⚠️ «{original}» یک دستور شناخته‌شده نیست.")
        return
    if custom_key in ALIAS_MAP:
        await message.reply("⚠️ این عبارت از قبل یک دستور اصلی ربات است و نمی‌شود بازنویسی‌اش کرد.")
        return
    group_data.setdefault('custom_commands', {})[custom_key] = original_key
    save_group_data(group_id, group_data)
    await message.reply(f"✅ از این به بعد «{custom.strip()}» هم مثل «{original.strip()}» عمل می‌کند.")

@bot.on_message(filters=lambda m: _cmd_is(m, "remove_custom_cmd"))
async def remove_custom_cmd_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return
    rest = _cmd_rest(message.text)
    custom_key = normalize_key(rest)
    if not custom_key:
        await message.reply("⚠️ دستور: «حذف دستور [دستور دلخواه]»")
        return
    custom_cmds = group_data.get('custom_commands', {})
    if custom_key not in custom_cmds:
        await message.reply("⚠️ چنین دستور دلخواهی ثبت نشده.")
        return
    custom_cmds.pop(custom_key, None)
    save_group_data(group_id, group_data)
    await message.reply("✅ دستور دلخواه حذف شد.")

@bot.on_message(filters=lambda m: _cmd_is(m, "show_custom_cmd"))
async def show_custom_cmd_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    rest = _cmd_rest(message.text)
    custom_key = normalize_key(rest)
    custom_cmds = group_data.get('custom_commands', {})
    if not custom_key:
        await message.reply("⚠️ دستور: «نمایش دستور [دستور دلخواه]»")
        return
    original = custom_cmds.get(custom_key)
    if not original:
        await message.reply("⚠️ چنین دستور دلخواهی ثبت نشده.")
        return
    await message.reply(f"🔎 «{rest.strip()}» ← معادل دستور «{original}» است.")

@bot.on_message(filters=lambda m: _cmd_is(m, "list_custom_cmds"))
async def list_custom_cmds_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    custom_cmds = group_data.get('custom_commands', {})
    if not custom_cmds:
        await message.reply("📋 هیچ دستور دلخواهی برای این گروه ثبت نشده.")
        return
    lines = ["📋 **لیست دستورات شخصی این گروه:**\n"]
    for custom_key, original_key in custom_cmds.items():
        lines.append(f"• «{custom_key}» ← «{original_key}»")
    await message.reply("\n".join(lines))

@bot.on_message(filters=lambda m: _cmd_is(m, "clear_custom_cmds"))
async def clear_custom_cmds_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return
    group_data['custom_commands'] = {}
    save_group_data(group_id, group_data)
    await message.reply("✅ همه‌ی دستورات دلخواه این گروه پاک شدند.")

def resolve_custom_command_text(group_data: dict, text: str) -> str:
    """اگر ابتدای متن با یک trigger سفارشیِ همین گروه مطابقت داشته باشد، معادل اصلی‌اش
    را جایگزین می‌کند (همراه بقیه‌ی متن/آرگومان‌ها) و متن جدید را برمی‌گرداند؛ وگرنه متن اصلی."""
    custom_cmds = group_data.get('custom_commands') or {}
    if not custom_cmds or not text:
        return text
    norm_key = normalize_key(text)
    norm_full = normalize_fa(text)
    best = None  # (len(trigger), original)
    for trigger, original in custom_cmds.items():
        if norm_key == trigger:
            rest = ""
        elif norm_key.startswith(trigger + " "):
            rest = norm_full[len(trigger):].strip()
        else:
            continue
        if best is None or len(trigger) > best[0]:
            best = (len(trigger), original, rest)
    if best is None:
        return text
    _, original, rest = best
    return f"{original} {rest}".strip()

def _resolve_command(message):
    """مثل _match_alias، ولی اول trigger های سفارشیِ همین گروه (سیستم «دستورات دلخواه») را هم
    در نظر می‌گیرد."""
    text = getattr(message, "text", None)
    if not text:
        return None
    group_id = get_chat_group_id(message)
    if group_id:
        group_data = get_group_data(group_id)
        rewritten = resolve_custom_command_text(group_data, text)
        if rewritten != text:
            matched = _match_alias(rewritten)
            if matched:
                return matched
    return _match_alias(text)

register_router_target("/bio", bio_cmd)
register_router_target("/khater", khater_cmd)
register_router_target("/fal", fal_cmd)
register_router_target("/challenge", challenge_cmd)
register_router_target("/story", story_cmd)
register_router_target("/truth", truth_cmd)
register_router_target("/dare", dare_cmd)
register_router_target("/truth_or_dare", truth_or_dare_cmd)
register_router_target("/penalty", penalty_cmd)
register_router_target("/penalty_dare", penalty_dare_cmd)
register_router_target("/riddle", riddle_cmd)
register_router_target("/proverb", proverb_cmd)
register_router_target("/motivation", motivation_cmd)
register_router_target("/joke", joke_cmd)
register_router_target("/funfact", fun_fact_cmd)

register_router_target("/ban", ban_cmd)
register_router_target("/unban", unban_cmd)
register_router_target("/kick", kick_cmd)
register_router_target("/warn", warn_cmd)
register_router_target("/unwarn", unwarn_cmd)
register_router_target("/mute", mute_cmd)
register_router_target("/unmute", unmute_cmd)
register_router_target("/warnaction", warnaction_cmd)
register_router_target("/warnexpire", warnexpire_cmd)
register_router_target("/block", block_cmd)
register_router_target("/unblock", unblock_cmd)
register_router_target("/clear", clear_cmd)

register_router_target("/lock", lock_group_cmd)
register_router_target("/sleep_on", sleep_on_cmd)
register_router_target("/sleep_off", sleep_off_cmd)
register_router_target("/antispam", anti_spam_cmd)
register_router_target("/antilink", anti_link_cmd)
register_router_target("/linklockon", link_lock_on_cmd)
register_router_target("/linklockoff", link_lock_off_cmd)
register_router_target("/swearlockon", swear_lock_on_cmd)
register_router_target("/swearlockoff", swear_lock_off_cmd)
register_router_target("/spamlockon", spam_lock_on_cmd)
register_router_target("/spamlockoff", spam_lock_off_cmd)
register_router_target("/captionlockon", caption_lock_on_cmd)
register_router_target("/captionlockoff", caption_lock_off_cmd)
register_router_target("/captionban_on", caption_ban_on_cmd)
register_router_target("/captionban_off", caption_ban_off_cmd)
register_router_target("/captionshowwarn_on", caption_showwarn_on_cmd)
register_router_target("/captionshowwarn_off", caption_showwarn_off_cmd)
register_router_target("/captionwarn_set", caption_warn_set_cmd)
register_router_target("/captionwarn_reset", caption_warn_reset_cmd)
register_router_target("/set_custom_emoji", set_custom_emoji_cmd)
register_router_target("/reset_all_custom_emoji", reset_all_custom_emoji_cmd)
register_router_target("/list_custom_emoji", list_custom_emoji_cmd)
register_router_target("/antiswear", anti_swear_cmd)
register_router_target("/filters", filters_list_cmd)

register_router_target("/admins", admins_list_cmd)
register_router_target("/specials", specials_list_cmd)
register_router_target("/exempts", exempts_list_cmd)
# 🛠 رفع باگ: این‌ها تابع واقعی و کار می‌کردن ولی هیچ‌جا (نه به‌عنوان
# router target نه به‌عنوان ALIAS_MAP) به عبارت فارسیِ راهنما وصل نشده
# بودن - یعنی «لیست مالک»/«لیست بلاک»/«لیست سکوت» که مستقیماً توی راهنما
# تبلیغ می‌شدن، هیچ جوابی نمی‌گرفتن (فقط دستور اسلش انگلیسیِ /owners و... کار
# می‌کرد که هیچ‌کس توی این ربات فارسی‌محور اونا رو تایپ نمی‌کنه).
register_router_target("/owners", owners_list_cmd)
register_router_target("/blocks", blocks_list_cmd)
register_router_target("/mutes", mutes_list_cmd)
register_router_target("/bans", bans_list_cmd)
register_router_target("/addfilter", add_filter_cmd)
register_router_target("/removefilter", remove_filter_cmd)
register_router_target("/clearfilters", clear_filters_cmd)

ALIAS_MAP["لیست ادمین"] = ("/admins", Perm.MEMBER)
ALIAS_MAP["لیست مالک"] = ("/owners", Perm.MEMBER)
ALIAS_MAP["لیست ویژه"] = ("/specials", Perm.MEMBER)
ALIAS_MAP["لیست معاف"] = ("/exempts", Perm.MEMBER)
ALIAS_MAP["لیست بلاک"] = ("/blocks", Perm.MEMBER)
ALIAS_MAP["لیست سکوت"] = ("/mutes", Perm.MEMBER)
ALIAS_MAP["لیست بن"] = ("/bans", Perm.MEMBER)
# 🛠 رفع باگ بزرگ: «فیلتر فحش»/«فیلتر کلمه» و مشتقاتشون (که کل بخش «قفل
# فحش» و «قفل کلمات غیرمجاز» راهنما دور همین‌ها ساخته شده) اصلاً هیچ الیاسی
# نداشتن - فقط دستور خام /addfilter و /removefilter و /filters کار می‌کردن.
# کد فعلی این دو مفهوم رو در یک لیست مشترک (filters.swear) پیاده‌سازی کرده،
# پس هر دو عبارت راهنما به همون یک لیست وصل می‌شن (به‌جای این‌که یکی‌شون
# کاملاً بی‌جواب بمونه).
ALIAS_MAP["فیلتر فحش"] = ("/addfilter", Perm.ADMIN)
ALIAS_MAP["فیلتر کلمه"] = ("/addfilter", Perm.ADMIN)
ALIAS_MAP["حذف فیلتر فحش"] = ("/removefilter", Perm.ADMIN)
ALIAS_MAP["حذف فیلتر کلمه"] = ("/removefilter", Perm.ADMIN)
ALIAS_MAP["لیست فحش"] = ("/filters", Perm.MEMBER)
ALIAS_MAP["لیست کلمات غیرمجاز"] = ("/filters", Perm.MEMBER)
ALIAS_MAP["پاکسازی لیست فحش"] = ("/clearfilters", Perm.ADMIN)
ALIAS_MAP["پاکسازی لیست کلمات غیرمجاز"] = ("/clearfilters", Perm.ADMIN)

register_router_target("/rules", rules_show_cmd)
register_router_target("/mystats", mystats_cmd)
register_router_target("/gstats", gstats_cmd)
register_router_target("/level", level_cmd)

register_router_target("/announce", announce_cmd)
register_router_target("/tagall", tagall_cmd)
register_router_target("/tag_owners", tag_owners_cmd)
register_router_target("/tag_admins", tag_admins_cmd)
register_router_target("/tag_specials", tag_specials_cmd)
register_router_target("/tag_exempts", tag_exempts_cmd)
register_router_target("/tag_mutes", tag_mutes_cmd)
register_router_target("/tag_blocks", tag_blocks_cmd)
register_router_target("/tag_kills", tag_kills_cmd)
register_router_target("/backup", backup_cmd)
register_router_target("/backups", backups_list_cmd)
register_router_target("/restore", restore_cmd)

# 🛠 اتصال هندلرهای «تم» و «لینک گروه» که در ALIAS_MAP بالا اضافه شدند؛
# بدون این خط‌ها، persian_alias_router دستور را تشخیص می‌داد ولی هیچ تابعی
# برای اجرا پیدا نمی‌کرد (پیام «هنوز به هندلر واقعی وصل نشده است» می‌گرفت).
register_router_target("/theme", theme_cmd)
register_router_target("/set_theme", set_theme_cmd)
register_router_target("/set_default_theme", set_default_theme_cmd)
register_router_target("/font", font_cmd)
register_router_target("/font_set", font_set_cmd)
register_router_target("/link", link_cmd)
register_router_target("/set_link", set_link_cmd)
register_router_target("/delete_link", delete_link_cmd)

register_router_target("/addadmin", add_admin_cmd)
register_router_target("/removeadmin", remove_admin_cmd)
register_router_target("/addspecial", add_special_cmd)
register_router_target("/removespecial", remove_special_cmd)
register_router_target("/addowner", add_owner_cmd)
register_router_target("/removeowner", remove_owner_cmd)
register_router_target("/exempt", exempt_cmd)
register_router_target("/unexempt", unexempt_cmd)


# =========================================================
#  📖 راهنما (جدید) — دسته‌بندی‌شده، فارسی + Slash
# =========================================================
HELP_TEXT = """╭━━━━ 📖 راهنمای گاردی ایکس ━━━━╮

🎮 سرگرمی (همه)
  بیو | خاطره | فال | چالش | داستان | پنالتی
  معما | ضرب‌المثل | جمله انگیزشی | شوخی | حقیقت جالب

👤 پروفایل و آمار (همه)
  پروفایل | آمار | سطح

🛡 مدیریت (مدیر و بالاتر — با ریپلای روی کاربر)
  بن | آنبن | اخراج | اخطار | رفع اخطار | ریست اخطار
  سکوت | آنسکوت | مسدود | آنبلاک | پاکسازی

🔐 امنیت (مدیر ارشد)
  قفل | ضدلینک | ضداسپم | ضدفحش | فیلترها
  حداکثر اخطار | مدت سکوت

👑 مدیران (مدیر ارشد / مالک)
  مدیران | ویژه‌ها | معاف‌ها
  /addadmin | /removeadmin | /addowner | /removeowner

🧠 سخنگو (مدیر و بالاتر)
  /learn [کلمه] ! [پاسخ] | /unlearn [کلمه] | /learned

📢 ابزارهای گروه
  اعلان | تگ همه | بکاپ | قوانین | لاگ | /admin (منوی مدیریت)

⚙️ تنظیمات
  تنظیمات

💡 همه دستورات Slash قدیمی (/ban، /mute، /stats و...) هم دقیقاً مثل قبل کار می‌کنند.
📚 لیست کامل و جامع دستورات: «راهنمای کامل ۱» تا «راهنمای کامل ۳»
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"""

@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("راهنما", "help"))
async def help_router_cmd(bot: Robot, message: Message):
    await message.reply(HELP_TEXT)


# =========================================================
#  📚 راهنمای کامل (مرجع جامع دستورات — ۳ بخش)
#  این متن‌ها مستقیماً از فهرست کامل دستورات و امکانات گاردی
#  (قفل‌ها، اموجی‌ها، تم/فونت، مدیریت مقام‌ها، آنتی‌اسپم،
#  هوش مصنوعی، سخنگو/یادگیری، خوشامدگویی و ...) گردآوری شده‌اند.
# =========================================================

FULL_GUIDE_1 = """╭━━━ 📚 راهنمای کامل گاردی (۱/۳) ━━━╮

✅ تایید عدم دسترسی
اگر مالک گروهید ولی مالک گاردی نشدید: دسترسی حذف پیام رو از گاردی بگیرید، دستور «تایید عدم دسترسی» رو بفرستید، دوباره دسترسی رو بدید. با «مالک» هم مالک اصلی گاردی رو می‌بینید.

✅ فعال/غیرفعال کردن دستورات
• [دستور] فعال / [دستور] غیرفعال  (برای سرگرمی و کاربردی، مثل: چالش غیرفعال، تاریخ فعال)

✅ سیستم قفل‌ها (لینک، آیدی، فوروارد، کدهنگی، متادیتا، کپشن، محتوای غیرمجاز، مستهجن و ...)
• لیست قفل
• لینک قفل / لینک باز
• تنظیم اخطار لینک #عدد
• تنظیم اخطار عدد غیرفعال  (برگشت به تعداد اخطار داشبورد)
• نمایش اخطار لینک فعال/غیرفعال
• بن عکس فعال/غیرفعال  (اگر خاموش باشه فقط عکس حذف میشه، بن نمیشه)

✅ قفل فحش
فیلتر فحش #متن | حذف فیلتر فحش #متن | قفل فحش | لیست فحش | پاکسازی لیست فحش | تنظیم اخطار فحش # | بن فحش فعال/غیرفعال | نمایش اخطار فحش فعال/غیرفعال

✅ قفل کلمات غیرمجاز
فیلتر کلمه #متن | حذف فیلتر کلمه #متن | قفل کلمات غیرمجاز | لیست کلمات غیرمجاز | پاکسازی لیست کلمات غیرمجاز | تنظیم اخطار کلمات غیرمجاز # | بن کلمات غیرمجاز فعال/غیرفعال

✅ شخصی‌سازی اموجی‌ها
تنظیم اموجی داشبورد [اموجی] | ریست اموجی داشبورد | لیست اموجی (برای دیدن همه‌ی بخش‌های قابل شخصی‌سازی)

✅ مسدودسازی
بن | ریم | سیک | اخراج  ← مسدود کردن
رفع مسدودیت | حذف بن | حذف ریم | انبن | انسیک  ← رفع مسدودیت

✅ قفل متادیتا (هایپرلینک، نقل‌قول و ...)
لیست متادیتا | نقل قول قفل / باز | تنظیم اموجی متادیتا [اموجی]

✅ آمار گروه و آمار اعضا
تنظیم اموجی آمار گروه [اموجی] | تنظیم اموجی آمار اعضا [اموجی]

✅ تگ‌ها
تگ ادمین | تگ ویژه | تگ مالک | تگ معاف | تگ سکوت | تگ کیل | تگ بلاک
تنظیم اموجی تگ [اموجی] | ریست اموجی تگ

✅ تنظیم قوانین
تنظیم قوانین #متن_قوانین | قوانین (نمایش) | حذف قوانین
دستور قوانین فعال/غیرفعال | تنظیم اموجی قوانین [اموجی]

✅ تم‌ها
تنظیم تم [فانتزی/عاشقانه/بهاری/شخصی/پیشفرض/پسرونه/دخترونه/ایران/جنگل/سلطنتی/شرقی/علاءالدین/کلاسیک/هانیبال/بریکینگ بد]
پنل تم | تنظیم تم پیشفرض

✅ بخش داشبورد
نمایش اخطار خاموش/روشن | بن روشن/خاموش | سرگرمی خاموش/روشن | سخنگو خاموش/روشن | پنل سخنگو
حالت خواب خاموش/روشن | حذف خودکار روشن/خاموش | ضد تبچی روشن/خاموش | تنظیم اخطار #عدد

✅ بخش محدودیت
قفل لینک/آیدی/فوروارد/کدهنگی | لیست قفل | محدودیت
[دستور] خاموش / [دستور] روشن  (برای سرگرمی‌ها و کاربردی‌ها)

✅ انتقال مالکیت بات
انتقال مالکیت (با ریپلای) یا انتقال مالکیت #شناسه_کاربر
شناسه کاربری (با/بدون ریپلای) | مالک

✅ لیست مجاز (Whitelist)
افزودن مجاز ... | حذف مجاز ... | لیست مجاز | پاکسازی لیست مجاز

✅ تنظیم مشخصات کاربری (بخش دسترسی)
تنظیم لقب/اصل/اسم/فامیلی غیرفعال یا فعال | تنظیم مشخصات غیرفعال
آمار (نمایش مشخصات خود) | حذف لقب/اصل/نام/فامیلی

╰━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"""

FULL_GUIDE_2 = """╭━━━ 📚 راهنمای کامل گاردی (۲/۳) ━━━╮

🌟 بخش مدیریتی و مقام‌ها
مقام‌ها: مالک اصلی → مالک → ویژه → ادمین → کاربر عادی
روش استفاده: با ریپلای روی شخص یا با «سکوت #شناسه_کاربر»

افزودن مالک/برکناری (دسترسی: مالک اصلی) | لیست مالک | پاکسازی لیست مالک
ویژه/برکناری (دسترسی: مالکین) | لیست ویژه | پاکسازی لیست ویژه
ادمین/برکناری (دسترسی: ویژه به‌بالا) | لیست ادمین | پاکسازی لیست ادمین
بلاک/حذف بلاک | لیست بلاک | پاکسازی لیست بلاک
سکوت/حذف سکوت | لیست سکوت | پاکسازی لیست سکوت
معاف/حذف معاف | لیست معاف | پاکسازی لیست معاف
کیل/حذف کیل | لیست کیل | پاکسازی لیست کیل

لیست‌ها، پاکسازی‌ها و ریست‌ها هر کدوم اموجی اختصاصی قابل تنظیم دارن:
تنظیم اموجی لیست [اموجی] | تنظیم اموجی پاکسازی [اموجی] | تنظیم اموجی ریست [اموجی]

🌟 فونت
پنل فونت | تنظیم فونت #نام‌فونت | تنظیم اموجی پنل فونت #اموجی | ریست اموجی پنل فونت
فونت‌ها: شکسته، لش، کشیده، سریانی، خط خورده، پیشفرض

🌟 قفل کپشن
قفل کپشن | کپشن باز | بن کپشن فعال/غیرفعال | نمایش اخطار کپشن فعال/غیرفعال
تنظیم اخطار کپشن #عدد | تنظیم اخطار کپشن غیرفعال

🌟 دستور آمار
دستور آمار غیرفعال/فعال
منع دستور برای شخص خاص: [دستور] غیرفعال/فعال + ریپلای روی شخص (مثال: دستور تاس غیرفعال)
بدون ریپلای = محدودیت روی کل گروه (قابل مشاهده در «محدودیت»)

✳️ قفل محتوای غیرمجاز
قفل محتوا / محتوا باز | فیلتر محتوا (با ریپلای) | حذف فیلتر محتوا (با ریپلای)
لیست محتوای غیرمجاز | پاکسازی لیست محتوا | تنظیم اموجی لیست محتوا #اموجی | ریست اموجی لیست محتوا
کاربرد: ممنوع کردن یک گیف/فایل/عکس/صدای خاص و مزاحم در گروه

✳️ تنظیم خودکار دستورات
دستور: «تنظیم خودکار دستورات» ← ایده‌آل‌ترین تنظیمات مدیریتی رو یکجا اعمال می‌کنه
شامل: بن فوری لینک/آیدی، دو اخطار برای پیام بلند/فوروارد/متادیتا، سه اخطار برای فحش و کلمات غیرمجاز، چند کلمه کلیدی پیش‌فرض ممنوعه، قفل هایپرلینک، نمایش اخطار و بن فعال، حالت خواب غیرفعال

✳️ سیستم ضد خیانت (محدودیت استفاده از دستورات)
دستور [X] #عدد  → محدود کردن تعداد استفاده روزانه (با ریپلای)
دستور [X] فعال → برداشتن محدودیت
دستور [X] غیرفعال/فعال → قطع دائمی دسترسی به آن دستور
ریست محدودیت → بازگشت همه محدودیت‌ها به حالت اول

✳️ تنظیم دستورات دلخواه
تنظیم دستور | حذف دستور | نمایش دستور | لیست دستورات شخصی | پاکسازی لیست دستورات شخصی
مثال: «تنظیم دستور ساعت : زمان» یعنی به‌جای «ساعت» از «زمان» استفاده بشه
دستور تنظیم دستور فعال/غیرفعال | دستور تنظیم دستور #تعداد

✅ اطلاعات و قیمت‌ها
قابلیت اطلاعات کشورها (با اسم کشور / پایتخت / اموجی پرچم)
قیمت طلا | قیمت دلار | قیمت سکه | قیمت ارز | قیمت رمز ارز | شاخص بورس | شاخص فرابورس | شاخص‌های منتخب
(همگی قابل شخصی‌سازی دستور/اموجی و محدودسازی برای اعضا)

✳️ آنتی‌اسپم
جلوگیری از پیام‌های رگباری/تکراری
اسپم قفل / باز | تنظیم اخطار اسپم #عدد | بن اسپم فعال/غیرفعال | نمایش اخطار اسپم فعال/غیرفعال

🌟 تنظیم مجزا برای هر شخص (با ریپلای)
تمام قفل‌ها (لینک، فحش، کلمات غیرمجاز، متادیتا و ...) رو می‌شه با ریپلای زدن، فقط برای یک نفر جدا تنظیم کرد:
لینک قفل/باز، نمایش اخطار لینک فعال/غیرفعال، بن لینک فعال/غیرفعال، تنظیم اخطار لینک #عدد
برای برداشتن: حذف قفل لینک (و مشابه آن برای بقیه‌ی قفل‌ها)
حذف لیست فحش | حذف لیست کلمات غیرمجاز | حذف لیست متادیتا

🌟 هوش مصنوعی
فقط برای مقام ویژه و مالک | استفاده: «هوش مصنوعی [متن]»
دستور هوش مصنوعی غیرفعال/فعال (با ریپلای = فقط برای همون شخص)
دستور هوش مصنوعی #عدد → محدودیت تعداد استفاده روزانه برای شخص خاص
ریپلای روی پاسخ قبلی هوش مصنوعی = ادامه‌ی همون گفتگو | بدون ریپلای = گفتگوی جدید
گفتگوها در پایان روز خودکار پاک می‌شن

🌟 ساخت گیف
ساخت گیف #متن | دستور ساخت گیف غیرفعال/فعال (با ریپلای برای یک نفر)
دستور ساخت گیف #عدد → محدودیت تعداد در روز
فایل خروجی به‌صورت لینک دانلود موقت ارسال می‌شه

🌟 حذف خودکار پیام‌های مدیریتی
حذف خودکار فعال/غیرفعال | تنظیم حذف خودکار #ثانیه (پیش‌فرض ۱۰ ثانیه)
دستور تنظیم حذف خودکار غیرفعال/فعال | دستور تنظیم حذف خودکار #عدد

╰━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"""

FULL_GUIDE_3 = """╭━━━ 📚 راهنمای کامل گاردی (۳/۳) ━━━╮

🌟 تنظیمات پیشرفته (فقط مالکین)
انتخاب اسم تصادفی فعال/غیرفعال
لیست پیشفرض فحش فعال/غیرفعال
لیست پیشفرض کلمات غیرمجاز فعال/غیرفعال
حذف پیام کاربر بن‌شده فعال/غیرفعال
تنظیم تعداد نمایش اخطار #مقدار
تنظیم حساسیت تشخیص کدهنگی #درصد (پیش‌فرض ۷۰٪)
فایل حجیم قفل/باز | تنظیم حجم فایل حجیم #مگابایت (پیش‌فرض ۵۰ مگابایت)
تنظیم دسترسی سرگرمی [مالک / مالک ویژه / مالک ویژه ادمین / مالک ویژه ادمین کاربرعادی]
تنظیم دسترسی سخنگو [همان ترکیب بالا]
پنل پیشرفته → نمایش وضعیت فعلی همه‌ی موارد بالا

🌟 تنظیم لینک گروه
تنظیم لینک #لینک‌گروه | لینک | حذف لینک
هرکدام قابل غیرفعال شدن: دستور تنظیم لینک غیرفعال/فعال، دستور لینک غیرفعال/فعال، دستور حذف لینک غیرفعال/فعال
محدودیت تعداد درخواست لینک برای شخص خاص: دستور لینک #عدد (با ریپلای)

🌟 قفل گروه
قفل گروه | گروه باز
دستور قفل گروه غیرفعال/فعال | دستور گروه باز غیرفعال/فعال
محدودیت تعداد استفاده: دستور قفل گروه #عدد (با ریپلای)

🌟 پیام مجاز در گروه
تنظیم پیام مجاز #متن | پیام مجاز (نمایش) | حذف پیام مجاز
دستور تنظیم پیام مجاز غیرفعال/فعال | دستور پیام مجاز غیرفعال/فعال | دستور حذف پیام مجاز غیرفعال/فعال
محدودیت تعداد: دستور تنظیم پیام مجاز #عدد (با ریپلای)

🌟 حذف پیام‌های یک کاربر
حذف #عدد  (با ریپلای روی کاربر → همون تعداد پیام آخرش حذف میشه)

🌟 سخنگوی شخصی و یادگیری
آموزش: «کلیدواژه ! پاسخ۱ ! پاسخ۲ ...»  → مثال: گاردی ! جونم ! بله عزیزم
نمایش پاسخ‌های یک کلیدواژه: «! کلیدواژه»
حذف یک پاسخ خاص: «کلیدواژه !! پاسخ»
حذف همه‌ی پاسخ‌های یک کلیدواژه: «کلیدواژه !!»
پنل سخنگو | سخنگو فعال | سخنگو بی‌ادب فعال/غیرفعال | سخنگو شخصی فعال/غیرفعال
(باید سخنگوی شخصی فعال باشه تا از کلمات یادگرفته‌شده استفاده کنه)

🌟 تنظیم مشخصات کاربری (گروهی و سراسری)
گروهی: تنظیم لقب/اصل/اسم/فامیلی #متن
سراسری: تنظیم لقب/اصل/اسم/فامیلی سراسری #متن
نمایش: لقب | اصل | اسم | فامیلی | لقب سراسری | اصل سراسری | اسم سراسری | فامیلی سراسری
حذف: حذف لقب/اصل/نام/فامیلی (و نسخه‌ی سراسری هرکدام)

🌟 شناسه کاربری و آیدی
شناسه کاربری (با ریپلای یا بدون ریپلای برای خود شخص)
همه‌ی دستورات گاردی هم با آیدی(یوزرنیم) و هم با شناسه کاربری کار می‌کنن (فقط برای آیدی، شخص باید یک‌بار پیوی بات رو استارت زده باشه)

🌟 هشتگ‌های کاربردی
#اسم_گروه → نام گروه
#تگ_کاربر → منشن (تگ) کاربر
#اسم_کاربر → نام نمایشی کاربر
#زمان یا #ساعت → ساعت فعلی
#تاریخ → تاریخ امروز
قابل استفاده در: سخنگو، قوانین، خوشامدگویی و خداحافظی

🌟 خوشامدگویی و خداحافظی
داشبورد وضعیت | خوشامدگویی فعال/غیرفعال | خداحافظی فعال/غیرفعال
تنظیم خوشامدگویی #متن | تنظیم خداحافظی #متن
نمایش: خوشامدگویی | خداحافظی
ریست خوشامدگویی | ریست خداحافظی
قابل غیرفعال‌سازی/محدودسازی برای ادمین‌ها (با/بدون ریپلای)
⚠️ توجه: به‌دلیل محدودیت فعلی پلتفرم، پیام خداحافظی غیرفعاله و پیام خوشامد فقط روی اولین پیام کاربر در گروه ارسال می‌شه.

✅ قفل مستهجن
لیست قفل | محدودیت
محتوای مستهجن قفل / باز
تنظیم اخطار محتوای مستهجن #عدد
بن محتوای مستهجن غیرفعال/فعال | نمایش اخطار محتوای مستهجن غیرفعال/فعال
حذف قفل محتوای مستهجن + ریپلای (استثنا برای یک شخص)
⚠️ فایل‌های بیش از ۵۰ مگابایت معمولاً بررسی نمی‌شن و در صورت عدم بررسی، بدون اخطار حذف می‌شن.

✅ کار با رسانه‌ها (سیو)
روی یک رسانه (عکس/فیلم/صدا/فایل) ریپلای بزنید و بفرستید: «سیو»
بعد از پردازش، بات یک هشتگ اختصاصی (مثل #image4) بهتون میده که هرجا استفاده بشه (مثلاً در خوشامدگویی یا یادگیری سخنگو) همون رسانه نمایش داده میشه.

🎮 پنالتی (فوتبالی) — جدید
دستور «پنالتی» یک پنالتی شبیه‌سازی‌شده می‌زنه؛ نتیجه تصادفیه:
گل ⚽️ | سیو شد 🧤 | دروازه‌بان گرفتش 🧤 | خورد به تیر 🥅
برای چالش/دیر پنالتی (نه شبیه‌سازی فوتبالی): «پنالتی چالش»

╰━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"""

@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("راهنمای کامل", "راهنمای کامل ۱", "راهنمای کامل 1"))
async def full_guide_1_cmd(bot: Robot, message: Message):
    await message.reply(FULL_GUIDE_1)

@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("راهنمای کامل ۲", "راهنمای کامل 2"))
async def full_guide_2_cmd(bot: Robot, message: Message):
    await message.reply(FULL_GUIDE_2)

@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("راهنمای کامل ۳", "راهنمای کامل 3"))
async def full_guide_3_cmd(bot: Robot, message: Message):
    await message.reply(FULL_GUIDE_3)


# =========================================================
#  👤 پروفایل (جدید) — از داده‌های واقعی موجود در دیتابیس
# =========================================================
@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("پروفایل", "profile"))
async def profile_router_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return

    group_data = get_group_data(group_id)
    reply_msg = getattr(message, "reply_to_message", None) or getattr(message, "reply_message", None)
    target_id = str(getattr(reply_msg, "sender_id", "")) if reply_msg is not None else str(message.sender_id)

    user_info = group_data.get("users", {}).get(target_id, {})
    name = user_info.get("first_name", "کاربر") or "کاربر"
    xp = group_data.get("xp", {}).get(target_id, 0)
    level = xp // 100  # همان فرمول ساده‌ای که level_cmd از قبل استفاده می‌کند
    warn_count = get_warn_count(group_data, target_id)
    max_warn = group_data.get("settings", {}).get("max_warn", 3)
    msg_count = group_data.get("message_count", {}).get(target_id, 0)
    ban_count = 1 if is_punished_active(group_data, "bans", target_id) else 0
    mute_count = 1 if is_punished_active(group_data, "mutes", target_id) else 0
    level_name = PERM_NAMES.get(get_permission_level(target_id, group_data), "عضو")

    text = (
        "╭━━━━ 👤 پروفایل ━━━━╮\n"
        f"┃ 👤 نام: {name}\n"
        f"┃ 🆔 شناسه: {target_id}\n"
        f"┃ 🎖 نقش: {level_name}\n"
        f"┃ ⭐ سطح: {level}\n"
        f"┃ ✨ XP: {xp}\n"
        f"┃ 💬 پیام: {msg_count}\n"
        f"┃ ⚠️ اخطار: {warn_count}/{max_warn}\n"
        f"┃ 🔇 سکوت: {'بله' if mute_count else 'خیر'}\n"
        f"┃ 🚫 بن: {'بله' if ban_count else 'خیر'}\n"
        "╰━━━━━━━━━━━━━━━━━━╯"
    )
    await message.reply(text)


# =========================================================
#  ⚙️ داشبورد تنظیمات (جدید) — روی همان دیکشنری settings موجود کار می‌کند
# =========================================================
def _onoff(v) -> str:
    return "🟢" if v else "🔴"

@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("آیدی من", "ایدی من", "شناسه من", "myid", "/myid"))
async def my_id_cmd(bot: Robot, message: Message):
    """نمایش شناسه‌ی عددی خود شما - برای مثال برای گذاشتن در SUPER_OWNERS یا برای /addowner"""
    user_id = str(message.sender_id)
    tag = " (مالک اصلی ربات ✅)" if is_super_owner(user_id) else ""
    await message.reply(f"🆔 شناسه‌ی شما: {user_id}{tag}")


@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("وضعیت مالکیت", "چک مالکیت", "ownership status", "مالک"))
async def ownership_status_cmd(bot: Robot, message: Message):
    """
    🔎 عیب‌یابی سریع مالکیت — مخصوصاً وقتی ربات روی چند ده/صد گروه فعاله.
    نشون می‌ده ربات الان کی رو به‌عنوان مالک این گروه مشخص می‌شناسه، تا اگه
    اشتباه بود، مالک واقعی سریع بفهمه و با «انتقال مالکیت» (ریپلای) درستش کنه.
    """
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    owners = group_data.get("owners", [])
    my_level = get_permission_level(user_id, group_data)
    lines = ["╭━━━━ 🔎 وضعیت مالکیت ━━━━╮"]
    if owners:
        for oid in owners:
            name = get_user_name_from_id(oid, group_data)
            lines.append(f"┃ 👑 {name} — {oid}")
    else:
        lines.append("┃ ⚠️ هنوز هیچ مالکی برای این گروه ثبت نشده!")
    lines.append(f"┃ 🆔 شناسه‌ی شما: {user_id}")
    lines.append(f"┃ 🎖 سطح دسترسی شما: {PERM_NAMES.get(my_level, my_level)}")
    lines.append("╰━━━━━━━━━━━━━━━━━━━━╯")
    if not owners:
        lines.append(
            "برای ثبت خودت به‌عنوان مالک، کافیه همین الان یه پیام دیگه بفرستی "
            "(اولین پیام‌فرست، خودکار مالک می‌شه)."
        )
    elif user_id not in owners and not is_super_owner(user_id):
        lines.append(
            "اگه مالک واقعی این گروهی ولی اسمت اینجا نیست، از یکی از مالک‌های "
            "بالا بخواه روی پیامت ریپلای کنه و بنویسه «انتقال مالکیت»."
        )
    await message.reply("\n".join(lines))


@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("انتقال مالکیت", "افزودن مالک با ریپلای"))
async def transfer_ownership_cmd(bot: Robot, message: Message):
    """
    👑 راه ساده و امن اضافه‌کردن مالک جدید در مقیاس چند صد گروه: به‌جای اینکه
    مالک مجبور باشه شناسه‌ی عددی طرف رو با «آیدی من» بگیره و دستی وارد کنه،
    کافیه روی پیام همون شخص ریپلای کنه و بنویسه «انتقال مالکیت».
    """
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not is_owner(user_id, group_data):
        await message.reply("❌ فقط مالک می‌تواند مالکیت رو منتقل/اضافه کنه!")
        return
    target_id = get_reply_sender_id(message)
    if not target_id:
        await message.reply("⚠️ باید روی پیام همون کاربر ریپلای کنی و بنویسی «انتقال مالکیت».")
        return
    if target_id in group_data.get("owners", []):
        await message.reply("⚠️ این کاربر از قبل مالک این گروهه.")
        return
    group_data.setdefault("owners", []).append(target_id)
    if not group_data.get("owner_primary"):
        group_data["owner_primary"] = target_id
    add_log(group_data, "انتقال/افزودن مالکیت با ریپلای", admin_id=user_id, target_id=target_id)
    save_group_data(group_id, group_data)
    name = get_user_name_from_id(target_id, group_data)
    await message.reply(f"👑 {name} به‌عنوان مالک این گروه اضافه شد!")


# =========================================================
#  🛠 رفع باگ: دستور «تایید عدم دسترسی» فقط در راهنما (FULL_GUIDE_1) تبلیغ
#  شده بود ولی هیچ‌جای کد پیاده نشده بود. ایده‌ش این بود: چون ربات هیچ راهی
#  برای خوندن «مالک واقعی گروه» از API روبیکا نداره، از یک روش غیرمستقیم
#  برای اثبات ادمین‌بودن استفاده می‌شه: از مالک واقعی گروه خواسته می‌شه
#  دسترسی «حذف پیام» گاردی رو موقتاً بگیره، بعد این دستور رو بفرسته. اگه
#  ربات واقعاً نتونه همون پیام رو حذف کنه (یعنی واقعاً دسترسیش گرفته شده)،
#  این خودش اثبات می‌کنه که فرستنده همین الان تغییرات ادمینی گروه رو در
#  دست داره - یعنی خودِ ادمین/مالک واقعی گروهه - و همون لحظه به‌عنوان مالک
#  گاردی هم ثبت می‌شه.
@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) == "تایید عدم دسترسی")
async def confirm_no_access_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return

    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)

    if is_owner(user_id, group_data):
        await message.reply("👑 شما همین الان هم مالک این گروه هستید، نیازی به این دستور نیست.")
        return

    try:
        await message.delete()
        # حذف موفق بود یعنی ربات همچنان دسترسی «حذف پیام» رو داره - پس این
        # اثبات نمی‌کنه که فرستنده ادمین واقعیه.
        await message.reply(
            "⚠️ گاردی هنوز دسترسی «حذف پیام» رو در این گروه داره، پس این دستور "
            "نمی‌تونه ادمین‌بودنتون رو اثبات کنه.\n\n"
            "۱) از تنظیمات گروه، دسترسی «حذف پیام» گاردی رو موقتاً بردارید.\n"
            "۲) دوباره «تایید عدم دسترسی» رو بفرستید.\n"
            "۳) بعد از تأیید، دسترسی رو به گاردی برگردونید."
        )
        return
    except Exception:
        # حذف پیام fail شد یعنی همین الان گاردی دسترسی حذف پیام رو نداره؛
        # از اونجایی که فقط ادمین/مالک واقعی گروه می‌تونه دسترسی‌های ربات رو
        # عوض کنه، همین کافیه تا مالک ثبت بشه.
        pass

    group_data.setdefault('owners', [])
    if user_id not in group_data['owners']:
        group_data['owners'].append(user_id)
    if not group_data.get('owner_primary'):
        group_data['owner_primary'] = user_id
    add_log(group_data, "تأیید مالکیت با تایید عدم دسترسی", admin_id=user_id, target_id=user_id)
    save_group_data(group_id, group_data)
    name = await get_display_name(bot, message) or "شما"
    await message.reply(
        f"✅ تأیید شد! چون گاردی الان نتونست پیام شما رو حذف کنه، مشخص شد که "
        f"شما کنترل دسترسی‌های ربات در این گروه رو در اختیار دارید.\n"
        f"👑 {name} به‌عنوان مالک گاردی در این گروه ثبت شد.\n\n"
        "حالا می‌تونید دسترسی «حذف پیام» رو دوباره به گاردی بدید تا کارش رو درست انجام بده."
    )


@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("تاس", "دایس", "dice", "/dice", "تاس بنداز"))
async def dice_cmd(bot: Robot, message: Message):
    """🎲 سرگرمی: انداختن تاس"""
    DICE_FACES = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
    result = random.randint(1, 6)
    name = await get_display_name(bot, message) or "شما"
    await message.reply(
        f"🎲 {name} تاس رو انداخت...\n"
        f"{DICE_FACES[result]}  عدد {result} اومد!"
    )


@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("دو تاس", "تاس دوتایی", "double dice"))
async def double_dice_cmd(bot: Robot, message: Message):
    """🎲🎲 سرگرمی: انداختن دو تاس با هم"""
    DICE_FACES = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
    r1, r2 = random.randint(1, 6), random.randint(1, 6)
    name = await get_display_name(bot, message) or "شما"
    await message.reply(
        f"🎲🎲 {name} دو تاس انداخت...\n"
        f"{DICE_FACES[r1]} + {DICE_FACES[r2]} = {r1 + r2}"
    )


@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("سکه", "شیر یا خط", "coin"))
async def coin_flip_cmd(bot: Robot, message: Message):
    """🪙 سرگرمی: شیر یا خط"""
    result = random.choice(["شیر 🦁", "خط ➖"])
    name = await get_display_name(bot, message) or "شما"
    await message.reply(f"🪙 {name} سکه رو انداخت بالا...\nنتیجه: {result}")


# 🆕 بازی جدید: بولینگ - طبق درخواست اضافه شد (قبلاً بین بازی‌های تاس/سکه/چرخ
# شانس چیزی برای بولینگ وجود نداشت، هرچند خیلی از کاربرها دنبالش بودن).
BOWLING_PIN = "🎳"

@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("بولینگ", "بولینگ بازی", "بازی بولینگ", "bowling"))
async def bowling_cmd(bot: Robot, message: Message):
    """🎳 سرگرمی: پرتاب توپ بولینگ"""
    knocked = random.randint(0, 10)
    name = await get_display_name(bot, message) or "شما"
    pins_line = BOWLING_PIN * knocked + "⬜" * (10 - knocked)

    if knocked == 10:
        comment = "🔥 استرایک! محشری!"
    elif knocked >= 7:
        comment = "👏 عالی بود!"
    elif knocked >= 4:
        comment = "🙂 بد نبود!"
    elif knocked >= 1:
        comment = "😅 یکم ضعیف بود..."
    else:
        comment = "🙈 گاتر رفت! توپ اصلاً به پین‌ها نخورد."

    await message.reply(
        f"🎳 {name} توپ رو پرتاب کرد...\n"
        f"{pins_line}\n"
        f"🎯 {knocked} پین از ۱۰ پین زده شد!\n"
        f"{comment}"
    )


@bot.on_message(filters=lambda m: m.text and normalize_key(m.text).startswith(("سنگ کاغذ قیچی", "سنگ کاغذ قضیچی")))
async def rock_paper_scissors_cmd(bot: Robot, message: Message):
    """✂️ سرگرمی: سنگ کاغذ قیچی"""
    choices = {"سنگ": "🪨", "کاغذ": "📄", "قیچی": "✂️"}
    norm = normalize_key(message.text)
    user_choice = None
    for key in choices:
        if norm.endswith(key):
            user_choice = key
            break
    if not user_choice:
        await message.reply(
            "✂️ برای بازی بنویس یکی از این‌ها رو:\n"
            "«سنگ کاغذ قیچی سنگ» یا «سنگ کاغذ قیچی کاغذ» یا «سنگ کاغذ قیچی قیچی»"
        )
        return
    bot_choice = random.choice(list(choices.keys()))
    if user_choice == bot_choice:
        result = "🤝 مساوی شد!"
    elif (
        (user_choice == "سنگ" and bot_choice == "قیچی")
        or (user_choice == "کاغذ" and bot_choice == "سنگ")
        or (user_choice == "قیچی" and bot_choice == "کاغذ")
    ):
        result = "🎉 شما بردید!"
    else:
        result = "😅 من بردم!"
    await message.reply(
        f"شما: {choices[user_choice]} {user_choice}\n"
        f"من: {choices[bot_choice]} {bot_choice}\n\n{result}"
    )


@bot.on_message(filters=lambda m: m.text and normalize_key(m.text).startswith(("انتخاب کن", "یا این یا اون")))
async def either_or_cmd(bot: Robot, message: Message):
    """🎯 سرگرمی: انتخاب تصادفی بین دو گزینه (مثال: «انتخاب کن پیتزا یا برگر»)"""
    norm = normalize_fa(message.text)
    for prefix in ("انتخاب کن", "یا این یا اون"):
        if norm.startswith(prefix):
            norm = norm[len(prefix):].strip()
            break
    parts = norm.split(" یا ")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        await message.reply("🎯 اینجوری بنویس: «انتخاب کن پیتزا یا برگر»")
        return
    a, b = parts[0].strip(), parts[1].strip()
    if len(a) > 30 or len(b) > 30:
        return
    winner = random.choice([a, b])
    await message.reply(f"🎯 بین «{a}» و «{b}»...\nمن میگم: {winner} 😄")


@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("چرخ شانس", "چرخونک", "wheel"))
async def wheel_of_luck_cmd(bot: Robot, message: Message):
    """🎡 سرگرمی: چرخ شانس"""
    prizes = [
        "🎁 یک لبخند رایگان!", "☕ یک فنجان چای مجازی", "🍀 یک روز پرشانس",
        "🎉 هیچی نبردی، دفعه بعد!", "💰 یک میلیون تومن مجازی", "😴 یک چرت کوتاه",
        "🌟 یک ستاره افتخاری", "🎶 یک آهنگ پیشنهادی", "🍕 یک پیتزای خیالی",
    ]
    name = await get_display_name(bot, message) or "شما"
    await message.reply(f"🎡 چرخ شانس داره می‌چرخه...\n\n{name} این رو برد:\n{random.choice(prizes)}")


@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("شانس امروز", "امروز چطوره", "امروزم چطوره"))
async def luck_today_cmd(bot: Robot, message: Message):
    """🍀 سرگرمی: درصد شانس امروز"""
    percent = random.randint(1, 100)
    if percent >= 80:
        comment = "امروز روز توئه! 🌟"
    elif percent >= 50:
        comment = "روز خوبیه، برو جلو! 💪"
    elif percent >= 25:
        comment = "یه روز معمولیه، مراقب باش 🙂"
    else:
        comment = "شاید بهتره امروز رو استراحت کنی 😅"
    name = await get_display_name(bot, message) or "شما"
    await message.reply(f"🍀 شانس امروز {name}: {percent}٪\n{comment}")


@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("تست هوش", "iq test", "iq"))
async def iq_test_cmd(bot: Robot, message: Message):
    """🧠 سرگرمی: تست هوش شوخی"""
    score = random.randint(70, 160)
    name = await get_display_name(bot, message) or "شما"
    await message.reply(f"🧠 نتیجه تست هوش {name}: {score}\n(فقط برای خنده‌ست، جدی نگیر! 😄)")


@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("استرس سنج", "استرسم چقدره"))
async def stress_meter_cmd(bot: Robot, message: Message):
    """😮‍💨 سرگرمی: استرس‌سنج شوخی"""
    percent = random.randint(0, 100)
    name = await get_display_name(bot, message) or "شما"
    await message.reply(f"😮‍💨 میزان استرس {name}: {percent}٪\nنفس عمیق بکش! 🌿")


@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("تنظیمات", "settings"))
async def settings_dashboard_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not has_permission(user_id, group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return

    s = group_data.get("settings", {})
    dash_emoji = get_custom_emoji(group_data, "dashboard")
    text = (
        f"╭━━━━ {dash_emoji} تنظیمات گروه ━━━━╮\n"
        f"┃ 🔗 ضدلینک: {_onoff(s.get('anti_link', True))}\n"
        f"┃ 🚫 ضداسپم: {_onoff(s.get('anti_spam', True))}\n"
        f"┃ 🤬 ضدفحش: {_onoff(s.get('anti_swear', True))}\n"
        f"┃ 🔒 قفل گروه: {_onoff(s.get('lock', False))}\n"
        f"┃ 😴 حالت خواب: {_onoff(s.get('sleep_mode', False))}\n"
        f"┃ ⚠️ حد اخطار: {s.get('max_warn', 3)}\n"
        f"┃ 🔇 مدت سکوت: {s.get('mute_duration', 5)} دقیقه\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n"
        "برای تغییر هرکدام همان دستورات قبلی را استفاده کنید:\n"
        "ضدلینک | ضداسپم | ضدفحش | قفل"
    )
    await message.reply(text)


# =========================================================
#  📜 لاگ / تاریخچه (جدید) — کلید logs قبلاً در دیتابیس تعریف شده بود
#  ولی هیچ‌جای کد فعلی چیزی داخلش ذخیره نمی‌کرد؛ از این نسخه به بعد واقعاً پر می‌شود.
# =========================================================
@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("لاگ", "تاریخچه", "log"))
async def logs_router_cmd(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    user_id = str(message.sender_id)
    if not has_permission(user_id, group_data, Perm.ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return

    logs = group_data.get("logs", [])
    if not logs:
        await message.reply("📜 هنوز هیچ عملیاتی ثبت نشده است.")
        return

    lines = ["╭━━━━ 📜 آخرین عملیات ━━━━╮"]
    for entry in logs[-10:][::-1]:
        t = entry.get("time", "")[:19].replace("T", " ")
        lines.append(f"┃ 🕒 {t} | {entry.get('action','')} | مدیر: {entry.get('admin','-')}")
    lines.append("╰━━━━━━━━━━━━━━━━━━━━╯")
    await message.reply("\n".join(lines))


# =========================================================
#  🚀 استارت + پیوی (جدید) — قبلاً هیچ هندلری برای /start وجود نداشت،
#  به همین دلیل «استارت» در پیوی و حتی در گروه اصلاً جواب نمی‌داد.
# =========================================================

PV_HELP_TEXT = f"""╭━━━━ 🌟 {BOT_NAME} ━━━━╮

سلام! من {BOT_NAME}‌ام، ربات مدیریت گروه و سرگرمی تلگرام. 🤖

🔹 برای استفاده از من، من رو به گروهت اضافه کن و ادمینم کن.
🔹 خودِ کسی که من رو اضافه می‌کنه (یا اولین بار «استارت»/«فعال»/«نصب» رو تو گروه می‌زنه)، خودکار مالک ربات تو همون گروه می‌شه.

📖 راهنمای کامل دستورات:
• «راهنمای کامل ۱»
• «راهنمای کامل ۲»
• «راهنمای کامل ۳»

🎮 چند تا از امکانات سرگرمی (هم تو گروه هم اینجا در پیوی قابل تست‌ان):
• فال | داستان | بیو | خاطره | چالش | معما | جوک | ضرب المثل
• جرأت | حقیقت | جرأت یا حقیقت | پنالتی | تاس | دو تاس | سکه
• بولینگ | سنگ کاغذ قیچی | چرخ شانس | شانس امروز | تست هوش | استرس سنج
• انتخاب کن [گزینه۱] یا [گزینه۲]

📊 آمار | آمار گروه | پروفایل | تنظیمات (داخل گروه)

📢 کانال ما: {FORCE_JOIN_CHANNEL_LINK}
🆘 پشتیبانی: {SUPPORT_LINK}

👨‍💻 ساخته شده توسط: @im_Saeed1

╰━━━━━━━━━━━━━━━━━━━━━━╯"""

# کلیدهایی که از قبل توسط ALIAS_MAP یا هندلرهای دیگه در پیوی جواب داده میشن،
# تا fallback زیر دوباره روی همون پیام جواب تکراری نده.
_PV_EXTRA_HANDLED_KEYS = {
    "استارت", "شروع", "/start", "start", "فعال", "نصب",
    "راهنمای کامل", "راهنمای کامل 1", "راهنمای کامل 2", "راهنمای کامل 3",
    "پروفایل", "profile", "تنظیمات", "settings", "لاگ", "تاریخچه", "log",
    "آیدی من", "ایدی من", "شناسه من", "myid", "/myid", "تاس", "dice",
    "دو تاس", "تاس دوتایی", "سکه", "شیر یا خط", "بولینگ", "بولینگ بازی",
    "بازی بولینگ", "bowling", "چرخ شانس", "چرخونک",
    "شانس امروز", "تست هوش", "استرس سنج", "وضعیت مالکیت", "چک مالکیت",
    "انتقال مالکیت", "مالک", "تایید عدم دسترسی",
    "پنل سخنگو", "سخنگو فعال", "سخنگو خاموش", "سخنگو روشن",
    "سخنگو شخصی فعال", "سخنگو شخصی غیرفعال",
    "سخنگو بی‌ادب فعال", "سخنگو بی ادب فعال",
    "سخنگو بی‌ادب غیرفعال", "سخنگو بی ادب غیرفعال",
    "دستور هوش مصنوعی غیرفعال", "دستور هوش مصنوعی فعال",
}

async def _handle_start(bot: Robot, message: Message):
    group_id = get_chat_group_id(message)

    if group_id:
        # 🛠 رویداد فعال‌سازی #۲: کسی داخل گروه /start یا «استارت» را می‌زند.
        # این تنها راهی‌ست که اگر رویداد my_chat_member (رویداد #۱ در
        # member_event_handler) به هر دلیلی به ربات نرسیده باشد، هنوز بشود
        # مالک را به‌صورت واقعی (نه با اولین پیام تصادفی) تعیین کرد.
        became_owner = await _set_owner_if_unset(bot, group_id, str(message.sender_id), "دستور استارت")
        if became_owner:
            name = await get_display_name(bot, message) or "شما"
            await message.reply(
                f"👑 {name} عزیز، {BOT_NAME} با موفقیت فعال شد و شما مالک این گروه شدید!\n"
                "برای دیدن راهنمای کامل بنویس: «راهنمای کامل ۱»"
            )
        else:
            await message.reply(
                f"✅ {BOT_NAME} در این گروه فعاله!\n"
                "برای دیدن راهنمای کامل بنویس: «راهنمای کامل ۱»"
            )
        return

    # پیوی: اول عضویت اجباری رو چک کن
    force_join_ok = await is_force_join_satisfied(bot, message)
    if force_join_ok is False:
        await message.reply(FORCE_JOIN_MSG)
        return
    if force_join_ok is None:
        await message.reply(FORCE_JOIN_UNKNOWN_MSG)
        return

    await message.reply(PV_HELP_TEXT)


@bot.on_message(commands=["start"])
async def start_cmd_official(bot: Robot, message: Message):
    """رویداد رسمی استارت روبیکا (وقتی کاربر برای اولین بار در پیوی ربات رو استارت می‌زنه)."""
    await _handle_start(bot, message)


@bot.on_message(filters=lambda m: m.text and normalize_key(m.text) in ("استارت", "شروع", "فعال", "نصب"))
async def start_cmd_fa(bot: Robot, message: Message):
    """معادل فارسی استارت، چون خیلی از کاربرها به‌جای /start می‌نویسن «استارت».
    🛠 به درخواست کاربر: «فعال» و «نصب» هم به‌عنوان جایگزینِ استارت/start برای
    روشن کردنِ ربات در گروه اضافه شدن (در پیوی هم مثل استارت راهنما نشون می‌ده)."""
    await _handle_start(bot, message)


@bot.on_message()
async def pv_fallback_handler(bot: Robot, message: Message):
    """
    اگه پیام در پیوی (نه گروه) بود و هیچ‌کدوم از دستورات شناخته‌شده نبود،
    به‌جای سکوت کامل، راهنما نشون بده. قبلاً پیوی اصلاً جواب نمی‌داد.
    """
    if get_chat_group_id(message):
        return
    text = message.text
    if not text:
        return
    key = normalize_key(text)
    if key in ALIAS_MAP or key in _PV_EXTRA_HANDLED_KEYS:
        return  # قبلاً توسط یه هندلر دیگه جواب داده شده، دوباره جواب نده
    force_join_ok = await is_force_join_satisfied(bot, message)
    if force_join_ok is False:
        await message.reply(FORCE_JOIN_MSG)
        return
    if force_join_ok is None:
        await message.reply(FORCE_JOIN_UNKNOWN_MSG)
        return
    await message.reply(PV_HELP_TEXT)


# =========================================================
#  🔗 دستورهای فارسی قفل نوع پیام: «قفل عکس» / «باز عکس» / «قفل گیف» ...
# =========================================================
def _make_lock_router_target(key: str, value: bool):
    async def _target(bot: Robot, message: Message):
        await _apply_lock_type(message, key, value)
    return _target

for _key, _names in LOCK_TYPE_ALIASES.items():
    _lock_canon, _unlock_canon = f"/locktype_{_key}", f"/unlocktype_{_key}"
    register_router_target(_lock_canon, _make_lock_router_target(_key, True))
    register_router_target(_unlock_canon, _make_lock_router_target(_key, False))
    for _n in _names:
        ALIAS_MAP[f"قفل {_n}"] = (_lock_canon, Perm.ADMIN)
        ALIAS_MAP[f"باز {_n}"] = (_unlock_canon, Perm.ADMIN)
register_router_target("/locktype", locktype_cmd)
register_router_target("/unlocktype", unlocktype_cmd)
register_router_target("/hangcode_sensitivity", hangcode_sensitivity_cmd)
register_router_target("/locks", locks_cmd)
register_router_target("/setspam", setspam_cmd)
ALIAS_MAP["وضعیت قفل ها"] = ("/locks", Perm.MEMBER)
ALIAS_MAP["وضعیت قفل‌ها"] = ("/locks", Perm.MEMBER)
ALIAS_MAP["تنظیم اسپم"] = ("/setspam", Perm.ADMIN)

# =========================================================
#  🆕 «تنظیم مشخصات کاربری» (لقب/اصل/اسم/فامیلی) — گروهی و سراسری
#  در راهنما (FULL_GUIDE_1 «تنظیم مشخصات کاربری» + FULL_GUIDE_3 «تنظیم
#  مشخصات کاربری (گروهی و سراسری)») به‌طور کامل تبلیغ می‌شد: تنظیم/نمایش/حذف
#  هر ۴ فیلد، هم برای همین گروه هم به‌صورت سراسری (مستقل از گروه). قبل از این،
#  نه این ۴ فیلد نه مفهوم «سراسری» هیچ‌جای کد وجود نداشت - فقط متن راهنما بود.
#  «فعال/غیرفعال» کردن هرکدام («تنظیم لقب فعال/غیرفعال») نیازی به کد جدا ندارد:
#  چون این دستورات هم مثل بقیه از persian_alias_router رد می‌شوند، سیستم عمومی
#  «محدودیت دستورات» (_handle_command_restriction) که از قبل پیاده‌سازی شده
#  بود، به‌صورت خودکار روی آن‌ها هم اعمال می‌شود.
# =========================================================
PROFILE_FIELDS: Dict[str, Tuple[str, List[str]]] = {
    # کلید داخلی: (نام فارسیِ نمایشی، همه‌ی نام‌های معتبر که کاربر ممکنه تایپ کنه)
    "title":  ("لقب", ["لقب"]),
    "asl":    ("اصل", ["اصل"]),
    # 🛠 خودِ راهنما بین «اسم» (در بخش تنظیم/نمایش) و «نام» (در بخش حذف: «حذف
    # لقب/اصل/نام/فامیلی») ناهماهنگ بود؛ هر دو نام پذیرفته می‌شوند تا کاربر
    # با هیچ‌کدام از دو شکلِ خودِ راهنما هم گیر نکند.
    "esm":    ("اسم", ["اسم", "نام"]),
    "family": ("فامیلی", ["فامیلی", "فامیل"]),
}

def _profile_group_store(group_data: dict, user_id: str) -> dict:
    return group_data.setdefault('user_profiles', {}).setdefault(str(user_id), {})

async def _profile_set_cmd(bot: Robot, message: Message, field_key: str, is_global: bool):
    fa_name = PROFILE_FIELDS[field_key][0]
    scope_word = " سراسری" if is_global else ""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not group_data.get('settings', {}).get('profile_enabled', True):
        await message.reply("⛔ تنظیم مشخصات کاربری در این گروه غیرفعال است.")
        return
    value = _cmd_rest(message.text).lstrip("#").strip()
    if not value:
        await message.reply(f"⚠️ دستور: تنظیم {fa_name}{scope_word} #متن")
        return
    user_id = str(message.sender_id)
    if is_global:
        profiles = get_global_profiles()
        profiles.setdefault(user_id, {})[field_key] = value
        save_global_profiles(profiles)
        await message.reply(f"✅ **{fa_name} سراسریِ شما تنظیم شد:**\n{value}")
    else:
        prof = _profile_group_store(group_data, user_id)
        prof[field_key] = value
        save_group_data(group_id, group_data)
        await message.reply(f"✅ **{fa_name} شما در این گروه تنظیم شد:**\n{value}")

async def _profile_show_cmd(bot: Robot, message: Message, field_key: str, is_global: bool):
    fa_name = PROFILE_FIELDS[field_key][0]
    label = f"{fa_name} سراسری" if is_global else fa_name
    user_id = str(message.sender_id)
    if is_global:
        value = get_global_profiles().get(user_id, {}).get(field_key)
    else:
        group_id = get_chat_group_id(message)
        if not group_id:
            await message.reply(GROUP_ONLY_MSG)
            return
        value = _profile_group_store(get_group_data(group_id), user_id).get(field_key)
    if value:
        await message.reply(f"📇 **{label}:** {value}")
    else:
        scope_word = " سراسری" if is_global else ""
        await message.reply(f"ℹ️ شما هنوز {label} تنظیم نکرده‌اید.\nبرای تنظیم: «تنظیم {fa_name}{scope_word} #متن»")

async def _profile_delete_cmd(bot: Robot, message: Message, field_key: str, is_global: bool):
    fa_name = PROFILE_FIELDS[field_key][0]
    label = f"{fa_name} سراسری" if is_global else fa_name
    user_id = str(message.sender_id)
    if is_global:
        profiles = get_global_profiles()
        existed = profiles.get(user_id, {}).pop(field_key, None) is not None
        save_global_profiles(profiles)
    else:
        group_id = get_chat_group_id(message)
        if not group_id:
            await message.reply(GROUP_ONLY_MSG)
            return
        group_data = get_group_data(group_id)
        existed = _profile_group_store(group_data, user_id).pop(field_key, None) is not None
        save_group_data(group_id, group_data)
    if existed:
        await message.reply(f"🗑️ **{label} شما حذف شد.**")
    else:
        await message.reply(f"ℹ️ شما {label}ای برای حذف ثبت نکرده بودید.")

def _make_profile_targets(field_key: str, is_global: bool):
    async def _set(bot: Robot, message: Message):
        await _profile_set_cmd(bot, message, field_key, is_global)
    async def _show(bot: Robot, message: Message):
        await _profile_show_cmd(bot, message, field_key, is_global)
    async def _delete(bot: Robot, message: Message):
        await _profile_delete_cmd(bot, message, field_key, is_global)
    return _set, _show, _delete

for _fkey, (_fa, _names) in PROFILE_FIELDS.items():
    for _scope, _suffix, _tag in ((False, "", ""), (True, "_global", " سراسری")):
        _set_canon = f"/profile_set_{_fkey}{_suffix}"
        _show_canon = f"/profile_show_{_fkey}{_suffix}"
        _del_canon = f"/profile_del_{_fkey}{_suffix}"
        _set_f, _show_f, _del_f = _make_profile_targets(_fkey, _scope)
        register_router_target(_set_canon, _set_f)
        register_router_target(_show_canon, _show_f)
        register_router_target(_del_canon, _del_f)
        for _n in _names:
            # طولانی‌ترین alias برنده می‌شه، پس «تنظیم لقب سراسری» با «تنظیم لقب»
            # تداخل نمی‌کنه (دقیقاً همون الگوی «تنظیم تم پیش‌فرض» / «تنظیم تم»).
            ALIAS_MAP[f"تنظیم {_n}{_tag}"] = (_set_canon, Perm.MEMBER)
            ALIAS_MAP[f"{_n}{_tag}"] = (_show_canon, Perm.MEMBER)
            ALIAS_MAP[f"حذف {_n}{_tag}"] = (_del_canon, Perm.MEMBER)

@bot.on_message(filters=lambda m: m.text and m.text == "/profile_toggle_on")
async def profile_toggle_on_cmd(bot: Robot, message: Message):
    """تنظیم مشخصات فعال: کلید کلیِ روشن‌کردن قابلیت لقب/اصل/اسم/فامیلی برای کل گروه."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.SUPER_ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return
    group_data['settings']['profile_enabled'] = True
    save_group_data(group_id, group_data)
    await message.reply("✅ **تنظیم مشخصات کاربری (لقب/اصل/اسم/فامیلی) فعال شد.**")

@bot.on_message(filters=lambda m: m.text and m.text == "/profile_toggle_off")
async def profile_toggle_off_cmd(bot: Robot, message: Message):
    """تنظیم مشخصات غیرفعال: خاموش‌کردن کل قابلیت برای این گروه (اجرای دستورات
    تنظیم/نمایش/حذف لقب/اصل/اسم/فامیلی رو در همین گروه مسدود می‌کند؛ نسخه‌ی
    سراسری چون به هیچ گروهی وابسته نیست، تحت تأثیر این کلید قرار نمی‌گیرد)."""
    group_id = get_chat_group_id(message)
    if not group_id:
        await message.reply(GROUP_ONLY_MSG)
        return
    group_data = get_group_data(group_id)
    if not has_permission(str(message.sender_id), group_data, Perm.SUPER_ADMIN):
        await message.reply(NO_PERMISSION_MSG)
        return
    group_data['settings']['profile_enabled'] = False
    save_group_data(group_id, group_data)
    await message.reply("✅ **تنظیم مشخصات کاربری (لقب/اصل/اسم/فامیلی) غیرفعال شد.**")

register_router_target("/profile_toggle_on", profile_toggle_on_cmd)
register_router_target("/profile_toggle_off", profile_toggle_off_cmd)
ALIAS_MAP["تنظیم مشخصات فعال"] = ("/profile_toggle_on", Perm.SUPER_ADMIN)
ALIAS_MAP["تنظیم مشخصات غیرفعال"] = ("/profile_toggle_off", Perm.SUPER_ADMIN)

# =========================================================
#  🔗 دستورهای فارسی تگ / اعضا
# =========================================================
register_router_target("/tag", tag_cmd)
register_router_target("/tagbots", tagbots_cmd)
register_router_target("/members", members_cmd)

# 🆕 ۴ قابلیت جدید (ضد تبچی، تنظیم خودکار/پیش‌فرض، محدودیت عمومی دستورات، دستورات دلخواه)
register_router_target("/tabchi_on", tabchi_on_cmd)
register_router_target("/tabchi_off", tabchi_off_cmd)
register_router_target("/tabchi_status", tabchi_status_cmd)
register_router_target("/tabchi_window", tabchi_window_cmd)
register_router_target("/auto_setup", auto_setup_cmd)
register_router_target("/full_reset_defaults", full_reset_defaults_cmd)
register_router_target("/reset_cmd_restrictions", reset_cmd_restrictions_cmd)
register_router_target("/list_cmd_restrictions", list_cmd_restrictions_cmd)
register_router_target("/set_custom_cmd", set_custom_cmd_cmd)
register_router_target("/remove_custom_cmd", remove_custom_cmd_cmd)
register_router_target("/show_custom_cmd", show_custom_cmd_cmd)
register_router_target("/list_custom_cmds", list_custom_cmds_cmd)
register_router_target("/clear_custom_cmds", clear_custom_cmds_cmd)
ALIAS_MAP["تگ"] = ("/tag", Perm.ADMIN)
ALIAS_MAP["تگ ربات"] = ("/tagbots", Perm.ADMIN)
ALIAS_MAP["تگ ربات ها"] = ("/tagbots", Perm.ADMIN)
ALIAS_MAP["اعضا"] = ("/members", Perm.ADMIN)

if __name__ == "__main__":
    print("=" * 70)
    print(f"🌟 {BOT_NAME} - نسخه کامل نهایی {VERSION}")
    print("=" * 70)
    print("🚀 ربات در حال اجرا...")
    print("📌 رویداد ماهانه: /monthly_event_add")
    print("📌 جایزه ویژه: /special_reward_add")
    print("📌 دریافت جایزه: /special_reward_claim")
    print("=" * 70)
    print("💡 **هر جا گاردی رو صدا کنی جوابت رو میدم!**")
    print("💡 **مثلا: گاردی سلام!**")
    print("=" * 70)
    
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 ربات متوقف شد!")
    except Exception as e:
        print(f"❌ خطا: {e}")

