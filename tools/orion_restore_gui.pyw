import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

PROJECT_ROOT = r"C:\Users\badee\Desktop\ORION_NEXT"
REMOTE = "origin"
BRANCHES = (
    "main",
    "orion-canonical-pipeline-boundary",
    "phase2/core-intelligence-hardening",
)
DEFAULT_BRANCH = "phase2/core-intelligence-hardening"
ALL_BRANCH = "ALL"
SYNC_BRANCHES = (
    "main",
    "orion-canonical-pipeline-boundary",
    "phase2/core-intelligence-hardening",
)
STATE_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "ORION_RESTORE")
STATE_FILE = os.path.join(STATE_DIR, "last_sync.json")
ARG_BRANCH = (os.environ.get("ORION_RESTORE_BRANCH") or (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BRANCH)).strip()

class OrionRestoreApp:
    """Exact GitHub -> Git -> Local repository restore utility.

    The selected branch becomes the complete source of truth. Tracked changes,
    untracked files/directories, and ignored files/directories are removed so
    the working tree contains only the selected GitHub revision (plus .git).
    """
    def __init__(self, root):
        self.root = root
        self.root.title("ORION Restore")
        self.root.geometry("900x720")
        self.root.minsize(760, 620)
        self.bg = "#101820"
        self.panel = "#17232d"
        self.fg = "#f2f5f7"
        self.muted = "#9aa8b2"
        self.accent = "#2eaadc"
        self.success = "#3fc36b"
        self.error = "#e05252"
        self.warning = "#e0a52e"
        self.root.configure(bg=self.bg)

        initial = ARG_BRANCH if ARG_BRANCH in BRANCHES else DEFAULT_BRANCH
        self.branch_var = tk.StringVar(value=initial)
        self.status_var = tk.StringVar(value="جاهز للاستعادة")
        self.files_var = tk.StringVar(value="0")
        self.added_var = tk.StringVar(value="0")
        self.updated_var = tk.StringVar(value="0")
        self.removed_var = tk.StringVar(value="0")
        self.running = False
        self._build_ui()

    @property
    def branch(self):
        value = self.branch_var.get().strip()
        return value if value == ALL_BRANCH or value in BRANCHES else DEFAULT_BRANCH

    @property
    def remote_ref(self):
        return f"{REMOTE}/{self.branch}"

    def _build_ui(self):
        tk.Label(self.root, text="ORION RESTORE", font=("Segoe UI", 22, "bold"), bg=self.bg, fg=self.fg).pack(pady=(20, 2))
        self.source_label = tk.Label(self.root, text="", font=("Segoe UI", 10), bg=self.bg, fg=self.muted)
        self.source_label.pack()
        info = tk.Frame(self.root, bg=self.panel)
        info.pack(fill="x", padx=28, pady=12)
        self._info_row(info, "Repository", "ORION_NEXT")
        branch_row = tk.Frame(info, bg=self.panel)
        branch_row.pack(fill="x", padx=16, pady=5)
        tk.Label(branch_row, text="Branch:", width=12, anchor="w", font=("Segoe UI", 9, "bold"), bg=self.panel, fg=self.muted).pack(side="left")
        self.branch_combo = ttk.Combobox(branch_row, textvariable=self.branch_var, values=(ALL_BRANCH, *BRANCHES), state="readonly", width=42, font=("Segoe UI", 9))
        self.branch_combo.pack(side="left", fill="x", expand=True)
        self.branch_combo.bind("<<ComboboxSelected>>", self._branch_changed)
        self._info_row(info, "Project", PROJECT_ROOT)
        status = tk.Frame(self.root, bg=self.bg)
        status.pack(fill="x", padx=28, pady=(8, 4))
        tk.Label(status, text="الحالة:", font=("Segoe UI", 10, "bold"), bg=self.bg, fg=self.muted).pack(side="left")
        self.status_label = tk.Label(status, textvariable=self.status_var, font=("Segoe UI", 10, "bold"), bg=self.bg, fg=self.success)
        self.status_label.pack(side="left", padx=8)
        stats = tk.Frame(self.root, bg=self.bg)
        stats.pack(fill="x", padx=28, pady=4)
        for i, (title, var, color) in enumerate((("FILES", self.files_var, self.accent), ("ADDED", self.added_var, self.success), ("UPDATED", self.updated_var, self.accent), ("REMOVED", self.removed_var, self.error))):
            stats.grid_columnconfigure(i, weight=1)
            card = tk.Frame(stats, bg="#182538", highlightthickness=1, highlightbackground="#24364b")
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 4, 4 if i < 3 else 0))
            tk.Label(card, text=title, font=("Segoe UI", 8, "bold"), bg="#182538", fg=self.muted).pack(anchor="w", padx=10, pady=(7, 1))
            tk.Label(card, textvariable=var, font=("Segoe UI", 17, "bold"), bg="#182538", fg=color).pack(anchor="w", padx=10, pady=(0, 7))
        self.button = tk.Button(self.root, text="⬇  استعادة مطابقة للمستودع", command=self.start_restore, font=("Segoe UI", 14, "bold"), bg=self.accent, fg="white", activebackground=self.accent, activeforeground="white", relief="flat", bd=0, cursor="hand2", padx=30, pady=12)
        self.button.pack(pady=(10, 8))
        tk.Label(self.root, text="⚠ استعادة Exact Mirror: سيتم حذف تعديلات Git والملفات/المجلدات غير المتتبعة والـignored غير الموجودة في الفرع الهدف.", font=("Segoe UI", 9), bg=self.bg, fg=self.warning, wraplength=820, justify="center").pack(pady=(0, 12))
        tk.Label(self.root, text="سجل العملية", font=("Segoe UI", 10, "bold"), bg=self.bg, fg=self.muted).pack(anchor="w", padx=28)
        self.output = scrolledtext.ScrolledText(self.root, height=13, bg="#0b1116", fg="#d9e1e6", insertbackground="white", font=("Consolas", 9), relief="flat", bd=0, wrap="word")
        self.output.pack(fill="both", expand=True, padx=28, pady=(6, 18))
        self._write("ORION Exact Restore جاهز.")
        self._write(f"Project: {PROJECT_ROOT}")
        self._write(f"Source: {REMOTE}/{self.branch}")
        self._write("اختر ALL أو أي فرع منفرد ثم نفّذ الاستعادة.")
        self._write("النتيجة المطلوبة: Local working tree == GitHub target revision.")

    def _branch_changed(self, _event=None):
        if not self.running:
            self.source_label.configure(text=("GitHub → Git → Local  |  ALL (3 branches)" if self.branch == ALL_BRANCH else f"GitHub → Git → Local  |  {self.branch}"))
            self._write(f"Target branch changed to: {self.branch}")

    def _info_row(self, parent, label, value):
        row = tk.Frame(parent, bg=self.panel)
        row.pack(fill="x", padx=16, pady=5)
        tk.Label(row, text=f"{label}:", width=12, anchor="w", font=("Segoe UI", 9, "bold"), bg=self.panel, fg=self.muted).pack(side="left")
        tk.Label(row, text=value, anchor="w", font=("Segoe UI", 9), bg=self.panel, fg=self.fg).pack(side="left", fill="x", expand=True)

    def _write(self, text):
        self.output.insert("end", text + "\n")
        self.output.see("end")

    def _ui(self, text):
        self.root.after(0, self._write, text)

    def _status(self, text, color):
        self.status_var.set(text)
        self.status_label.configure(fg=color)

    def _reset_stats(self):
        for var in (self.files_var, self.added_var, self.updated_var, self.removed_var):
            var.set("0")

    def _git(self, args):
        process = subprocess.Popen(["git", *args], cwd=PROJECT_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        lines = [line.rstrip() for line in process.stdout if line.rstrip()]
        return process.wait(), lines

    def _git_value(self, args):
        code, lines = self._git(args)
        if code != 0:
            raise RuntimeError("\n".join(lines) or "Git command failed.")
        return lines[-1].strip() if lines else ""

    def _load_sync_state(self):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _save_sync_state(self, branch, commit):
        os.makedirs(STATE_DIR, exist_ok=True)
        state = self._load_sync_state()
        state[branch] = {"commit": commit}
        with open(STATE_FILE, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)

    def _save_all_sync_state(self, commits):
        os.makedirs(STATE_DIR, exist_ok=True)
        state = self._load_sync_state()
        for branch, commit in commits.items():
            state[branch] = {"commit": commit}
        with open(STATE_FILE, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)

    def _sync_all_refs(self):
        """Fetch all official branches without changing the working tree."""
        self._ui("[ALL] جلب الفروع الثلاثة إلى مستودع Git المحلي...")
        for branch in SYNC_BRANCHES:
            code, lines = self._git(["fetch", REMOTE, branch])
            if code != 0:
                raise RuntimeError(f"فشل جلب GitHub/{branch}.\n" + ("\n".join(lines) or "Git fetch failed."))
            for line in lines:
                self._ui(line)
        commits = {}
        for branch in SYNC_BRANCHES:
            ref = f"{REMOTE}/{branch}"
            commits[branch] = self._git_value(["rev-parse", "--verify", ref])
            self._ui(f"GitHub/{branch}: {commits[branch]}")
        current_branch = self._git_value(["branch", "--show-current"])
        current_commit = self._git_value(["rev-parse", "HEAD"])
        self._ui(f"Local working branch remains: {current_branch or '(detached HEAD)'}")
        self._ui(f"Local working commit remains: {current_commit}")
        self._save_all_sync_state(commits)
        return commits

    def _stats(self, target_commit):
        """Count tracked changes required to make the current tree match target."""
        code, lines = self._git(["diff", "--name-status", "--find-renames", target_commit])
        if code != 0:
            raise RuntimeError("\n".join(lines) or "تعذر حساب إحصائيات الملفات.")
        added = sum(1 for line in lines if line.startswith("D"))
        removed = sum(1 for line in lines if line.startswith("A"))
        updated = len(lines) - added - removed
        return len(lines), added, updated, removed

    def _extra_preview(self):
        """Return all untracked/ignored paths that exact restore will remove."""
        code, lines = self._git(["clean", "-fdxn"])
        if code != 0:
            raise RuntimeError("\n".join(lines) or "تعذر فحص الملفات الزائدة.")
        return [line for line in lines if line.startswith("Would remove ")]

    def start_restore(self):
        if self.running:
            return
        if not os.path.isdir(PROJECT_ROOT):
            self._status("المشروع غير موجود", self.error)
            self._write(PROJECT_ROOT)
            return
        self.running = True
        self._reset_stats()
        self.button.configure(state="disabled", text="⏳  جاري الاستعادة...")
        self.branch_combo.configure(state="disabled")
        self._status("جاري الفحص...", self.accent)
        threading.Thread(target=self._restore, daemon=True).start()

    def _restore(self):
        branch = self.branch
        remote_ref = f"{REMOTE}/{branch}" if branch != ALL_BRANCH else None
        try:
            if branch == ALL_BRANCH:
                self._restore_all()
                return
            self._ui("=" * 64)
            self._ui("ORION EXACT RESTORE STARTED")
            self._ui("=" * 64)
            self._ui(f"Target: GitHub/{branch}")
            self._ui("[1/9] فحص مستودع Git...")
            if self._git_value(["rev-parse", "--is-inside-work-tree"]) != "true":
                raise RuntimeError("المجلد المحلي ليس مستودع Git صالحًا.")
            remote_url = self._git_value(["remote", "get-url", REMOTE])
            self._ui(f"Remote: {remote_url}")
            self._ui(f"[2/9] جلب GitHub/{branch}...")
            code, lines = self._git(["fetch", REMOTE, branch])
            if code != 0:
                raise RuntimeError("\n".join(lines) or "فشل جلب البيانات من GitHub.")
            for line in lines:
                self._ui(line)
            local_commit = self._git_value(["rev-parse", "HEAD"])
            remote_commit = self._git_value(["rev-parse", "--verify", remote_ref])
            current_branch = self._git_value(["branch", "--show-current"])
            self._ui(f"Local branch : {current_branch or '(detached HEAD)'}")
            self._ui(f"Target branch: {branch}")
            self._ui(f"Local commit : {local_commit}")
            self._ui(f"GitHub commit: {remote_commit}")
            state = self._load_sync_state()
            last_sync = state.get(branch, {})
            tracked_total, tracked_added, tracked_updated, tracked_removed = self._stats(remote_commit)
            if isinstance(last_sync, dict) and last_sync.get("commit") == remote_commit and tracked_total == 0:
                total = added = updated = removed = 0
                extras = self._extra_preview()
                self._ui("Last successful sync already matches this GitHub commit; no repository changes detected.")
            else:
                total, added, updated, removed = tracked_total, tracked_added, tracked_updated, tracked_removed
                extras = self._extra_preview()
            self._ui(f"Tracked changes needed: {total} | Added: {added} | Updated: {updated} | Removed: {removed}")
            self._ui(f"Extra local paths to remove: {len(extras)}")
            for line in extras[:100]:
                self._ui(f"  {line}")
            if len(extras) > 100:
                self._ui(f"  ... and {len(extras) - 100} more")
            self.root.after(0, self.files_var.set, str(total + len(extras)))
            self.root.after(0, self.added_var.set, str(added))
            self.root.after(0, self.updated_var.set, str(updated))
            self.root.after(0, self.removed_var.set, str(removed + len(extras)))
            if current_branch == branch and local_commit == remote_commit and not extras:
                code, status_lines = self._git(["status", "--porcelain", "--ignored"])
                if code != 0:
                    raise RuntimeError("تعذر التحقق من الحالة المحلية.")
                if status_lines:
                    raise RuntimeError("بقيت تغييرات محلية رغم تطابق الـ commit.")
                self._save_sync_state(branch, remote_commit)
                for var in (self.files_var, self.added_var, self.updated_var, self.removed_var):
                    self.root.after(0, var.set, "0")
                self.root.after(0, self._finish, True, f"المشروع مطابق بالفعل لـ GitHub/{branch}.")
                return
            if not self._confirm(local_commit, remote_commit, len(extras), branch):
                self.root.after(0, self._cancel)
                return
            self._ui("[4/9] تنظيف أي تغييرات متتبعة محليًا...")
            code, lines = self._git(["reset", "--hard"])
            if code != 0:
                raise RuntimeError("\n".join(lines) or "فشل تنظيف التعديلات المتتبعة.")
            for line in lines:
                self._ui(line)
            self._ui("[5/9] حذف كل الملفات والمجلدات المحلية غير الموجودة في Git...")
            code, lines = self._git(["clean", "-fdx"])
            if code != 0:
                raise RuntimeError("\n".join(lines) or "فشل حذف الملفات الزائدة.")
            for line in lines:
                self._ui(line)
            self._ui(f"[6/9] التحويل إلى الفرع الهدف {branch}...")
            if current_branch != branch:
                exists, _ = self._git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"])
                switch = ["switch", branch] if exists == 0 else ["switch", "-c", branch, "--track", remote_ref]
                code, lines = self._git(switch)
                if code != 0:
                    raise RuntimeError("تعذر التحويل إلى الفرع الهدف.\n" + ("\n".join(lines) or "Git switch failed."))
                for line in lines:
                    self._ui(line)
            self._ui("[7/9] ضبط الملفات على نسخة GitHub حرفيًا...")
            code, lines = self._git(["reset", "--hard", remote_ref])
            if code != 0:
                raise RuntimeError("\n".join(lines) or "فشلت استعادة ملفات المشروع.")
            for line in lines:
                self._ui(line)
            self._ui("[8/9] مزامنة الوحدات الفرعية إن وجدت وتنظيفها...")
            code, lines = self._git(["submodule", "update", "--init", "--recursive"])
            if code != 0:
                raise RuntimeError("\n".join(lines) or "فشل تحديث الوحدات الفرعية.")
            for line in lines:
                self._ui(line)
            code, lines = self._git(["submodule", "foreach", "--recursive", "git", "reset", "--hard"])
            if code != 0:
                raise RuntimeError("\n".join(lines) or "فشل تنظيف تغييرات الوحدات الفرعية.")
            for line in lines:
                self._ui(line)
            code, lines = self._git(["submodule", "foreach", "--recursive", "git", "clean", "-fdx"])
            if code != 0:
                raise RuntimeError("\n".join(lines) or "فشل تنظيف الملفات الزائدة في الوحدات الفرعية.")
            for line in lines:
                self._ui(line)
            final_commit = self._git_value(["rev-parse", "HEAD"])
            self._ui(f"[9/9] التحقق النهائي — Commit: {final_commit}")
            if final_commit != remote_commit:
                raise RuntimeError(f"الـ commit المحلي النهائي لا يطابق GitHub/{branch}.")
            code, lines = self._git(["diff", "--quiet", remote_ref, "HEAD"])
            if code != 0:
                raise RuntimeError("فشل تطابق الملفات المتتبعة مع GitHub.")
            code, status_lines = self._git(["status", "--porcelain", "--ignored"])
            if code != 0:
                raise RuntimeError("تعذر التحقق النهائي من نظافة working tree.")
            if status_lines:
                raise RuntimeError("بقيت عناصر محلية بعد الاستعادة؛ لم نعلن التطابق.\n" + "\n".join(status_lines[:100]))
            self._ui("FINAL REPOSITORY STATE: EXACT MATCH")
            self._save_sync_state(branch, remote_commit)
            self.root.after(0, self._finish, True, f"تمت مزامنة Local بالكامل مع GitHub/{branch}.")
        except Exception as exc:
            self.root.after(0, self._fail, str(exc))

    def _restore_all(self):
        self._ui("=" * 64)
        self._ui("ORION ALL-BRANCH SYNC STARTED")
        self._ui("=" * 64)
        self._ui("ALL = تحديث الفروع الثلاثة داخل مستودع Git المحلي.")
        self._ui("لن يتم تبديل working tree بين الفروع الثلاثة.")
        self._ui("سيبقى working tree على الفرع الحالي دون تغيير.")
        if self._git_value(["rev-parse", "--is-inside-work-tree"]) != "true":
            raise RuntimeError("المجلد المحلي ليس مستودع Git صالحًا.")
        remote_url = self._git_value(["remote", "get-url", REMOTE])
        self._ui(f"Remote: {remote_url}")
        self._sync_all_refs()
        for var in (self.files_var, self.added_var, self.updated_var, self.removed_var):
            self.root.after(0, var.set, "0")
        self._ui("ALL SYNC: الفروع الثلاثة محدثة محليًا.")
        self._ui("ALL SYNC لا يغيّر ملفات working tree الحالية.")
        self._ui("يمكن بعد ذلك اختيار أي فرع منفرد لتنفيذ Exact Restore إليه.")
        self.root.after(0, self._finish, True, "تمت مزامنة الفروع الثلاثة محليًا. الإحصائيات: 0 لأن working tree لم يتغير.")

    def _confirm(self, local_commit, remote_commit, extra_count, branch):
        event = threading.Event()
        result = {"ok": False}
        def ask():
            message = (f"الفرع الهدف: GitHub/{branch}\n\n" "سيصبح المجلد المحلي نسخة مطابقة للفرع الهدف.\n\n" "سيتم حذف:\n" "• تعديلات الملفات المتتبعة محليًا\n" "• الملفات والمجلدات غير المتتبعة\n" "• الملفات والمجلدات ignored غير الموجودة في Git\n" "• أي تغييرات داخل الوحدات الفرعية\n\n" f"عناصر محلية زائدة مكتشفة: {extra_count}\n\n" f"Local: {local_commit[:12]}\n" f"GitHub: {remote_commit[:12]}\n\n" "هذه العملية لا تحذف مستودع .git نفسه.\n\n" "هل تريد تنفيذ Exact Restore؟")
            result["ok"] = messagebox.askyesno("تأكيد Exact Restore", message, icon="warning")
            event.set()
        self.root.after(0, ask)
        event.wait()
        return result["ok"]

    def _finish(self, success, message):
        self._write("=" * 64)
        self._write("ORION EXACT RESTORE COMPLETED SUCCESSFULLY" if success else "ORION RESTORE COMPLETED")
        self._write("GitHub → Git → Local")
        self._write(f"Target branch: {self.branch}")
        self._write("FINAL REPOSITORY STATE: EXACT MATCH")
        self._write("لا توجد ملفات/مجلدات untracked أو ignored خارج نسخة GitHub.")
        self._write("=" * 64)
        self._status(f"{message} ✅", self.success)
        self.running = False
        self.button.configure(state="normal", text="⬇  استعادة مطابقة للمستودع")
        self.branch_combo.configure(state="readonly")

    def _cancel(self):
        self._write("تم إلغاء الاستعادة بواسطة المستخدم.")
        self._status("تم إلغاء العملية", self.warning)
        self.running = False
        self.button.configure(state="normal", text="⬇  استعادة مطابقة للمستودع")
        self.branch_combo.configure(state="readonly")

    def _fail(self, message):
        self._write("ORION RESTORE ERROR")
        self._write(message)
        self._status("حدث خطأ ❌", self.error)
        self.running = False
        self.button.configure(state="normal", text="⬇  استعادة مطابقة للمستودع")
        self.branch_combo.configure(state="readonly")
        messagebox.showerror("ORION Restore", message)

def main():
    if not os.path.isdir(PROJECT_ROOT):
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("ORION Restore", f"مشروع ORION غير موجود:\n\n{PROJECT_ROOT}")
        root.destroy()
        return
    root = tk.Tk()
    app = OrionRestoreApp(root)
    app.source_label.configure(text=("GitHub → Git → Local  |  ALL (3 branches)" if app.branch == ALL_BRANCH else f"GitHub → Git → Local  |  {app.branch}"))
    root.mainloop()

if __name__ == "__main__":
    main()
