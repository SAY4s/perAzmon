"""
quiz_bot.py  —  ربات تلگرام آزمون چهارجوابی (Telegram Mini App)
================================================================================
این ربات کارهای زیر رو انجام می‌ده:
  1. وقتی کاربر /start می‌زند، دکمه‌ی باز کردن Mini App رو نشون می‌ده
  2. وقتی Mini App نتیجه‌ی آزمون رو می‌فرسته (sendData)، نتیجه رو
     خودش برای ادمین می‌فرسته (خلاصه‌ی نام، کد ملی، یوزرنیم و امتیاز)

⚠️ نکته‌ی مهم و حیاتی:
  برای اینکه Telegram.WebApp.sendData() کار کند، دکمه‌ی باز کردن
  Mini App باید از نوع KeyboardButton (ReplyKeyboardMarkup) باشد،
  نه InlineKeyboardButton. این یک محدودیت رسمی خود تلگرام است؛
  دکمه‌های Inline به‌طور قابل‌اعتماد sendData را پشتیبانی نمی‌کنند.

نصب پیش‌نیاز:
  pip install pyTelegramBotAPI

اجرا:
  python quiz_bot.py
"""

import json
import os

import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

# ═══════════════════════════════════════════════
#  ⚙️  تنظیمات — این بخش رو حتماً پر کن
# ═══════════════════════════════════════════════

# توکن ربات خودت رو از BotFather بگیر و اینجا بذار
BOT_TOKEN = "YOUR_BOT_TOKEN"   # ← عوض کن

# آدرس Mini App که باید HTTPS باشد (برای تست لوکال، راهنمای پایین فایل را ببین)
WEBAPP_URL = "https://your-domain.com/quiz/"   # ← عوض کن

# Chat ID عددی ادمین — جایی که خلاصه‌ی نتیجه‌ی هر آزمون فرستاده می‌شود
# راهنما برای گرفتنش: به ربات @userinfobot پیام بده، عدد chat id رو بهت می‌ده
ADMIN_CHAT_ID = "YOUR_ADMIN_CHAT_ID"   # ← عوض کن

# ═══════════════════════════════════════════════

bot = telebot.TeleBot(BOT_TOKEN)


# ───────────────────────────────────────────────
#  /start  —  نمایش دکمه‌ی باز کردن آزمون
# ───────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def handle_start(message):
    user_name = message.from_user.first_name or "کاربر"

    # ⚠️ از ReplyKeyboardMarkup استفاده می‌کنیم، نه InlineKeyboardMarkup
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton(
        text="📝 شروع آزمون",
        web_app=WebAppInfo(url=WEBAPP_URL)
    ))

    welcome_text = (
        f"سلام {user_name}! 👋\n\n"
        "به ربات آزمون خوش آمدید.\n"
        "برای شروع، روی دکمه‌ی پایین کلیک کنید 👇"
    )

    bot.send_message(message.chat.id, welcome_text, reply_markup=keyboard)


@bot.message_handler(commands=["help"])
def handle_help(message):
    help_text = (
        "📌 راهنما:\n\n"
        "/start - شروع و باز کردن آزمون\n"
        "/help  - نمایش این پیام\n"
    )
    bot.send_message(message.chat.id, help_text)


# ───────────────────────────────────────────────
#  دریافت نتیجه‌ی آزمون از Mini App
# ───────────────────────────────────────────────
@bot.message_handler(content_types=["web_app_data"])
def handle_webapp_data(message):
    raw = message.web_app_data.data

    try:
        result = json.loads(raw)
    except Exception:
        bot.send_message(
            message.chat.id,
            f"⚠️ داده‌ی نامعتبر دریافت شد:\n<code>{raw}</code>",
            parse_mode="HTML"
        )
        return

    # ساخت پیام خلاصه برای ادمین
    summary = build_result_summary(result)

    try:
        bot.send_message(ADMIN_CHAT_ID, summary, parse_mode="HTML")
    except Exception as e:
        print(f"[ADMIN NOTIFY ERROR] {e}")

    # تأیید برای خود کاربر
    bot.send_message(
        message.chat.id,
        f"✅ آزمون شما با موفقیت ثبت شد!\n\n"
        f"🎯 امتیاز شما: {result.get('score', '—')} از {result.get('total', '—')}\n\n"
        "نتیجه برای بررسی به مدیر ارسال شد."
    )


def build_result_summary(result: dict) -> str:
    """متن خلاصه‌ی نتیجه‌ی آزمون رو برای ادمین می‌سازه."""
    D = "━━━━━━━━━━━━━━━━━━━━"
    username = result.get("username")
    username_display = f"@{username}" if username else "—"

    return (
        f"📝 <b>نتیجه‌ی آزمون جدید</b>\n"
        f"{D}\n"
        f"👤 <b>نام:</b> {result.get('first_name', '—')} {result.get('last_name', '—')}\n"
        f"🆔 <b>کد ملی:</b> {result.get('national_id', '—')}\n"
        f"💬 <b>یوزرنیم:</b> {username_display}\n"
        f"🔢 <b>آیدی عددی تلگرام:</b> {result.get('telegram_id', '—')}\n"
        f"{D}\n"
        f"🎯 <b>امتیاز:</b> {result.get('score', '—')} از {result.get('total', '—')}\n"
        f"{D}"
    )


if __name__ == "__main__":
    print("✅ ربات آزمون در حال اجراست...")
    bot.infinity_polling()
