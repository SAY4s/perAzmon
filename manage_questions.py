"""
manage_questions.py  —  ابزار مدیریت سؤالات آزمون
================================================================================
این اسکریپت کاملاً مجزا از ربات اصلیه. باهاش می‌تونی سؤالات رو:
  - مشاهده کنی (لیست کامل)
  - اضافه کنی (سؤال جدید با ۴ گزینه)
  - ویرایش کنی (تغییر متن سؤال، گزینه‌ها یا جواب صحیح)
  - حذف کنی
  - یا مستقیم همه‌ی سؤالات قبلی رو با یه فایل جدید جایگزین کنی

این اسکریپت با questions.json کار می‌کنه — همون فایلی که ربات اصلی
موقع اجرای آزمون ازش می‌خونه. هیچ نیازی به تغییر کد ربات نیست؛
کافیه این اسکریپت رو اجرا کنی و سؤالات رو آپدیت کنی.

اجرا:
  python manage_questions.py
"""

import json
import os

QUESTIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "questions.json")


# ───────────────────────────────────────────────
#  توابع پایه‌ی خواندن / نوشتن فایل
# ───────────────────────────────────────────────
def load_questions() -> list:
    """تمام سؤالات رو از فایل JSON می‌خونه. اگه فایل نباشه، لیست خالی برمی‌گردونه."""
    if not os.path.exists(QUESTIONS_FILE):
        return []
    try:
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"❌ خطا در خواندن فایل: {e}")
        return []


def save_questions(questions: list):
    """لیست سؤالات رو با فرمت زیبا (indent=2) و پشتیبانی کامل از فارسی ذخیره می‌کنه."""
    with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
    print(f"✅ ذخیره شد در: {QUESTIONS_FILE}")


def get_next_id(questions: list) -> int:
    """شناسه‌ی بعدی رو محاسبه می‌کنه (بزرگ‌ترین id فعلی + ۱)."""
    if not questions:
        return 1
    return max(q.get("id", 0) for q in questions) + 1


# ───────────────────────────────────────────────
#  نمایش سؤالات
# ───────────────────────────────────────────────
def list_questions():
    questions = load_questions()
    if not questions:
        print("\n⚠️  هیچ سؤالی ثبت نشده است.\n")
        return

    print(f"\n📋 لیست سؤالات (تعداد: {len(questions)})")
    print("─" * 50)
    for q in questions:
        correct_choice = q["choices"][q["correct_index"]]
        print(f"\n#{q['id']}  {q['question']}")
        for i, choice in enumerate(q["choices"]):
            marker = "✅" if i == q["correct_index"] else "  "
            print(f"   {marker} {i + 1}. {choice}")
    print("\n" + "─" * 50)


# ───────────────────────────────────────────────
#  اضافه کردن سؤال جدید
# ───────────────────────────────────────────────
def add_question():
    print("\n➕ افزودن سؤال جدید")
    print("─" * 30)

    question_text = input("متن سؤال: ").strip()
    if not question_text:
        print("❌ متن سؤال نمی‌تواند خالی باشد.")
        return

    choices = []
    for i in range(4):
        choice = input(f"گزینه {i + 1}: ").strip()
        if not choice:
            print("❌ همه‌ی گزینه‌ها باید پر شوند.")
            return
        choices.append(choice)

    while True:
        try:
            correct = int(input("شماره‌ی گزینه‌ی صحیح (۱ تا ۴): ").strip())
            if 1 <= correct <= 4:
                correct_index = correct - 1
                break
            print("❌ باید عددی بین ۱ تا ۴ باشد.")
        except ValueError:
            print("❌ لطفاً یک عدد وارد کنید.")

    questions = load_questions()
    new_question = {
        "id": get_next_id(questions),
        "question": question_text,
        "choices": choices,
        "correct_index": correct_index,
    }
    questions.append(new_question)
    save_questions(questions)
    print(f"✅ سؤال #{new_question['id']} با موفقیت اضافه شد.")


# ───────────────────────────────────────────────
#  ویرایش سؤال
# ───────────────────────────────────────────────
def edit_question():
    questions = load_questions()
    if not questions:
        print("\n⚠️  هیچ سؤالی برای ویرایش وجود ندارد.\n")
        return

    list_questions()
    try:
        target_id = int(input("\nشناسه‌ی (#) سؤالی که می‌خوای ویرایش کنی: ").strip())
    except ValueError:
        print("❌ شناسه باید عدد باشد.")
        return

    question = next((q for q in questions if q["id"] == target_id), None)
    if not question:
        print(f"❌ سؤالی با شناسه {target_id} پیدا نشد.")
        return

    print(f"\nویرایش سؤال #{target_id} — برای رد شدن از هر فیلد، Enter بزن (مقدار قبلی حفظ می‌شود)")

    new_text = input(f"متن سؤال [{question['question']}]: ").strip()
    if new_text:
        question["question"] = new_text

    for i in range(4):
        new_choice = input(f"گزینه {i + 1} [{question['choices'][i]}]: ").strip()
        if new_choice:
            question["choices"][i] = new_choice

    new_correct = input(f"شماره‌ی گزینه‌ی صحیح [{question['correct_index'] + 1}]: ").strip()
    if new_correct:
        try:
            correct = int(new_correct)
            if 1 <= correct <= 4:
                question["correct_index"] = correct - 1
            else:
                print("⚠️  عدد نامعتبر بود — مقدار قبلی حفظ شد.")
        except ValueError:
            print("⚠️  ورودی نامعتبر بود — مقدار قبلی حفظ شد.")

    save_questions(questions)
    print(f"✅ سؤال #{target_id} با موفقیت ویرایش شد.")


# ───────────────────────────────────────────────
#  حذف سؤال
# ───────────────────────────────────────────────
def delete_question():
    questions = load_questions()
    if not questions:
        print("\n⚠️  هیچ سؤالی برای حذف وجود ندارد.\n")
        return

    list_questions()
    try:
        target_id = int(input("\nشناسه‌ی (#) سؤالی که می‌خوای حذف کنی: ").strip())
    except ValueError:
        print("❌ شناسه باید عدد باشد.")
        return

    question = next((q for q in questions if q["id"] == target_id), None)
    if not question:
        print(f"❌ سؤالی با شناسه {target_id} پیدا نشد.")
        return

    confirm = input(f"⚠️  مطمئنی می‌خوای سؤال «{question['question']}» حذف شود؟ (y/n): ").strip().lower()
    if confirm == "y":
        questions = [q for q in questions if q["id"] != target_id]
        save_questions(questions)
        print(f"✅ سؤال #{target_id} حذف شد.")
    else:
        print("لغو شد.")


# ───────────────────────────────────────────────
#  جایگزینی کامل با فایل دیگر (Import یکجا)
# ───────────────────────────────────────────────
def import_from_file():
    print("\n📥 وارد کردن سؤالات از یک فایل JSON دیگر")
    path = input("مسیر کامل فایل JSON: ").strip()

    if not os.path.exists(path):
        print(f"❌ فایلی در مسیر «{path}» پیدا نشد.")
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            new_questions = json.load(f)
    except Exception as e:
        print(f"❌ خطا در خواندن فایل: {e}")
        return

    # اعتبارسنجی ساده‌ی ساختار
    required_keys = {"question", "choices", "correct_index"}
    for i, q in enumerate(new_questions):
        if not required_keys.issubset(q.keys()):
            print(f"❌ سؤال شماره {i + 1} ساختار نامعتبر دارد (کلیدهای لازم: {required_keys})")
            return
        if len(q["choices"]) != 4:
            print(f"❌ سؤال شماره {i + 1} باید دقیقاً ۴ گزینه داشته باشد.")
            return

    # اطمینان از وجود id برای هر سؤال
    for i, q in enumerate(new_questions):
        q.setdefault("id", i + 1)

    confirm = input(f"⚠️  این کار {len(new_questions)} سؤال فعلی را با {len(new_questions)} سؤال جدید جایگزین می‌کند. ادامه می‌دهید؟ (y/n): ").strip().lower()
    if confirm == "y":
        save_questions(new_questions)
        print(f"✅ {len(new_questions)} سؤال با موفقیت جایگزین شد.")
    else:
        print("لغو شد.")


# ───────────────────────────────────────────────
#  منوی اصلی
# ───────────────────────────────────────────────
def main_menu():
    while True:
        print("\n" + "═" * 50)
        print("📚  ابزار مدیریت سؤالات آزمون")
        print("═" * 50)
        print("1. نمایش همه‌ی سؤالات")
        print("2. افزودن سؤال جدید")
        print("3. ویرایش سؤال")
        print("4. حذف سؤال")
        print("5. وارد کردن (Import) از فایل دیگر")
        print("0. خروج")
        print("─" * 50)

        choice = input("انتخاب شما: ").strip()

        if choice == "1":
            list_questions()
        elif choice == "2":
            add_question()
        elif choice == "3":
            edit_question()
        elif choice == "4":
            delete_question()
        elif choice == "5":
            import_from_file()
        elif choice == "0":
            print("👋 خروج از برنامه.")
            break
        else:
            print("❌ گزینه نامعتبر. دوباره تلاش کنید.")


if __name__ == "__main__":
    main_menu()
