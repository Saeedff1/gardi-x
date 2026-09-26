# -*- coding: utf-8 -*-
"""
telegram_compat.py
===================
لایه‌ی سازگاری بین ربات «گاردی» و تلگرام واقعی، روی کتابخانه‌ی python-telegram-bot (نسخه‌ی ۲۰+، async).

نصب پیش‌نیاز (توی Pydroid3 هم با همین دستور):
    pip install "python-telegram-bot>=20,<22" --break-system-packages

همه‌ی موارد زیر روی API واقعی تلگرام کار می‌کنند (برخلاف روبیکا، تلگرام همه‌ی این‌ها را دارد):
ارسال/حذف/پین پیام، بن/آنبن/کیک، سکوت‌کردن (restrict)، گرفتن لیست ادمین‌ها،
تعداد اعضا، وضعیت عضو، لینک دعوت، و رویداد ورود/خروج/تغییر وضعیت عضو (chat_member).
"""

import time
import logging
import html as _html
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Any, Dict, Callable

from telegram import Update, ChatPermissions
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters as ptb_filters,
)
from telegram.error import TelegramError

_log = logging.getLogger("telegram_compat")

TELEGRAM_MAX_TEMP_MINUTES = 366 * 24 * 60  # تلگرام بن/سکوت موقت را حداکثر تا ۳۶۶ روز قبول می‌کند


def until_timestamp(duration_minutes: Optional[int]):
    """python-telegram-bot برای until_date یک datetime (یا unix ts) می‌خواهد."""
    if duration_minutes is None:
        return None
    return datetime.now() + timedelta(minutes=int(duration_minutes))


def mention_html(user_id, name: str) -> str:
    safe_name = _html.escape(name or "کاربر")
    return f'<a href="tg://user?id={user_id}">{safe_name}</a>'


@dataclass
class ActionResult:
    ok: bool
    error: Optional[str] = None
    warning: Optional[str] = None
    code: Optional[str] = None
    data: Any = None

    def __bool__(self):
        return bool(self.ok)

    def get(self, key, default=None):
        return getattr(self, key, default)


@dataclass
class MemberEvent:
    chat_id: Any = None
    user: dict = field(default_factory=dict)
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    actor_id: Optional[int] = None
    source: Optional[str] = None  # "chat_member" یا "service"


class Message:
    """پوشش دور telegram.Message برای هم‌نام‌شدن ویژگی‌ها با چیزی که کد اصلی انتظار دارد."""

    def __init__(self, raw, bot: "Robot"):
        self._raw = raw
        self._bot = bot

    def __getattr__(self, item):
        return getattr(self._raw, item, None)

    @property
    def sender_id(self):
        return self._raw.from_user.id if self._raw.from_user else None

    @property
    def sender_first_name(self):
        return self._raw.from_user.first_name if self._raw.from_user else None

    @property
    def text(self):
        return self._raw.text or self._raw.caption

    @property
    def chat_id(self):
        return self._raw.chat_id

    @property
    def chat_type(self):
        """'private' / 'group' / 'supergroup' / 'channel'"""
        return self._raw.chat.type if self._raw.chat else None

    @property
    def reply_to_message(self):
        rtm = self._raw.reply_to_message
        return Message(rtm, self._bot) if rtm else None

    async def reply(self, text, html: bool = False, **kwargs):
        try:
            pm = kwargs.pop("parse_mode", None)
            parse_mode = ParseMode.HTML if (html or pm == "html") else pm
            res = await self._raw.reply_text(text, parse_mode=parse_mode, **kwargs)
            self._bot._notify_sent(self._raw.chat_id, getattr(res, "message_id", None))
            return ActionResult(True, data=res)
        except TelegramError as e:
            return ActionResult(False, error=str(e), code="reply_failed")

    async def delete(self):
        try:
            await self._raw.delete()
            return ActionResult(True)
        except TelegramError as e:
            return ActionResult(False, error=str(e), code="delete_failed")


class Robot:
    def __init__(self, token: str, **kwargs):
        self.app: Application = ApplicationBuilder().token(token).build()
        self._bot_id_cache: Optional[int] = None
        self._group_counter = 0  # هر on_message یه handler group جدا می‌گیره تا ترتیب ثبت حفظ بشه
        # 🛠 قبلاً پیام‌هایی که خودِ ربات می‌فرستاد (reply/send_text) هیچ‌جا ثبت
        # نمی‌شدند (چون فقط پیام‌های ورودی کاربرها روی on_message هندل می‌شدن)،
        # در نتیجه دستور «پاکسازی» فقط پیام کاربرها رو پاک می‌کرد و پیام‌های
        # خودِ ربات (تاییدها، پاسخ‌ها و...) جا می‌موندن. الان هر ارسال موفق
        # (reply یا send_text) این callback رو صدا می‌زنه تا فایل اصلی بتونه
        # پیام رو هم توی RECENT_MESSAGES ثبت کنه و قابل‌حذف بشه.
        self.on_sent_message: Optional[Callable[[Any, Optional[int]], None]] = None

    def __getattr__(self, item):
        # هر چیزی که اینجا صراحتاً تعریف نشده، از self.app.bot گرفته می‌شود (telegram.Bot واقعی)
        return getattr(self.app.bot, item)

    def _notify_sent(self, chat_id, message_id: Optional[int]):
        if self.on_sent_message is None or message_id is None:
            return
        try:
            self.on_sent_message(chat_id, message_id)
        except Exception as e:
            _log.warning("on_sent_message callback خطا داد: %s", e)

    @property
    def bot_id(self) -> Optional[int]:
        return self._bot_id_cache or (self.app.bot.id if self.app.bot else None)

    # ---------------- هندلرها ----------------
    def on_message(self, filters: Optional[Callable] = None, commands: Optional[list] = None):
        """
        هم filters=lambda m: ... و هم commands=["start", ...] پشتیبانی می‌شود
        (چون در خود فایل اصلی هر دو سبک استفاده شده‌اند).
        """
        cmd_set = {c.lstrip("/").lower() for c in commands} if commands else None

        def _cmd_matches(msg) -> bool:
            text = msg.text or ""
            if not text.startswith("/"):
                return False
            first_word = text.split()[0][1:].split("@")[0].lower()
            return first_word in cmd_set

        def wrapper(func):
            async def ptb_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if update.effective_message is None:
                    return
                msg = Message(update.effective_message, self)
                if cmd_set is not None and not _cmd_matches(msg):
                    return
                if filters is not None:
                    try:
                        if not filters(msg):
                            return
                    except Exception as e:
                        _log.warning("filter خطا داد: %s", e)
                        return
                await func(self, msg)

            self._group_counter += 1
            self.app.add_handler(MessageHandler(ptb_filters.ALL, ptb_callback), group=self._group_counter)
            return func

        return wrapper

    def on_member_update(self):
        def wrapper(func):
            async def ptb_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
                cmu = update.chat_member or update.my_chat_member
                if cmu is None:
                    return
                new_u = cmu.new_chat_member.user
                ev = MemberEvent(
                    chat_id=cmu.chat.id,
                    user={
                        "id": new_u.id,
                        "is_bot": new_u.is_bot,
                        "first_name": new_u.first_name,
                        "username": new_u.username,
                    },
                    old_status=cmu.old_chat_member.status if cmu.old_chat_member else None,
                    new_status=cmu.new_chat_member.status,
                    actor_id=cmu.from_user.id if cmu.from_user else None,
                    source="chat_member",
                )
                await func(self, ev)

            self.app.add_handler(ChatMemberHandler(ptb_callback, ChatMemberHandler.ANY_CHAT_MEMBER))
            return func

        return wrapper

    # 🆕 سیستم خطای سراسری: قبلاً هیچ‌جا application.add_error_handler صدا زده
    # نمی‌شد. یعنی اگه یکی از صدها هندلر خطا می‌داد، python-telegram-bot فقط
    # یک لاگ داخلی (که هیچ‌کس نمی‌دید) ثبت می‌کرد و کاربر برای همیشه بدون هیچ
    # جوابی می‌موند - نه خطایی نشون داده می‌شد، نه صاحب ربات خبردار می‌شد.
    # این متد اجازه می‌ده فایل اصلی یک callback خودش رو به‌عنوان error handler
    # واقعیِ Application ثبت کنه (چیزی که از طریق self.app.bot در دسترس نیست،
    # چون add_error_handler متعلق به Application‌ـه نه به خودِ Bot).
    def set_error_handler(self, callback):
        self.app.add_error_handler(callback)


    def run(self):
        return self.app.run_polling(allowed_updates=Update.ALL_TYPES)

    # ---------------- پیام‌رسانی ----------------
    async def send_text(self, chat_id, text, html: bool = False, reply_to_message_id=None, **kwargs):
        try:
            res = await self.app.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML if html else None,
                reply_to_message_id=reply_to_message_id,
                **kwargs,
            )
            self._notify_sent(chat_id, getattr(res, "message_id", None))
            return ActionResult(True, data=res)
        except TelegramError as e:
            return ActionResult(False, error=str(e), code="send_failed")

    async def delete_message(self, chat_id, message_id):
        try:
            await self.app.bot.delete_message(chat_id, message_id)
            return ActionResult(True)
        except TelegramError as e:
            return ActionResult(False, error=str(e), code="delete_failed")

    async def delete_message_id(self, chat_id, message_id):
        return await self.delete_message(chat_id, message_id)

    async def pin_message(self, chat_id, message_id, disable_notification: bool = False):
        try:
            await self.app.bot.pin_chat_message(chat_id, message_id, disable_notification=disable_notification)
            return ActionResult(True)
        except TelegramError as e:
            return ActionResult(False, error=str(e), code="pin_failed")

    async def unpin_message(self, chat_id, message_id):
        try:
            await self.app.bot.unpin_chat_message(chat_id, message_id)
            return ActionResult(True)
        except TelegramError as e:
            return ActionResult(False, error=str(e), code="unpin_failed")

    async def unpin_all_messages(self, chat_id):
        try:
            await self.app.bot.unpin_all_chat_messages(chat_id)
            return ActionResult(True)
        except TelegramError as e:
            return ActionResult(False, error=str(e), code="unpin_all_failed")

    # ---------------- اطلاعات کاربر/چت ----------------
    async def get_name(self, user_id, chat_id=None):
        try:
            chat = await self.app.bot.get_chat(chat_id or user_id)
            return " ".join(filter(None, [chat.first_name, chat.last_name])) or chat.title
        except TelegramError as e:
            _log.warning("get_name خطا داد (%s): %s", user_id, e)
            return None

    async def get_username(self, user_id, chat_id=None):
        try:
            chat = await self.app.bot.get_chat(chat_id or user_id)
            return chat.username
        except TelegramError as e:
            _log.warning("get_username خطا داد (%s): %s", user_id, e)
            return None

    async def resolve_username(self, username):
        try:
            chat = await self.app.bot.get_chat(username if str(username).startswith("@") else f"@{username}")
            return ActionResult(True, data=chat)
        except TelegramError as e:
            return ActionResult(False, error=str(e), code="resolve_failed")

    async def check_join(self, channel_id, user_id):
        try:
            member = await self.app.bot.get_chat_member(channel_id, user_id)
            return member.status in ("member", "administrator", "creator")
        except TelegramError as e:
            _log.warning("check_join خطا داد: %s", e)
            return False

    async def get_member_status(self, group_id, user_id):
        try:
            member = await self.app.bot.get_chat_member(group_id, user_id)
            return member.status
        except TelegramError as e:
            _log.warning("get_member_status خطا داد: %s", e)
            return None

    async def get_member_info(self, group_id, user_id):
        try:
            member = await self.app.bot.get_chat_member(group_id, user_id)
            return {
                "id": member.user.id,
                "is_bot": member.user.is_bot,
                "first_name": member.user.first_name,
                "last_name": member.user.last_name,
                "username": member.user.username,
                "status": member.status,
            }
        except TelegramError as e:
            _log.warning("get_member_info خطا داد: %s", e)
            return None

    async def get_admins(self, group_id):
        try:
            admins = await self.app.bot.get_chat_administrators(group_id)
            return [
                {"id": a.user.id, "username": a.user.username, "status": a.status, "is_bot": a.user.is_bot}
                for a in admins
            ]
        except TelegramError as e:
            _log.warning("get_admins خطا داد: %s", e)
            return []

    async def get_member_count(self, group_id):
        try:
            return await self.app.bot.get_chat_member_count(group_id)
        except TelegramError as e:
            _log.warning("get_member_count خطا داد: %s", e)
            return None

    async def get_bot_permissions(self, group_id):
        try:
            me = await self._ensure_bot_id()
            member = await self.app.bot.get_chat_member(group_id, me)
            if member.status not in ("administrator", "creator"):
                return {"is_admin": False}
            perms = {"is_admin": True}
            for attr in (
                "can_restrict_members", "can_delete_messages", "can_invite_users",
                "can_pin_messages", "can_promote_members", "can_manage_chat",
            ):
                perms[attr] = getattr(member, attr, None)
            return perms
        except TelegramError as e:
            _log.warning("get_bot_permissions خطا داد: %s", e)
            return {}

    async def get_invite_link(self, group_id):
        try:
            chat = await self.app.bot.get_chat(group_id)
            if chat.invite_link:
                return chat.invite_link
            link = await self.app.bot.export_chat_invite_link(group_id)
            return link
        except TelegramError as e:
            _log.warning("get_invite_link خطا داد: %s", e)
            return None

    async def _ensure_bot_id(self):
        if self._bot_id_cache is None:
            me = await self.app.bot.get_me()
            self._bot_id_cache = me.id
        return self._bot_id_cache

    # ---------------- مدیریت اعضا (بن/سکوت/کیک) ----------------
    async def ban_user(self, group_id, user_id, until_ts=None):
        try:
            await self.app.bot.ban_chat_member(group_id, user_id, until_date=until_ts)
            return ActionResult(True)
        except TelegramError as e:
            return ActionResult(False, error=str(e), code="ban_failed")

    async def unban_user(self, group_id, user_id):
        try:
            await self.app.bot.unban_chat_member(group_id, user_id, only_if_banned=True)
            return ActionResult(True)
        except TelegramError as e:
            return ActionResult(False, error=str(e), code="unban_failed")

    async def kick_user(self, group_id, user_id):
        """کیک = بن لحظه‌ای + آنبن فوری، تا کاربر بتونه دوباره بیاد ولی الان بیرون بشه."""
        res = await self.ban_user(group_id, user_id)
        if not res:
            return res
        return await self.unban_user(group_id, user_id)

    async def restrict_user(self, group_id, user_id, until_ts=None, **perms):
        try:
            permissions = ChatPermissions(
                can_send_messages=perms.get("can_send_messages", False),
                can_send_audios=perms.get("can_send_audios", False),
                can_send_documents=perms.get("can_send_documents", False),
                can_send_photos=perms.get("can_send_photos", False),
                can_send_videos=perms.get("can_send_videos", False),
                can_send_video_notes=perms.get("can_send_video_notes", False),
                can_send_voice_notes=perms.get("can_send_voice_notes", False),
                can_send_polls=perms.get("can_send_polls", False),
                can_send_other_messages=perms.get("can_send_other_messages", False),
                can_add_web_page_previews=perms.get("can_add_web_page_previews", False),
                can_change_info=perms.get("can_change_info", False),
                can_invite_users=perms.get("can_invite_users", False),
                can_pin_messages=perms.get("can_pin_messages", False),
            )
            await self.app.bot.restrict_chat_member(group_id, user_id, permissions=permissions, until_date=until_ts)
            return ActionResult(True)
        except TelegramError as e:
            return ActionResult(False, error=str(e), code="restrict_failed")

    async def unrestrict_user(self, group_id, user_id):
        try:
            permissions = ChatPermissions(
                can_send_messages=True, can_send_audios=True, can_send_documents=True,
                can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
                can_add_web_page_previews=True, can_change_info=False,
                can_invite_users=True, can_pin_messages=False,
            )
            await self.app.bot.restrict_chat_member(group_id, user_id, permissions=permissions)
            return ActionResult(True)
        except TelegramError as e:
            return ActionResult(False, error=str(e), code="unrestrict_failed")
