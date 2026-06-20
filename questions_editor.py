"""
questions_editor.py  —  ابزار گرافیکی مدیریت آزمون‌ها و سؤالات
================================================================================
این ابزار کاملاً مستقل و آفلاین است — هیچ ارتباطی با ربات تلگرام یا
هیچ سروری ندارد. فقط با فایل exams.json روی همین کامپیوتر کار می‌کند.

با این ابزار می‌توانی:
  - آزمون جدید بسازی (با تنظیمات نمره‌دهی مخصوص خودش)
  - آزمون موجود را ویرایش یا حذف کنی
  - برای هر آزمون، سؤال چهارگزینه‌ای یا تشریحی اضافه/ویرایش/حذف کنی
  - ترتیب سؤالات را تغییر دهی (بالا/پایین)
  - همه چیز را در فایل exams.json ذخیره کنی

بعد از ذخیره، خودت فایل exams.json را به‌جای نسخه‌ی قبلی روی هاست
(مثلاً GitHub Pages) جایگزین کن. این ابزار به سرور یا ربات دست نمی‌زند.

اجرا:
  python questions_editor.py

نیاز به نصب اضافه ندارد — tkinter جزو کتابخانه‌ی استاندارد پایتون است.
(در لینوکس اگر نصب نبود: sudo apt install python3-tk)
"""

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

EXAMS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exams.json")


# ───────────────────────────────────────────────
#  مدل داده
# ───────────────────────────────────────────────
def load_exams():
    if not os.path.exists(EXAMS_FILE):
        return []
    try:
        with open(EXAMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        messagebox.showerror("خطا", f"خطا در خواندن فایل exams.json:\n{e}")
        return []


def save_exams(exams):
    with open(EXAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(exams, f, ensure_ascii=False, indent=2)


def slugify(text: str) -> str:
    """شناسه‌ی ساده از روی عنوان آزمون می‌سازد (فقط برای آزمون‌های جدید)."""
    base = "".join(c if c.isalnum() else "-" for c in text.strip().lower())
    base = "-".join(filter(None, base.split("-")))
    return base or "exam"


def unique_exam_id(base_id, exams, ignore_id=None):
    existing = {e["id"] for e in exams if e["id"] != ignore_id}
    if base_id not in existing:
        return base_id
    i = 2
    while f"{base_id}-{i}" in existing:
        i += 1
    return f"{base_id}-{i}"


def next_question_id(questions):
    if not questions:
        return 1
    return max(q.get("id", 0) for q in questions) + 1


# ───────────────────────────────────────────────
#  پنجره‌ی ویرایش سؤال (چهارگزینه‌ای یا تشریحی)
# ───────────────────────────────────────────────
class QuestionDialog(tk.Toplevel):
    def __init__(self, parent, question=None):
        super().__init__(parent)
        self.title("سؤال" if question is None else "ویرایش سؤال")
        self.geometry("520x520")
        self.resizable(True, True)
        self.result = None
        self.question = question or {}

        self.configure(padx=16, pady=16)

        # نوع سؤال
        type_frame = ttk.Frame(self)
        type_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(type_frame, text="نوع سؤال:", font=("Tahoma", 10, "bold")).pack(side="right", padx=(0, 8))
        self.type_var = tk.StringVar(value=self.question.get("type", "multiple_choice"))
        ttk.Radiobutton(type_frame, text="چهارگزینه‌ای", variable=self.type_var,
                         value="multiple_choice", command=self.on_type_change).pack(side="right", padx=4)
        ttk.Radiobutton(type_frame, text="تشریحی", variable=self.type_var,
                         value="essay", command=self.on_type_change).pack(side="right", padx=4)

        # متن سؤال
        ttk.Label(self, text="متن سؤال:", font=("Tahoma", 10, "bold")).pack(anchor="e")
        self.question_text = tk.Text(self, height=3, wrap="word", font=("Tahoma", 10))
        self.question_text.pack(fill="x", pady=(4, 12))
        self.question_text.insert("1.0", self.question.get("question", ""))

        # کانتینر بخش متغیر (گزینه‌ها یا حداکثر نمره)
        self.dynamic_frame = ttk.Frame(self)
        self.dynamic_frame.pack(fill="both", expand=True)

        self.choice_entries = []
        self.correct_var = tk.IntVar(value=self.question.get("correct_index", 0))
        self.max_score_var = tk.StringVar(value=str(self.question.get("max_score", 5)))

        self.build_dynamic_section()

        # دکمه‌ها
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", pady=(12, 0))
        ttk.Button(btn_frame, text="ذخیره", command=self.on_save).pack(side="right", padx=4)
        ttk.Button(btn_frame, text="انصراف", command=self.destroy).pack(side="right", padx=4)

        self.transient(parent)
        self.grab_set()

    def on_type_change(self):
        self.build_dynamic_section()

    def build_dynamic_section(self):
        for w in self.dynamic_frame.winfo_children():
            w.destroy()
        self.choice_entries = []

        if self.type_var.get() == "multiple_choice":
            ttk.Label(self.dynamic_frame, text="گزینه‌ها (گزینه‌ی صحیح را با دکمه‌ی رادیویی مشخص کن):",
                      font=("Tahoma", 10, "bold")).pack(anchor="e", pady=(0, 6))

            existing_choices = self.question.get("choices", ["", "", "", ""])
            while len(existing_choices) < 4:
                existing_choices.append("")

            for i in range(4):
                row = ttk.Frame(self.dynamic_frame)
                row.pack(fill="x", pady=3)
                ttk.Radiobutton(row, variable=self.correct_var, value=i).pack(side="right")
                entry = ttk.Entry(row, font=("Tahoma", 10), justify="right")
                entry.pack(side="right", fill="x", expand=True, padx=6)
                entry.insert(0, existing_choices[i])
                self.choice_entries.append(entry)
        else:
            ttk.Label(self.dynamic_frame, text="حداکثر نمره‌ی این سؤال (نمره‌دهی توسط ادمین):",
                      font=("Tahoma", 10, "bold")).pack(anchor="e", pady=(0, 6))
            entry = ttk.Entry(self.dynamic_frame, textvariable=self.max_score_var,
                               font=("Tahoma", 10), justify="right", width=10)
            entry.pack(anchor="e")
            ttk.Label(self.dynamic_frame,
                      text="توجه: پاسخ این نوع سؤال متنیه و باید توسط ادمین\nدر چت ربات (با دستور /بررسی) نمره‌دهی شود.",
                      foreground="#6b7280", font=("Tahoma", 9), justify="right").pack(anchor="e", pady=(10, 0))

    def on_save(self):
        qtext = self.question_text.get("1.0", "end").strip()
        if not qtext:
            messagebox.showwarning("خطا", "متن سؤال نمی‌تواند خالی باشد.")
            return

        qtype = self.type_var.get()
        data = {"type": qtype, "question": qtext}

        if qtype == "multiple_choice":
            choices = [e.get().strip() for e in self.choice_entries]
            if any(not c for c in choices):
                messagebox.showwarning("خطا", "همه‌ی ۴ گزینه باید پر شوند.")
                return
            data["choices"] = choices
            data["correct_index"] = self.correct_var.get()
        else:
            try:
                max_score = float(self.max_score_var.get())
                if max_score <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("خطا", "حداکثر نمره باید عددی مثبت باشد.")
                return
            data["max_score"] = max_score

        self.result = data
        self.destroy()


# ───────────────────────────────────────────────
#  پنجره‌ی ویرایش اطلاعات کلی آزمون (عنوان، توضیحات، تنظیمات نمره‌دهی)
# ───────────────────────────────────────────────
class ExamMetaDialog(tk.Toplevel):
    def __init__(self, parent, exam=None, exams=None):
        super().__init__(parent)
        self.title("آزمون جدید" if exam is None else "ویرایش اطلاعات آزمون")
        self.geometry("440x420")
        self.result = None
        self.exam = exam or {}
        self.exams = exams or []

        self.configure(padx=16, pady=16)

        ttk.Label(self, text="عنوان آزمون:", font=("Tahoma", 10, "bold")).pack(anchor="e")
        self.title_var = tk.StringVar(value=self.exam.get("title", ""))
        ttk.Entry(self, textvariable=self.title_var, font=("Tahoma", 10), justify="right").pack(fill="x", pady=(4, 12))

        ttk.Label(self, text="توضیح کوتاه (در لیست آزمون‌ها نمایش داده می‌شود):",
                  font=("Tahoma", 10, "bold")).pack(anchor="e")
        self.desc_var = tk.StringVar(value=self.exam.get("description", ""))
        ttk.Entry(self, textvariable=self.desc_var, font=("Tahoma", 10), justify="right").pack(fill="x", pady=(4, 16))

        ttk.Separator(self).pack(fill="x", pady=(0, 12))
        ttk.Label(self, text="تنظیمات نمره‌دهی این آزمون", font=("Tahoma", 10, "bold")).pack(anchor="e", pady=(0, 8))

        settings = self.exam.get("settings", {})

        # نمره منفی
        penalty_frame = ttk.Frame(self)
        penalty_frame.pack(fill="x", pady=4)
        ttk.Label(penalty_frame, text="نمره‌ی منفی برای هر پاسخ غلط (۰ = بدون نمره منفی):",
                  font=("Tahoma", 9)).pack(anchor="e")
        self.penalty_var = tk.StringVar(value=str(settings.get("wrong_answer_penalty", 0)))
        ttk.Entry(penalty_frame, textvariable=self.penalty_var, font=("Tahoma", 10),
                  justify="right", width=10).pack(anchor="e", pady=(4, 0))

        # اجباری بودن پاسخ به همه سؤالات
        self.require_all_var = tk.BooleanVar(value=settings.get("require_all_answers", False))
        ttk.Checkbutton(self, text="پاسخ به همه‌ی سؤالات این آزمون الزامی باشد",
                         variable=self.require_all_var).pack(anchor="e", pady=(12, 0))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", pady=(20, 0))
        ttk.Button(btn_frame, text="ذخیره", command=self.on_save).pack(side="right", padx=4)
        ttk.Button(btn_frame, text="انصراف", command=self.destroy).pack(side="right", padx=4)

        self.transient(parent)
        self.grab_set()

    def on_save(self):
        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning("خطا", "عنوان آزمون نمی‌تواند خالی باشد.")
            return

        try:
            penalty = float(self.penalty_var.get())
            if penalty < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("خطا", "نمره‌ی منفی باید عددی بزرگ‌تر یا مساوی صفر باشد.")
            return

        exam_id = self.exam.get("id")
        if not exam_id:
            exam_id = unique_exam_id(slugify(title), self.exams)

        self.result = {
            "id": exam_id,
            "title": title,
            "description": self.desc_var.get().strip(),
            "settings": {
                "wrong_answer_penalty": penalty,
                "require_all_answers": self.require_all_var.get(),
            },
        }
        self.destroy()


# ───────────────────────────────────────────────
#  پنجره‌ی اصلی
# ───────────────────────────────────────────────
class EditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ابزار مدیریت آزمون‌ها")
        self.geometry("880x560")

        self.exams = load_exams()
        self.selected_exam_index = None

        self.build_ui()
        self.refresh_exam_list()

    # ── چیدمان کلی ──
    def build_ui(self):
        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        # ستون راست: لیست آزمون‌ها
        left_panel = ttk.Frame(main, width=260)
        left_panel.pack(side="right", fill="y", padx=(12, 0))

        ttk.Label(left_panel, text="آزمون‌ها", font=("Tahoma", 12, "bold")).pack(anchor="e", pady=(0, 8))

        self.exam_listbox = tk.Listbox(left_panel, font=("Tahoma", 10), justify="right",
                                        activestyle="none", exportselection=False)
        self.exam_listbox.pack(fill="both", expand=True)
        self.exam_listbox.bind("<<ListboxSelect>>", self.on_exam_select)

        exam_btns = ttk.Frame(left_panel)
        exam_btns.pack(fill="x", pady=(8, 0))
        ttk.Button(exam_btns, text="➕ آزمون جدید", command=self.add_exam).pack(fill="x", pady=2)
        ttk.Button(exam_btns, text="✏️ ویرایش اطلاعات", command=self.edit_exam_meta).pack(fill="x", pady=2)
        ttk.Button(exam_btns, text="🗑 حذف آزمون", command=self.delete_exam).pack(fill="x", pady=2)

        ttk.Separator(left_panel).pack(fill="x", pady=10)
        ttk.Button(left_panel, text="💾 ذخیره در exams.json", command=self.save_all).pack(fill="x", pady=2)

        # ستون چپ: جزئیات آزمون انتخاب‌شده و سؤالاتش
        right_panel = ttk.Frame(main)
        right_panel.pack(side="right", fill="both", expand=True)

        self.exam_title_label = ttk.Label(right_panel, text="آزمونی انتخاب نشده",
                                           font=("Tahoma", 13, "bold"))
        self.exam_title_label.pack(anchor="e")
        self.exam_desc_label = ttk.Label(right_panel, text="", foreground="#6b7280", font=("Tahoma", 9))
        self.exam_desc_label.pack(anchor="e", pady=(2, 4))
        self.exam_settings_label = ttk.Label(right_panel, text="", foreground="#2f6f4f", font=("Tahoma", 9, "bold"))
        self.exam_settings_label.pack(anchor="e", pady=(0, 10))

        ttk.Separator(right_panel).pack(fill="x", pady=(0, 10))

        cols_frame = ttk.Frame(right_panel)
        cols_frame.pack(fill="both", expand=True)

        self.question_listbox = tk.Listbox(cols_frame, font=("Tahoma", 10), justify="right",
                                            activestyle="none", exportselection=False)
        self.question_listbox.pack(side="right", fill="both", expand=True)
        self.question_listbox.bind("<<ListboxSelect>>", self.on_question_select)

        q_btns = ttk.Frame(cols_frame)
        q_btns.pack(side="left", fill="y", padx=(0, 8))
        ttk.Button(q_btns, text="➕ سؤال جدید", command=self.add_question).pack(fill="x", pady=2)
        ttk.Button(q_btns, text="✏️ ویرایش سؤال", command=self.edit_question).pack(fill="x", pady=2)
        ttk.Button(q_btns, text="🗑 حذف سؤال", command=self.delete_question).pack(fill="x", pady=2)
        ttk.Separator(q_btns, orient="horizontal").pack(fill="x", pady=8)
        ttk.Button(q_btns, text="⬆ بالا", command=lambda: self.move_question(-1)).pack(fill="x", pady=2)
        ttk.Button(q_btns, text="⬇ پایین", command=lambda: self.move_question(1)).pack(fill="x", pady=2)

    # ── کمکی‌ها ──
    def current_exam(self):
        if self.selected_exam_index is None:
            return None
        return self.exams[self.selected_exam_index]

    def refresh_exam_list(self):
        self.exam_listbox.delete(0, "end")
        for exam in self.exams:
            qcount = len(exam.get("questions", []))
            self.exam_listbox.insert("end", f"{exam.get('title', exam.get('id'))}  ({qcount} سؤال)")

        if self.exams:
            idx = self.selected_exam_index if self.selected_exam_index is not None else 0
            idx = min(idx, len(self.exams) - 1)
            self.exam_listbox.selection_set(idx)
            self.selected_exam_index = idx
        else:
            self.selected_exam_index = None

        self.refresh_exam_detail()

    def refresh_exam_detail(self):
        exam = self.current_exam()
        if not exam:
            self.exam_title_label.config(text="آزمونی انتخاب نشده")
            self.exam_desc_label.config(text="")
            self.exam_settings_label.config(text="")
            self.question_listbox.delete(0, "end")
            return

        self.exam_title_label.config(text=exam.get("title", exam.get("id")))
        self.exam_desc_label.config(text=exam.get("description", ""))

        settings = exam.get("settings", {})
        penalty = settings.get("wrong_answer_penalty", 0)
        require_all = settings.get("require_all_answers", False)
        settings_text = f"نمره منفی هر غلط: {penalty}   |   پاسخ به همه الزامی: {'بله' if require_all else 'خیر'}"
        self.exam_settings_label.config(text=settings_text)

        self.refresh_question_list()

    def refresh_question_list(self):
        self.question_listbox.delete(0, "end")
        exam = self.current_exam()
        if not exam:
            return
        for q in exam.get("questions", []):
            tag = "📝 تشریحی" if q.get("type") == "essay" else "🔘 چهارگزینه‌ای"
            preview = q.get("question", "")[:60]
            self.question_listbox.insert("end", f"[{tag}]  {preview}")

    # ── مدیریت آزمون‌ها ──
    def on_exam_select(self, event):
        sel = self.exam_listbox.curselection()
        if sel:
            self.selected_exam_index = sel[0]
            self.refresh_exam_detail()

    def add_exam(self):
        dialog = ExamMetaDialog(self, exams=self.exams)
        self.wait_window(dialog)
        if dialog.result:
            new_exam = dialog.result
            new_exam["questions"] = []
            self.exams.append(new_exam)
            self.selected_exam_index = len(self.exams) - 1
            self.refresh_exam_list()

    def edit_exam_meta(self):
        exam = self.current_exam()
        if not exam:
            messagebox.showinfo("توجه", "ابتدا یک آزمون را انتخاب کنید.")
            return
        dialog = ExamMetaDialog(self, exam=exam, exams=self.exams)
        self.wait_window(dialog)
        if dialog.result:
            exam.update(dialog.result)
            self.refresh_exam_list()

    def delete_exam(self):
        exam = self.current_exam()
        if not exam:
            messagebox.showinfo("توجه", "ابتدا یک آزمون را انتخاب کنید.")
            return
        if messagebox.askyesno("تأیید حذف", f"آزمون «{exam.get('title')}» و همه‌ی سؤالاتش حذف شود؟"):
            self.exams.pop(self.selected_exam_index)
            self.selected_exam_index = None
            self.refresh_exam_list()

    # ── مدیریت سؤالات ──
    def selected_question_index(self):
        sel = self.question_listbox.curselection()
        return sel[0] if sel else None

    def on_question_select(self, event):
        pass  # فقط برای فعال نگه داشتن انتخاب؛ منطق خاصی لازم نیست

    def add_question(self):
        exam = self.current_exam()
        if not exam:
            messagebox.showinfo("توجه", "ابتدا یک آزمون را انتخاب یا ایجاد کنید.")
            return
        dialog = QuestionDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            questions = exam.setdefault("questions", [])
            dialog.result["id"] = next_question_id(questions)
            questions.append(dialog.result)
            self.refresh_exam_list()

    def edit_question(self):
        exam = self.current_exam()
        idx = self.selected_question_index()
        if not exam or idx is None:
            messagebox.showinfo("توجه", "ابتدا یک سؤال را انتخاب کنید.")
            return
        question = exam["questions"][idx]
        dialog = QuestionDialog(self, question=question)
        self.wait_window(dialog)
        if dialog.result:
            dialog.result["id"] = question["id"]
            exam["questions"][idx] = dialog.result
            self.refresh_exam_list()

    def delete_question(self):
        exam = self.current_exam()
        idx = self.selected_question_index()
        if not exam or idx is None:
            messagebox.showinfo("توجه", "ابتدا یک سؤال را انتخاب کنید.")
            return
        if messagebox.askyesno("تأیید حذف", "این سؤال حذف شود؟"):
            exam["questions"].pop(idx)
            self.refresh_exam_list()

    def move_question(self, direction):
        exam = self.current_exam()
        idx = self.selected_question_index()
        if not exam or idx is None:
            return
        new_idx = idx + direction
        questions = exam["questions"]
        if 0 <= new_idx < len(questions):
            questions[idx], questions[new_idx] = questions[new_idx], questions[idx]
            self.refresh_question_list()
            self.question_listbox.selection_set(new_idx)

    # ── ذخیره ──
    def save_all(self):
        try:
            save_exams(self.exams)
            messagebox.showinfo("ذخیره شد", f"تغییرات با موفقیت در فایل زیر ذخیره شد:\n{EXAMS_FILE}")
        except Exception as e:
            messagebox.showerror("خطا", f"ذخیره‌سازی با خطا مواجه شد:\n{e}")


if __name__ == "__main__":
    app = EditorApp()
    app.mainloop()
