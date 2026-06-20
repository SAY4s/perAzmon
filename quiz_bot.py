"""
quiz_bot.py  —  ربات تلگرام چند آزمونه (Telegram Mini App)
================================================================================
این ربات:
  1. وقتی کاربر /start می‌زند، دکمه‌ی باز کردن Mini App رو نشون می‌ده
     (کاربر داخل سایت، آزمون مورد نظرش رو از لیست انتخاب می‌کند)
  2. وقتی Mini App نتیجه‌ی یک آزمون رو می‌فرسته (sendData)، ربات:
       - نمره را بر اساس تنظیمات همان آزمون (نمره‌ی منفی برای جواب غلط،
         اجباری بودن پاسخ به همه‌ی سؤالات) محاسبه می‌کند
       - اگر سؤال تشریحی وجود داشته باشد، آن را در صف بررسی ادمین قرار می‌دهد
       - خلاصه را برای ادمین می‌فرستد
       - به خود کاربر هم نتیجه را نشان می‌دهد — و اگر این آزمون را قبلاً
         هم داده باشد، با نمره‌ی دفعه‌ی قبل مقایسه می‌کند («خوش برگشتی»)

⚠️ نکته‌ی مهم و حیاتی:
  برای اینکه Telegram.WebApp.sendData() کار کند، دکمه‌ی باز کردن
  Mini App باید از نوع KeyboardButton (ReplyKeyboardMarkup) باشد،
  نه InlineKeyboardButton. این یک محدودیت رسمی خود تلگرام است.

⚠️ نکته‌ی مهم درباره‌ی حافظه:
  این ربات هیچ دیتابیسی ندارد. همه‌چیز (نمرات قبلی کاربران، صف بررسی
  سؤالات تشریحی) فقط در حافظه‌ی RAM نگه داشته می‌شود. با هر بار
  ری‌استارت ربات، این اطلاعات از بین می‌روند. این یک انتخاب عمدی
  برای سادگی است، نه یک باگ.

نصب پیش‌نیاز:
  pip install pyTelegramBotAPI

اجرا:
  python quiz_bot.py
"""

import json
import os
import threading

import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

# ═══════════════════════════════════════════════
#  ⚙️  تنظیمات — این بخش رو حتماً پر کن
# ═══════════════════════════════════════════════

BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"   # ← از BotFather بگیر (توکن قبلی لو رفته بود، حتماً عوضش کن)

WEBAPP_URL = "https://say4s.github.io/perAzmon/"   # ← آدرس GitHub Pages سایت

ADMIN_CHAT_ID = "7633207763"   # ← chat id عددی ادمین

EXAMS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exams.json")

# ═══════════════════════════════════════════════

bot = telebot.TeleBot(BOT_TOKEN)

# ───────────────────────────────────────────────
#  حافظه‌ی موقت (در RAM) — نه دیتابیس
# ───────────────────────────────────────────────
# نمرات قبلی هر کاربر، به ازای کد ملی + شناسه‌ی آزمون
# ساختار: previous_scores[(national_id, exam_id)] = {"score": .., "max_score": ..}
previous_scores = {}

# صف بررسی سؤالات تشریحی، در انتظار نمره‌دهی ادمین
# هر آیتم: {"national_id", "full_name", "exam_id", "exam_title",
#           "question", "answer_text", "max_score"}
review_queue = []

# جلسه‌ی فعلی بررسی هر ادمین (برای جریان مکالمه‌ای /بررسی)
# ساختار: admin_review_session[admin_chat_id] = index در review_queue
admin_review_session = {}

lock = threading.Lock()


# ───────────────────────────────────────────────
#  خواندن فایل آزمون‌ها
# ───────────────────────────────────────────────
def load_exams() -> list:
    if not os.path.exists(EXAMS_FILE):
        return []
    try:
        with open(EXAMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[EXAMS LOAD ERROR] {e}")
        return []


def find_exam(exam_id: str) -> dict | None:
    for exam in load_exams():
        if exam.get("id") == exam_id:
            return exam
    return None


# ───────────────────────────────────────────────
#  /start  —  نمایش دکمه‌ی باز کردن آزمون
# ───────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def handle_start(message):
    user_name = message.from_user.first_name or "کاربر"

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
        "/start    - شروع و باز کردن آزمون\n"
        "/help     - نمایش این پیام\n"
    )
    if str(message.chat.id) == str(ADMIN_CHAT_ID):
        help_text += "/بررسی    - بررسی و نمره‌دهی به پاسخ‌های تشریحی در صف (فقط ادمین)\n"
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

    exam_id = result.get("exam_id")
    exam = find_exam(exam_id)
    if not exam:
        bot.send_message(message.chat.id, "⚠️ آزمون مورد نظر یافت نشد (ممکن است حذف شده باشد).")
        return

    scored = score_submission(exam, result)

    national_id = result.get("national_id")
    full_name = f"{result.get('first_name', '')} {result.get('last_name', '')}".strip()

    # مقایسه با دفعه‌ی قبل (در همین اجرای ربات)
    key = (national_id, exam_id)
    with lock:
        previous = previous_scores.get(key)
        previous_scores[key] = {"score": scored["score"], "max_score": scored["max_score"]}

    # اگر سؤال تشریحی داشت، در صف بررسی ادمین قرار بده
    if scored["essay_answers"]:
        with lock:
            for ea in scored["essay_answers"]:
                review_queue.append({
                    "national_id": national_id,
                    "full_name": full_name,
                    "exam_id": exam_id,
                    "exam_title": exam.get("title", exam_id),
                    "question": ea["question"],
                    "answer_text": ea["answer_text"],
                    "max_score": ea["max_score"],
                })

    # پیام برای ادمین
    admin_summary = build_admin_summary(exam, result, scored)
    try:
        bot.send_message(ADMIN_CHAT_ID, admin_summary, parse_mode="HTML")
    except Exception as e:
        print(f"[ADMIN NOTIFY ERROR] {e}")

    if scored["essay_answers"]:
        try:
            bot.send_message(
                ADMIN_CHAT_ID,
                f"📩 {len(scored['essay_answers'])} پاسخ تشریحی جدید در صف بررسی قرار گرفت.\n"
                f"برای نمره‌دهی دستور /بررسی را بزنید."
            )
        except Exception:
            pass

    # پیام برای کاربر
    user_message = build_user_result_message(exam, scored, previous)
    bot.send_message(message.chat.id, user_message, parse_mode="HTML")


def score_submission(exam: dict, result: dict) -> dict:
    """
    نمره را بر اساس تنظیمات آزمون محاسبه می‌کند.
    خروجی:
      score, max_score, correct_count, wrong_count, unanswered_count,
      total_questions, essay_answers (لیستی که باید توسط ادمین بررسی شود),
      all_answered (bool)
    """
    settings = exam.get("settings", {})
    penalty = settings.get("wrong_answer_penalty", 0)  # عدد مثبت یعنی کسر این مقدار

    questions = exam.get("questions", [])
    answers = result.get("answers", {})  # { "question_id(str)": idx یا متن }

    score = 0.0
    max_score = 0.0
    correct_count = 0
    wrong_count = 0
    unanswered_count = 0
    essay_answers = []

    for q in questions:
        qid = str(q["id"])
        qtype = q.get("type", "multiple_choice")

        if qtype == "essay":
            max_score += q.get("max_score", 5)
            answer_text = (answers.get(qid) or "").strip()
            if answer_text:
                essay_answers.append({
                    "question": q["question"],
                    "answer_text": answer_text,
                    "max_score": q.get("max_score", 5),
                })
            else:
                unanswered_count += 1
            continue

        # چهارگزینه‌ای
        max_score += 1
        given = answers.get(qid, None)

        if given is None or given == "":
            unanswered_count += 1
            continue

        try:
            given_idx = int(given)
        except (TypeError, ValueError):
            unanswered_count += 1
            continue

        if given_idx == q.get("correct_index"):
            score += 1
            correct_count += 1
        else:
            wrong_count += 1
            score -= penalty

    total_questions = len(questions)
    all_answered = unanswered_count == 0

    return {
        "score": round(score, 2),
        "max_score": round(max_score, 2),
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "unanswered_count": unanswered_count,
        "total_questions": total_questions,
        "essay_answers": essay_answers,
        "all_answered": all_answered,
    }


def build_admin_summary(exam: dict, result: dict, scored: dict) -> str:
    D = "━━━━━━━━━━━━━━━━━━━━"
    username = result.get("username")
    username_display = f"@{username}" if username else "—"

    essay_note = ""
    if scored["essay_answers"]:
        essay_note = f"\n📝 <b>شامل {len(scored['essay_answers'])} پاسخ تشریحی</b> (نمره نهایی پس از بررسی تغییر می‌کند)"

    return (
        f"📝 <b>نتیجه‌ی جدید — {exam.get('title', exam.get('id'))}</b>\n"
        f"{D}\n"
        f"👤 <b>نام:</b> {result.get('first_name', '—')} {result.get('last_name', '—')}\n"
        f"🆔 <b>کد ملی:</b> {result.get('national_id', '—')}\n"
        f"💬 <b>یوزرنیم:</b> {username_display}\n"
        f"🔢 <b>آیدی عددی تلگرام:</b> {result.get('telegram_id', '—')}\n"
        f"{D}\n"
        f"✅ صحیح: {scored['correct_count']}  |  ❌ غلط: {scored['wrong_count']}  |  ⏺ بی‌پاسخ: {scored['unanswered_count']}\n"
        f"🎯 <b>نمره (بدون تشریحی):</b> {scored['score']} از {scored['max_score']}"
        f"{essay_note}\n"
        f"{D}"
    )


def build_user_result_message(exam: dict, scored: dict, previous: dict | None) -> str:
    title = exam.get("title", exam.get("id"))

    lines = [f"✅ آزمون «{title}» با موفقیت ثبت شد!\n"]
    lines.append(f"🎯 نمره‌ی شما: {scored['score']} از {scored['max_score']}")

    if scored["essay_answers"]:
        lines.append("📝 پاسخ‌(های) تشریحی شما برای بررسی نهایی به مدیر ارسال شد؛ نمره‌ی نهایی پس از بررسی اعلام خواهد شد.")

    if previous is not None:
        prev_score = previous["score"]
        diff = scored["score"] - prev_score
        if diff > 0:
            lines.append(f"\n🎉 خوش برگشتی! نمره‌ات نسبت به دفعه‌ی قبل ({prev_score}) بهتر شده — تبریک می‌گم! 📈")
        elif diff < 0:
            lines.append(f"\n👋 خوش برگشتی! این‌بار نمره‌ات ({scored['score']}) نسبت به دفعه‌ی قبل ({prev_score}) کمی پایین‌تر بود. جای نگرانی نیست، دوباره تلاش کن! 📉")
        else:
            lines.append(f"\n👋 خوش برگشتی! نمره‌ات دقیقاً مثل دفعه‌ی قبل ({prev_score}) شد.")
    else:
        lines.append("\nنتیجه برای بررسی به مدیر ارسال شد.")

    return "\n".join(lines)


# ───────────────────────────────────────────────
#  بررسی دستی سؤالات تشریحی توسط ادمین
# ───────────────────────────────────────────────
def is_admin(message) -> bool:
    return str(message.chat.id) == str(ADMIN_CHAT_ID)


@bot.message_handler(commands=["بررسی", "review"])
def handle_review_start(message):
    if not is_admin(message):
        bot.send_message(message.chat.id, "⛔ این دستور فقط برای ادمین است.")
        return

    with lock:
        if not review_queue:
            bot.send_message(message.chat.id, "✅ صف بررسی خالی است. هیچ پاسخ تشریحی‌ای در انتظار نیست.")
            return
        admin_review_session[message.chat.id] = 0

    send_next_review_item(message.chat.id)


def send_next_review_item(chat_id):
    with lock:
        idx = admin_review_session.get(chat_id, 0)
        if idx >= len(review_queue):
            admin_review_session.pop(chat_id, None)
            bot.send_message(chat_id, "🏁 صف بررسی به پایان رسید.")
            return
        item = review_queue[idx]

    D = "━━━━━━━━━━━━━━━━━━━━"
    text = (
        f"📝 <b>بررسی پاسخ تشریحی</b>  ({idx + 1}/{len(review_queue)})\n"
        f"{D}\n"
        f"👤 {item['full_name']}  |  🆔 {item['national_id']}\n"
        f"📚 آزمون: {item['exam_title']}\n"
        f"{D}\n"
        f"❓ <b>سؤال:</b>\n{item['question']}\n\n"
        f"✏️ <b>پاسخ کاربر:</b>\n{item['answer_text']}\n"
        f"{D}\n"
        f"لطفاً نمره‌ای بین ۰ تا {item['max_score']} ارسال کنید (فقط عدد):"
    )
    bot.send_message(chat_id, text, parse_mode="HTML")


@bot.message_handler(func=lambda m: is_admin(m) and m.chat.id in admin_review_session,
                      content_types=["text"])
def handle_review_score_input(message):
    chat_id = message.chat.id
    with lock:
        idx = admin_review_session.get(chat_id)
        if idx is None or idx >= len(review_queue):
            return
        item = review_queue[idx]

    try:
        given_score = float(message.text.strip())
    except ValueError:
        bot.send_message(chat_id, "❌ لطفاً فقط یک عدد ارسال کنید.")
        return

    if not (0 <= given_score <= item["max_score"]):
        bot.send_message(chat_id, f"❌ نمره باید بین ۰ تا {item['max_score']} باشد.")
        return

    bot.send_message(
        chat_id,
        f"✅ نمره‌ی {given_score} از {item['max_score']} برای پاسخ {item['full_name']} ثبت شد."
    )

    with lock:
        review_queue.pop(idx)
        # idx همونی می‌مونه چون آیتم بعدی جای این اومده

    send_next_review_item(chat_id)


if __name__ == "__main__":
    print("✅ ربات آزمون در حال اجراست...")
    bot.infinity_polling()
