"""
questions_editor.py  —  ابزار گرافیکی مدیریت آزمون‌ها و سؤالات (نسخه‌ی پیشرفته)
================================================================================
این ابزار کاملاً مستقل و آفلاین است — هیچ ارتباطی با ربات تلگرام یا
هیچ سروری ندارد. فقط با فایل exams.json روی همین کامپیوتر کار می‌کند.

امکانات:
  - تم تاریک / روشن (با یک دکمه قابل تغییر)
  - جستجوی زنده در لیست آزمون‌ها و لیست سؤالات
  - افزودن / ویرایش / حذف / تکرار (duplicate) آزمون و سؤال
  - تنظیمات نمره‌دهی مستقل برای هر آزمون (نمره‌ی منفی، الزامی بودن پاسخ)
  - سؤال چهارگزینه‌ای یا تشریحی
  - تغییر ترتیب سؤالات (بالا/پایین)
  - Undo / Redo کامل برای همه‌ی تغییرات (Ctrl+Z / Ctrl+Y یا دکمه‌های بالای صفحه)
  - ذخیره در exams.json

بعد از ذخیره، خودت فایل exams.json را به‌جای نسخه‌ی قبلی روی هاست
(مثلاً GitHub Pages) جایگزین کن. این ابزار به سرور یا ربات دست نمی‌زند.

اجرا:
  python questions_editor.py

نیاز به نصب اضافه ندارد — tkinter جزو کتابخانه‌ی استاندارد پایتون است.
(در لینوکس اگر نصب نبود: sudo apt install python3-tk)
"""

import copy
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox

EXAMS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exams.json")


# ═══════════════════════════════════════════════════════════════
#  تم‌ها (روشن / تاریک)
# ═══════════════════════════════════════════════════════════════
THEMES = {
    "light": {
        "bg":            "#f7f5f2",
        "surface":       "#ffffff",
        "surface_alt":   "#f0eee9",
        "ink":           "#1f2430",
        "muted":         "#6b7280",
        "primary":       "#2f6f4f",
        "primary_d":     "#244f3a",
        "accent":        "#c9622a",
        "danger":        "#b3432f",
        "border":        "#e5e1da",
        "select_bg":     "#dcebe2",
        "list_bg":       "#ffffff",
        "list_fg":       "#1f2430",
        "entry_bg":      "#ffffff",
    },
    "dark": {
        "bg":            "#15171c",
        "surface":       "#1d2027",
        "surface_alt":   "#262a33",
        "ink":           "#e9eaee",
        "muted":         "#9aa1ad",
        "primary":       "#49b07d",
        "primary_d":     "#36905f",
        "accent":        "#e0843f",
        "danger":        "#e0685a",
        "border":        "#33363f",
        "select_bg":     "#234334",
        "list_bg":       "#1d2027",
        "list_fg":       "#e9eaee",
        "entry_bg":      "#262a33",
    },
}

FONT_FAMILY = "Tahoma"


# ═══════════════════════════════════════════════════════════════
#  مدل داده — کمکی‌های خالص (بدون UI)، قابل تست مجزا
# ═══════════════════════════════════════════════════════════════
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


def duplicate_exam(exam, all_exams):
    """یک کپی کامل از آزمون با id و عنوان جدید برمی‌گرداند."""
    new_exam = copy.deepcopy(exam)
    new_exam["title"] = f"{exam.get('title', exam.get('id'))} (کپی)"
    base_id = slugify(new_exam["title"])
    new_exam["id"] = unique_exam_id(base_id, all_exams)
    return new_exam


def duplicate_question(question, questions):
    """یک کپی از سؤال با id جدید برمی‌گرداند."""
    new_q = copy.deepcopy(question)
    new_q["id"] = next_question_id(questions)
    if new_q.get("question"):
        new_q["question"] = new_q["question"] + " (کپی)"
    return new_q


def matches_search(text, query):
    if not query:
        return True
    return query.strip().lower() in (text or "").lower()


# ═══════════════════════════════════════════════════════════════
#  مدیریت Undo / Redo  —  بر اساس snapshot کامل از لیست آزمون‌ها
#  (داده‌ها کوچک هستن، snapshot ساده‌ترین و امن‌ترین روشه)
# ═══════════════════════════════════════════════════════════════
class HistoryManager:
    def __init__(self, initial_state, max_history=60):
        self.undo_stack = [copy.deepcopy(initial_state)]
        self.redo_stack = []
        self.max_history = max_history

    def push(self, state):
        """قبل از یک تغییر، state فعلی (بعد از تغییر) را اضافه می‌کند."""
        self.undo_stack.append(copy.deepcopy(state))
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def can_undo(self):
        return len(self.undo_stack) > 1

    def can_redo(self):
        return len(self.redo_stack) > 0

    def undo(self):
        if not self.can_undo():
            return None
        current = self.undo_stack.pop()
        self.redo_stack.append(current)
        return copy.deepcopy(self.undo_stack[-1])

    def redo(self):
        if not self.can_redo():
            return None
        state = self.redo_stack.pop()
        self.undo_stack.append(copy.deepcopy(state))
        return copy.deepcopy(state)


# ═══════════════════════════════════════════════════════════════
#  پنجره‌ی پایه با پشتیبانی از تم (برای دیالوگ‌ها)
# ═══════════════════════════════════════════════════════════════
class ThemedDialog(tk.Toplevel):
    def __init__(self, app, title):
        super().__init__(app)
        self.app = app
        self.title(title)
        self.result = None
        t = app.theme
        self.configure(bg=t["bg"], padx=16, pady=16)
        self.transient(app)

    def themed_label(self, parent, text, bold=False, size=10, muted=False):
        t = self.app.theme
        return tk.Label(
            parent, text=text, bg=t["bg"],
            fg=t["muted"] if muted else t["ink"],
            font=(FONT_FAMILY, size, "bold" if bold else "normal"),
            justify="right",
        )

    def themed_entry(self, parent, textvariable=None, width=None):
        t = self.app.theme
        kwargs = dict(
            bg=t["entry_bg"], fg=t["ink"], insertbackground=t["ink"],
            relief="flat", highlightthickness=1,
            highlightbackground=t["border"], highlightcolor=t["primary"],
            font=(FONT_FAMILY, 10), justify="right",
        )
        if width:
            kwargs["width"] = width
        e = tk.Entry(parent, textvariable=textvariable, **kwargs) if textvariable is not None \
            else tk.Entry(parent, **kwargs)
        return e

    def themed_text(self, parent, height=3):
        t = self.app.theme
        return tk.Text(
            parent, height=height, wrap="word",
            bg=t["entry_bg"], fg=t["ink"], insertbackground=t["ink"],
            relief="flat", highlightthickness=1,
            highlightbackground=t["border"], highlightcolor=t["primary"],
            font=(FONT_FAMILY, 10),
        )

    def themed_button(self, parent, text, command, primary=False):
        t = self.app.theme
        bg = t["primary"] if primary else t["surface_alt"]
        fg = "#ffffff" if primary else t["ink"]
        active_bg = t["primary_d"] if primary else t["border"]
        btn = tk.Button(
            parent, text=text, command=command,
            bg=bg, fg=fg, activebackground=active_bg, activeforeground=fg,
            relief="flat", font=(FONT_FAMILY, 10, "bold"),
            padx=14, pady=6, cursor="hand2", borderwidth=0,
        )
        return btn

    def themed_frame(self, parent):
        return tk.Frame(parent, bg=self.app.theme["bg"])


# ═══════════════════════════════════════════════════════════════
#  پنجره‌ی ویرایش سؤال (چهارگزینه‌ای یا تشریحی)
# ═══════════════════════════════════════════════════════════════
class QuestionDialog(ThemedDialog):
    def __init__(self, app, question=None):
        super().__init__(app, "سؤال جدید" if question is None else "ویرایش سؤال")
        self.geometry("540x540")
        self.resizable(True, True)
        self.question = question or {}
        t = self.app.theme

        type_frame = self.themed_frame(self)
        type_frame.pack(fill="x", pady=(0, 12))
        self.themed_label(type_frame, "نوع سؤال:", bold=True).pack(side="right", padx=(0, 8))

        self.type_var = tk.StringVar(value=self.question.get("type", "multiple_choice"))
        for value, label in (("multiple_choice", "چهارگزینه‌ای"), ("essay", "تشریحی")):
            rb = tk.Radiobutton(
                type_frame, text=label, value=value, variable=self.type_var,
                command=self.build_dynamic_section, bg=t["bg"], fg=t["ink"],
                selectcolor=t["surface_alt"], activebackground=t["bg"],
                font=(FONT_FAMILY, 10), highlightthickness=0,
            )
            rb.pack(side="right", padx=4)

        self.themed_label(self, "متن سؤال:", bold=True).pack(anchor="e")
        self.question_text = self.themed_text(self, height=3)
        self.question_text.pack(fill="x", pady=(4, 12))
        self.question_text.insert("1.0", self.question.get("question", ""))

        self.dynamic_frame = self.themed_frame(self)
        self.dynamic_frame.pack(fill="both", expand=True)

        self.choice_entries = []
        self.correct_var = tk.IntVar(value=self.question.get("correct_index", 0))
        self.max_score_var = tk.StringVar(value=str(self.question.get("max_score", 5)))

        self.build_dynamic_section()

        btn_frame = self.themed_frame(self)
        btn_frame.pack(fill="x", pady=(12, 0))
        self.themed_button(btn_frame, "ذخیره", self.on_save, primary=True).pack(side="right", padx=4)
        self.themed_button(btn_frame, "انصراف", self.destroy).pack(side="right", padx=4)

        self.grab_set()

    def build_dynamic_section(self):
        for w in self.dynamic_frame.winfo_children():
            w.destroy()
        self.choice_entries = []
        t = self.app.theme

        if self.type_var.get() == "multiple_choice":
            self.themed_label(self.dynamic_frame, "گزینه‌ها (گزینه‌ی صحیح را با دکمه‌ی رادیویی مشخص کن):",
                               bold=True).pack(anchor="e", pady=(0, 6))

            existing_choices = list(self.question.get("choices", ["", "", "", ""]))
            while len(existing_choices) < 4:
                existing_choices.append("")

            for i in range(4):
                row = self.themed_frame(self.dynamic_frame)
                row.pack(fill="x", pady=3)
                rb = tk.Radiobutton(
                    row, variable=self.correct_var, value=i, bg=t["bg"],
                    selectcolor=t["surface_alt"], activebackground=t["bg"], highlightthickness=0,
                )
                rb.pack(side="right")
                entry = self.themed_entry(row)
                entry.pack(side="right", fill="x", expand=True, padx=6)
                entry.insert(0, existing_choices[i])
                self.choice_entries.append(entry)
        else:
            self.themed_label(self.dynamic_frame, "حداکثر نمره‌ی این سؤال (نمره‌دهی توسط ادمین):",
                               bold=True).pack(anchor="e", pady=(0, 6))
            entry = self.themed_entry(self.dynamic_frame, textvariable=self.max_score_var, width=10)
            entry.pack(anchor="e")
            self.themed_label(
                self.dynamic_frame,
                "توجه: پاسخ این نوع سؤال متنیه و باید توسط ادمین\nدر چت ربات (با دستور /بررسی) نمره‌دهی شود.",
                muted=True, size=9,
            ).pack(anchor="e", pady=(10, 0))

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


# ═══════════════════════════════════════════════════════════════
#  پنجره‌ی ویرایش اطلاعات کلی آزمون
# ═══════════════════════════════════════════════════════════════
class ExamMetaDialog(ThemedDialog):
    def __init__(self, app, exam=None, exams=None):
        super().__init__(app, "آزمون جدید" if exam is None else "ویرایش اطلاعات آزمون")
        self.geometry("460x440")
        self.exam = exam or {}
        self.exams = exams or []
        t = self.app.theme

        self.themed_label(self, "عنوان آزمون:", bold=True).pack(anchor="e")
        self.title_var = tk.StringVar(value=self.exam.get("title", ""))
        self.themed_entry(self, textvariable=self.title_var).pack(fill="x", pady=(4, 12))

        self.themed_label(self, "توضیح کوتاه (در لیست آزمون‌ها نمایش داده می‌شود):", bold=True).pack(anchor="e")
        self.desc_var = tk.StringVar(value=self.exam.get("description", ""))
        self.themed_entry(self, textvariable=self.desc_var).pack(fill="x", pady=(4, 16))

        sep = tk.Frame(self, height=1, bg=t["border"])
        sep.pack(fill="x", pady=(0, 12))

        self.themed_label(self, "تنظیمات نمره‌دهی این آزمون", bold=True).pack(anchor="e", pady=(0, 8))

        settings = self.exam.get("settings", {})

        penalty_frame = self.themed_frame(self)
        penalty_frame.pack(fill="x", pady=4)
        self.themed_label(penalty_frame, "نمره‌ی منفی برای هر پاسخ غلط (۰ = بدون نمره منفی):", size=9).pack(anchor="e")
        self.penalty_var = tk.StringVar(value=str(settings.get("wrong_answer_penalty", 0)))
        self.themed_entry(penalty_frame, textvariable=self.penalty_var, width=10).pack(anchor="e", pady=(4, 0))

        self.require_all_var = tk.BooleanVar(value=settings.get("require_all_answers", False))
        cb = tk.Checkbutton(
            self, text="پاسخ به همه‌ی سؤالات این آزمون الزامی باشد",
            variable=self.require_all_var, bg=t["bg"], fg=t["ink"],
            selectcolor=t["surface_alt"], activebackground=t["bg"],
            font=(FONT_FAMILY, 10), highlightthickness=0,
        )
        cb.pack(anchor="e", pady=(12, 0))

        btn_frame = self.themed_frame(self)
        btn_frame.pack(fill="x", pady=(20, 0))
        self.themed_button(btn_frame, "ذخیره", self.on_save, primary=True).pack(side="right", padx=4)
        self.themed_button(btn_frame, "انصراف", self.destroy).pack(side="right", padx=4)

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


# ═══════════════════════════════════════════════════════════════
#  پنجره‌ی اصلی
# ═══════════════════════════════════════════════════════════════
class EditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ابزار مدیریت آزمون‌ها")
        self.geometry("980x600")
        self.minsize(760, 480)

        self.theme_name = "light"
        self.theme = THEMES[self.theme_name]

        self.exams = load_exams()
        self.history = HistoryManager(self.exams)

        self.selected_exam_index = None
        self.exam_search_var = tk.StringVar()
        self.question_search_var = tk.StringVar()
        self.exam_search_var.trace_add("write", lambda *a: self.refresh_exam_list())
        self.question_search_var.trace_add("write", lambda *a: self.refresh_question_list())

        # ایندکس‌های فیلترشده (برای نگاشت ردیف لیست‌باکس به ایندکس واقعی در self.exams)
        self._visible_exam_indices = []
        self._visible_question_indices = []

        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        self.build_ui()
        self.apply_theme()
        self.refresh_exam_list()

        self.bind_all("<Control-z>", lambda e: self.undo())
        self.bind_all("<Control-y>", lambda e: self.redo())
        self.bind_all("<Control-Shift-Z>", lambda e: self.redo())

    # ─────────────────────────────────────────
    #  چیدمان
    # ─────────────────────────────────────────
    def build_ui(self):
        self.root_frame = tk.Frame(self)
        self.root_frame.pack(fill="both", expand=True)

        # ── نوار بالا: Undo/Redo + تغییر تم + ذخیره ──
        self.toolbar = tk.Frame(self.root_frame)
        self.toolbar.pack(fill="x", side="top")

        self.undo_btn = self._toolbar_button(self.toolbar, "↩ Undo", self.undo)
        self.undo_btn.pack(side="right", padx=(10, 4), pady=8)
        self.redo_btn = self._toolbar_button(self.toolbar, "↪ Redo", self.redo)
        self.redo_btn.pack(side="right", padx=4, pady=8)

        self.theme_btn = self._toolbar_button(self.toolbar, "🌙 تم تاریک", self.toggle_theme)
        self.theme_btn.pack(side="left", padx=(4, 10), pady=8)

        self.save_btn = self._toolbar_button(self.toolbar, "💾 ذخیره در exams.json", self.save_all, primary=True)
        self.save_btn.pack(side="left", padx=4, pady=8)

        # ── بدنه‌ی اصلی: لیست آزمون‌ها (راست) + جزئیات و سؤالات (چپ) ──
        self.body = tk.Frame(self.root_frame)
        self.body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # ستون راست: لیست آزمون‌ها
        self.left_panel = tk.Frame(self.body, width=280)
        self.left_panel.pack(side="right", fill="y", padx=(12, 0))

        self.exam_list_label = tk.Label(self.left_panel, text="آزمون‌ها", font=(FONT_FAMILY, 12, "bold"))
        self.exam_list_label.pack(anchor="e", pady=(0, 6))

        self.exam_search_entry = self._search_entry(self.left_panel, self.exam_search_var, "جستجوی آزمون...")
        self.exam_search_entry.pack(fill="x", pady=(0, 8))

        exam_list_wrap = tk.Frame(self.left_panel)
        exam_list_wrap.pack(fill="both", expand=True)
        self.exam_listbox = tk.Listbox(exam_list_wrap, font=(FONT_FAMILY, 10), justify="right",
                                        activestyle="none", exportselection=False, relief="flat",
                                        highlightthickness=1, borderwidth=0)
        self.exam_listbox.pack(side="right", fill="both", expand=True)
        self.exam_listbox.bind("<<ListboxSelect>>", self.on_exam_select)

        exam_btns = tk.Frame(self.left_panel)
        exam_btns.pack(fill="x", pady=(8, 0))
        self.exam_action_buttons = [
            self._action_button(exam_btns, "➕ آزمون جدید", self.add_exam),
            self._action_button(exam_btns, "✏️ ویرایش اطلاعات", self.edit_exam_meta),
            self._action_button(exam_btns, "⧉ تکرار آزمون", self.duplicate_exam_action),
            self._action_button(exam_btns, "🗑 حذف آزمون", self.delete_exam),
        ]
        for b in self.exam_action_buttons:
            b.pack(fill="x", pady=2)

        # ستون چپ: جزئیات آزمون انتخاب‌شده و سؤالاتش
        self.right_panel = tk.Frame(self.body)
        self.right_panel.pack(side="right", fill="both", expand=True)

        self.exam_title_label = tk.Label(self.right_panel, text="آزمونی انتخاب نشده", font=(FONT_FAMILY, 14, "bold"))
        self.exam_title_label.pack(anchor="e")
        self.exam_desc_label = tk.Label(self.right_panel, text="", font=(FONT_FAMILY, 9))
        self.exam_desc_label.pack(anchor="e", pady=(2, 4))
        self.exam_settings_label = tk.Label(self.right_panel, text="", font=(FONT_FAMILY, 9, "bold"))
        self.exam_settings_label.pack(anchor="e", pady=(0, 10))

        self.sep1 = tk.Frame(self.right_panel, height=1)
        self.sep1.pack(fill="x", pady=(0, 10))

        search_row = tk.Frame(self.right_panel)
        search_row.pack(fill="x", pady=(0, 8))
        self.question_search_entry = self._search_entry(search_row, self.question_search_var, "جستجوی سؤال...")
        self.question_search_entry.pack(fill="x")

        cols_frame = tk.Frame(self.right_panel)
        cols_frame.pack(fill="both", expand=True)

        self.question_listbox = tk.Listbox(cols_frame, font=(FONT_FAMILY, 10), justify="right",
                                            activestyle="none", exportselection=False, relief="flat",
                                            highlightthickness=1, borderwidth=0)
        self.question_listbox.pack(side="right", fill="both", expand=True)

        q_btns = tk.Frame(cols_frame)
        q_btns.pack(side="left", fill="y", padx=(0, 8))
        self.question_action_buttons = [
            self._action_button(q_btns, "➕ سؤال جدید", self.add_question),
            self._action_button(q_btns, "✏️ ویرایش سؤال", self.edit_question),
            self._action_button(q_btns, "⧉ تکرار سؤال", self.duplicate_question_action),
            self._action_button(q_btns, "🗑 حذف سؤال", self.delete_question),
        ]
        for b in self.question_action_buttons:
            b.pack(fill="x", pady=2)
        self.sep2 = tk.Frame(q_btns, height=1)
        self.sep2.pack(fill="x", pady=8)
        self.move_buttons = [
            self._action_button(q_btns, "⬆ بالا", lambda: self.move_question(-1)),
            self._action_button(q_btns, "⬇ پایین", lambda: self.move_question(1)),
        ]
        for b in self.move_buttons:
            b.pack(fill="x", pady=2)

        # نوار وضعیت پایین
        self.status_label = tk.Label(self.root_frame, text="", font=(FONT_FAMILY, 9), anchor="e")
        self.status_label.pack(fill="x", side="bottom", padx=12, pady=(0, 6))

    def _toolbar_button(self, parent, text, command, primary=False):
        btn = tk.Button(parent, text=text, command=command, relief="flat",
                         font=(FONT_FAMILY, 9, "bold"), padx=12, pady=5, cursor="hand2", borderwidth=0)
        btn._is_primary = primary  # رنگ واقعی در apply_theme ست می‌شود
        return btn

    def _action_button(self, parent, text, command):
        btn = tk.Button(parent, text=text, command=command, relief="flat",
                         font=(FONT_FAMILY, 9), padx=10, pady=6, cursor="hand2", borderwidth=0, anchor="e")
        return btn

    def _search_entry(self, parent, var, placeholder):
        entry = tk.Entry(parent, textvariable=var, relief="flat", highlightthickness=1,
                          font=(FONT_FAMILY, 10), justify="right")
        return entry

    # ─────────────────────────────────────────
    #  تم
    # ─────────────────────────────────────────
    def toggle_theme(self):
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.theme = THEMES[self.theme_name]
        self.apply_theme()

    def apply_theme(self):
        t = self.theme
        is_dark = self.theme_name == "dark"

        self.configure(bg=t["bg"])
        self.root_frame.configure(bg=t["bg"])
        self.toolbar.configure(bg=t["surface"])
        self.body.configure(bg=t["bg"])
        self.left_panel.configure(bg=t["bg"])
        self.right_panel.configure(bg=t["bg"])
        self.status_label.configure(bg=t["bg"], fg=t["muted"])

        self.theme_btn.configure(text="☀️ تم روشن" if is_dark else "🌙 تم تاریک")

        for btn in (self.undo_btn, self.redo_btn, self.theme_btn, self.save_btn):
            primary = getattr(btn, "_is_primary", False)
            bg = t["primary"] if primary else t["surface_alt"]
            fg = "#ffffff" if primary else t["ink"]
            active = t["primary_d"] if primary else t["border"]
            btn.configure(bg=bg, fg=fg, activebackground=active, activeforeground=fg)

        for label in (self.exam_list_label, self.exam_title_label):
            label.configure(bg=t["bg"], fg=t["ink"])
        self.exam_desc_label.configure(bg=t["bg"], fg=t["muted"])
        self.exam_settings_label.configure(bg=t["bg"], fg=t["primary"])

        for sep in (self.sep1, self.sep2):
            sep.configure(bg=t["border"])

        for entry in (self.exam_search_entry, self.question_search_entry):
            entry.configure(bg=t["entry_bg"], fg=t["ink"], insertbackground=t["ink"],
                             highlightbackground=t["border"], highlightcolor=t["primary"])

        for lb in (self.exam_listbox, self.question_listbox):
            lb.configure(bg=t["list_bg"], fg=t["list_fg"], selectbackground=t["select_bg"],
                         selectforeground=t["ink"], highlightbackground=t["border"])

        all_action_buttons = self.exam_action_buttons + self.question_action_buttons + self.move_buttons
        for btn in all_action_buttons:
            btn.configure(bg=t["surface_alt"], fg=t["ink"], activebackground=t["border"], activeforeground=t["ink"])

        self.update_history_buttons()

    # ─────────────────────────────────────────
    #  Undo / Redo
    # ─────────────────────────────────────────
    def update_history_buttons(self):
        t = self.theme
        self.undo_btn.configure(state="normal" if self.history.can_undo() else "disabled")
        self.redo_btn.configure(state="normal" if self.history.can_redo() else "disabled")

    def push_history(self):
        """بعد از هر تغییر داده‌محور باید این صدا زده شود."""
        self.history.push(self.exams)
        self.update_history_buttons()

    def undo(self):
        new_state = self.history.undo()
        if new_state is None:
            return
        self.exams = new_state
        self.selected_exam_index = min(self.selected_exam_index or 0, max(len(self.exams) - 1, 0))
        self.refresh_exam_list()
        self.update_history_buttons()
        self.set_status("بازگردانی (Undo) انجام شد.")

    def redo(self):
        new_state = self.history.redo()
        if new_state is None:
            return
        self.exams = new_state
        self.selected_exam_index = min(self.selected_exam_index or 0, max(len(self.exams) - 1, 0))
        self.refresh_exam_list()
        self.update_history_buttons()
        self.set_status("انجام مجدد (Redo) انجام شد.")

    def set_status(self, text):
        self.status_label.configure(text=text)
        self.after(3000, lambda: self.status_label.configure(text=""))

    # ─────────────────────────────────────────
    #  کمکی‌ها
    # ─────────────────────────────────────────
    def current_exam(self):
        if self.selected_exam_index is None:
            return None
        if 0 <= self.selected_exam_index < len(self.exams):
            return self.exams[self.selected_exam_index]
        return None

    def refresh_exam_list(self):
        query = self.exam_search_var.get()
        self.exam_listbox.delete(0, "end")
        self._visible_exam_indices = []

        for real_idx, exam in enumerate(self.exams):
            title = exam.get("title", exam.get("id", ""))
            if not matches_search(title, query) and not matches_search(exam.get("description", ""), query):
                continue
            qcount = len(exam.get("questions", []))
            self.exam_listbox.insert("end", f"{title}  ({qcount} سؤال)")
            self._visible_exam_indices.append(real_idx)

        # سعی کن انتخاب فعلی را حفظ کنی، وگرنه اولین مورد قابل‌مشاهده را انتخاب کن
        if self.selected_exam_index in self._visible_exam_indices:
            list_pos = self._visible_exam_indices.index(self.selected_exam_index)
            self.exam_listbox.selection_set(list_pos)
        elif self._visible_exam_indices:
            self.selected_exam_index = self._visible_exam_indices[0]
            self.exam_listbox.selection_set(0)
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
        self._visible_question_indices = []
        exam = self.current_exam()
        if not exam:
            return

        query = self.question_search_var.get()
        for real_idx, q in enumerate(exam.get("questions", [])):
            text = q.get("question", "")
            if not matches_search(text, query):
                continue
            tag = "📝 تشریحی" if q.get("type") == "essay" else "🔘 چهارگزینه‌ای"
            preview = text[:60]
            self.question_listbox.insert("end", f"[{tag}]  {preview}")
            self._visible_question_indices.append(real_idx)

    # ── مدیریت آزمون‌ها ──
    def on_exam_select(self, event):
        sel = self.exam_listbox.curselection()
        if sel:
            self.selected_exam_index = self._visible_exam_indices[sel[0]]
            self.refresh_exam_detail()

    def add_exam(self):
        dialog = ExamMetaDialog(self, exams=self.exams)
        self.wait_window(dialog)
        if dialog.result:
            new_exam = dialog.result
            new_exam["questions"] = []
            self.exams.append(new_exam)
            self.selected_exam_index = len(self.exams) - 1
            self.push_history()
            self.refresh_exam_list()
            self.set_status(f"آزمون «{new_exam['title']}» اضافه شد.")

    def edit_exam_meta(self):
        exam = self.current_exam()
        if not exam:
            messagebox.showinfo("توجه", "ابتدا یک آزمون را انتخاب کنید.")
            return
        dialog = ExamMetaDialog(self, exam=exam, exams=self.exams)
        self.wait_window(dialog)
        if dialog.result:
            exam.update(dialog.result)
            self.push_history()
            self.refresh_exam_list()
            self.set_status("اطلاعات آزمون به‌روزرسانی شد.")

    def duplicate_exam_action(self):
        exam = self.current_exam()
        if not exam:
            messagebox.showinfo("توجه", "ابتدا یک آزمون را انتخاب کنید.")
            return
        new_exam = duplicate_exam(exam, self.exams)
        self.exams.insert(self.selected_exam_index + 1, new_exam)
        self.selected_exam_index += 1
        self.push_history()
        self.refresh_exam_list()
        self.set_status(f"آزمون تکرار شد: «{new_exam['title']}»")

    def delete_exam(self):
        exam = self.current_exam()
        if not exam:
            messagebox.showinfo("توجه", "ابتدا یک آزمون را انتخاب کنید.")
            return
        if messagebox.askyesno("تأیید حذف", f"آزمون «{exam.get('title')}» و همه‌ی سؤالاتش حذف شود؟"):
            self.exams.pop(self.selected_exam_index)
            self.selected_exam_index = None
            self.push_history()
            self.refresh_exam_list()
            self.set_status("آزمون حذف شد.")

    # ── مدیریت سؤالات ──
    def selected_question_index(self):
        """ایندکس واقعی سؤال انتخاب‌شده در exam['questions'] (با درنظرگرفتن فیلتر جستجو)."""
        sel = self.question_listbox.curselection()
        if not sel:
            return None
        return self._visible_question_indices[sel[0]]

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
            self.push_history()
            self.refresh_exam_list()
            self.set_status("سؤال جدید اضافه شد.")

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
            self.push_history()
            self.refresh_exam_list()
            self.set_status("سؤال ویرایش شد.")

    def duplicate_question_action(self):
        exam = self.current_exam()
        idx = self.selected_question_index()
        if not exam or idx is None:
            messagebox.showinfo("توجه", "ابتدا یک سؤال را انتخاب کنید.")
            return
        questions = exam["questions"]
        new_q = duplicate_question(questions[idx], questions)
        questions.insert(idx + 1, new_q)
        self.push_history()
        self.refresh_exam_list()
        self.set_status("سؤال تکرار شد.")

    def delete_question(self):
        exam = self.current_exam()
        idx = self.selected_question_index()
        if not exam or idx is None:
            messagebox.showinfo("توجه", "ابتدا یک سؤال را انتخاب کنید.")
            return
        if messagebox.askyesno("تأیید حذف", "این سؤال حذف شود؟"):
            exam["questions"].pop(idx)
            self.push_history()
            self.refresh_exam_list()
            self.set_status("سؤال حذف شد.")

    def move_question(self, direction):
        exam = self.current_exam()
        idx = self.selected_question_index()
        if not exam or idx is None:
            return
        new_idx = idx + direction
        questions = exam["questions"]
        if 0 <= new_idx < len(questions):
            questions[idx], questions[new_idx] = questions[new_idx], questions[idx]
            self.push_history()
            self.refresh_question_list()
            # تلاش برای انتخاب دوباره‌ی همان سؤال در موقعیت جدید (در صورت عدم فیلتر شدن)
            if new_idx in self._visible_question_indices:
                self.question_listbox.selection_set(self._visible_question_indices.index(new_idx))

    # ── ذخیره ──
    def save_all(self):
        try:
            save_exams(self.exams)
            self.set_status(f"ذخیره شد در: {EXAMS_FILE}")
        except Exception as e:
            messagebox.showerror("خطا", f"ذخیره‌سازی با خطا مواجه شد:\n{e}")


if __name__ == "__main__":
    app = EditorApp()
    app.mainloop()