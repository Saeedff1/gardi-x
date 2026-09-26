# -*- coding: utf-8 -*-
"""
تست خودکار سیستم بکاپ/Restore (بخش ۸: مشکل #101 و #104)
==========================================================
فقط تابع خالص _validate_backup و ثابت BACKUP_SCHEMA_VERSION را از فایل
اصلی استخراج می‌کند (بدون نیاز به python-telegram-bot) و اعتبارسنجی
بکاپ‌های سالم/ناسالم/ناسازگار را تست می‌کند.

اجرا:
    python3 tests/test_backup_restore.py
"""

import ast
import sys
from pathlib import Path

# 🛠 رفع باگ: مسیر قبلی با فرض ثابت "این تست داخل یک پوشه‌ی tests/ کنار فایل
# اصلیه" ساخته می‌شد (parent.parent)، که اگر تست کنار خودِ گاردی_تلگرام.py
# اجرا بشه (نه داخل یک زیرپوشه‌ی tests/)، فایل پیدا نمی‌شه. الان چند مسیر
# محتمل رو به‌ترتیب امتحان می‌کنه: کنار خودِ تست، یک پوشه بالاتر (حالت
# tests/)، و در نهایت یک جست‌وجوی ساده در کل مسیر پروژه.
def _find_bot_file() -> Path:
    here = Path(__file__).resolve().parent
    candidates = [
        here / "گاردی_تلگرام.py",
        here.parent / "گاردی_تلگرام.py",
    ]
    for c in candidates:
        if c.exists():
            return c
    # 🛠 رفع باگ: این تست فقط دنبال «گاردی_تلگرام.py» می‌گشت، ولی فایل اصلیِ
    # پروژه با اسم دیگری («گاردی_ایکس_...py») توزیع می‌شد - یعنی خودِ تستِ
    # بکاپ/ریستور همیشه با FileNotFoundError متوقف می‌شد و هیچ‌وقت واقعاً
    # اجرا نمی‌شد (یک نمونه‌ی دیگر از «ظاهرش هست ولی پشتش خالیه»). الگوی
    # جست‌وجو الان هم «گاردی...تلگرام» و هم «گاردی...ایکس» رو می‌پذیرد.
    for base in (here, here.parent, here.parent.parent):
        matches = list(base.glob("*گاردی*تلگرام*.py")) or list(base.glob("*گاردی*ایکس*.py"))
        if matches:
            return matches[0]
    raise FileNotFoundError(
        "فایل اصلی ربات (گاردی_تلگرام.py یا گاردی_ایکس_*.py) پیدا نشد. این تست "
        "رو یا کنار خودِ فایل اصلی، یا داخل یک پوشه‌ی tests/ درست یک سطح "
        "پایین‌تر از فایل اصلی قرار بده."
    )

BOT_FILE = _find_bot_file()


def _load():
    src = BOT_FILE.read_text(encoding="utf-8")
    tree = ast.parse(src)
    ns = {"Optional": __import__("typing").Optional}
    version = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "BACKUP_SCHEMA_VERSION" for t in node.targets
        ):
            version = ast.literal_eval(node.value)
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_BACKUP_REQUIRED_KEYS" for t in node.targets
        ):
            code = ast.get_source_segment(src, node)
            exec(compile(code, str(BOT_FILE), "exec"), ns)
        if isinstance(node, ast.FunctionDef) and node.name == "_validate_backup":
            code = ast.get_source_segment(src, node)
            exec(compile(code, str(BOT_FILE), "exec"), ns)
    if version is None or "_validate_backup" not in ns:
        raise RuntimeError("BACKUP_SCHEMA_VERSION یا _validate_backup پیدا نشد.")
    ns["BACKUP_SCHEMA_VERSION"] = version
    return ns["_validate_backup"], version


def main():
    validate, current_version = _load()
    failures = []

    def check(label, data, should_be_valid):
        err = validate(data)
        ok = err is None
        if ok != should_be_valid:
            failures.append(f"❌ {label}: انتظار {'معتبر' if should_be_valid else 'نامعتبر'}, "
                             f"نتیجه: {'معتبر' if ok else 'نامعتبر'} ({err!r})")

    good = {"group_id": "1", "schema_version": current_version, "settings": {"anti_link": True}}
    check("بکاپ سالم و کامل", good, True)
    check("رشته به‌جای دیکشنری", "not a dict", False)
    check("بدون schema_version", {"group_id": "1", "settings": {}}, False)
    check("بدون group_id", {"schema_version": current_version, "settings": {}}, False)
    check("settings غایب", {"group_id": "1", "schema_version": current_version}, False)
    check("settings نوع اشتباه", {"group_id": "1", "schema_version": current_version, "settings": []}, False)
    check("نسخه‌ی Schema از آینده (ناسازگار)",
          {"group_id": "1", "schema_version": current_version + 1, "settings": {}}, False)
    check("نسخه‌ی Schema قدیمی‌تر (باید قبول شود)",
          {"group_id": "1", "schema_version": max(0, current_version - 1) if current_version > 0 else 0,
           "settings": {}}, True if current_version > 0 else True)

    if failures:
        print("\n".join(failures))
        print(f"\n{len(failures)} مورد ناموفق.")
        sys.exit(1)
    print("✅ همه‌ی تست‌های اعتبارسنجی بکاپ/Restore (بخش ۸) قبول شدند.")


if __name__ == "__main__":
    main()
