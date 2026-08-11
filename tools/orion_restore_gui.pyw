import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext


PROJECT_ROOT = r"C:\Users\badee\Desktop\ORION_NEXT"
REMOTE = "origin"
DEFAULT_BRANCH = "phase2/core-intelligence-hardening"
BRANCH = (os.environ.get("ORION_RESTORE_BRANCH") or (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BRANCH)).strip() or DEFAULT_BRANCH


class OrionRestoreApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ORION Restore")
        self.root.geometry("820x680")
        self.root.minsize(720, 600)
        self.bg = "#101820"
        self.panel = "#17232d"
        self.fg = "#f2f5f7"
        self.muted = "#9aa8b2"
        self.accent = "#2eaadc"
        self.success = "#3fc36b"
        self.error = "#e05252"
        self.warning = "#e0a52e"
        self.root.configure(bg=self.bg)
        self.status_var = tk.StringVar(value="جاهز للاستعادة")
        self.files_var = tk.StringVar(value="0")
        self.added_var = tk.StringVar(value="0")
        self.updated_var = tk.StringVar(value="0")
        self.removed_var = tk.StringVar(value="0")
        self.running = False
        self._build_ui()

    def _build_ui(self):
        tk.Label(self.root, text="ORION RESTORE", font=("Segoe UI", 22, "bold"), bg=self.bg, fg=self.fg).pack(pady=(24, 2))
        tk.Label(self.root, text=f"GitHub → Git → Local  |  {BRANCH}", font=("Segoe UI", 10), bg=self.bg, fg=self.muted).pack()

        info = tk.Frame(self.root, bg=self.panel)
        info.pack(fill="x", padx=28, pady=12)
        self._info_row(info, "Repository", "ORION_NEXT")
        self._info_row(info, "Branch", BRANCH)
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

        self.button = tk.Button(self.root, text="⬇  استعادة الآن", command=self.start_restore, font=("Segoe UI", 14, "bold"), bg=self.accent, fg="white", activebackground=self.accent, activeforeground="white", relief="flat", bd=0, cursor="hand2", padx=30, pady=12)
        self.button.pack(pady=(10, 8))
        tk.Label(self.root, text="⚠ الاستعادة تستبدل تعديلات الملفات المتتبعة محليًا ولا تحذف الملفات غير المتتبعة.", font=("Segoe UI", 9), bg=self.bg, fg=self.warning).pack(pady=(0, 12))
        tk.Label(self.root, text="سجل العملية", font=("Segoe UI", 10, "bold"), bg=self.bg, fg=self.muted).pack(anchor="w", padx=28)
        self.output = scrolledtext.ScrolledText(self.root, height=12, bg="#0b1116", fg="#d9e1e6", insertbackground="white", font=("Consolas", 9), relief="flat", bd=0, wrap="word")
        self.output.pack(fill="both", expand=True, padx=28, pady=(6, 20))
        self._write("ORION Restore جاهز.")
        self._write(f"Project: {PROJECT_ROOT}")
        self._write(f"Source: {REMOTE}/{BRANCH}")
        self._write("main متاح بتمرير main كوسيط، وPhase 2 هو الافتراضي.")

    def _info_row(self, parent, label, value):
        row = tk.Frame(parent, bg=self.panel)
        row.pack(fill="x", padx=16, pady=5)
        tk.Label(row, text=f"{label}:", width=12, anchor="w", font=("Segoe UI", 9, "bold"), bg=self.panel, fg=self.muted).pack(side="left")
        tk.Label(row, text=value, anchor="w", font=("Segoe UI", 9), bg=self.panel, fg=self.fg).pack(side="left", fill="x", expand=True)

    def _write(self, text):
        self.output.insert("end", text + "\n")
        self.output.see("end")

    def _status(self, text, color):
        self.status_var.set(text)
        self.status_label.configure(fg=color)

    def _reset_stats(self):
        for var in (self.files_var, self.added_var, self.updated_var, self.removed_var):
            var.set("0")

    def _git(self, args):
        p = subprocess.Popen(["git", *args], cwd=PROJECT_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        lines = [line.rstrip() for line in p.stdout if line.rstrip()]
        return p.wait(), lines

    def _git_value(self, args):
        code, lines = self._git(args)
        if code != 0:
            raise RuntimeError("\n".join(lines) or "Git command failed.")
        return lines[-1].strip() if lines else ""

    def _stats(self, local_commit, remote_commit):
        code, lines = self._git(["diff", "--name-status", "--find-renames", local_commit, remote_commit])
        if code != 0:
            raise RuntimeError("\n".join(lines) or "تعذر حساب إحصائيات الملفات.")
        added = sum(1 for x in lines if x.startswith("A"))
        removed = sum(1 for x in lines if x.startswith("D"))
        updated = len(lines) - added - removed
        return len(lines), added, updated, removed

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
        self._status("جاري الفحص...", self.accent)
        threading.Thread(target=self._restore, daemon=True).start()

    def _restore(self):
        try:
            self._ui("=" * 58)
            self._ui("ORION RESTORE STARTED")
            self._ui("=" * 58)
            self._ui("[1/8] فحص مستودع Git...")
            if self._git_value(["rev-parse", "--is-inside-work-tree"]) != "true":
                raise RuntimeError("المجلد المحلي ليس مستودع Git صالحًا.")
            remote_url = self._git_value(["remote", "get-url", REMOTE])
            self._ui(f"Remote: {remote_url}")
            self._ui(f"[2/8] جلب GitHub/{BRANCH}...")
            code, lines = self._git(["fetch", REMOTE, BRANCH])
            if code != 0:
                raise RuntimeError("\n".join(lines) or "فشل جلب البيانات من GitHub.")
            for line in lines:
                self._ui(line)

            local_commit = self._git_value(["rev-parse", "HEAD"])
            remote_ref = f"{REMOTE}/{BRANCH}"
            remote_commit = self._git_value(["rev-parse", "--verify", remote_ref])
            current_branch = self._git_value(["branch", "--show-current"])
            self._ui(f"Local branch : {current_branch or '(detached HEAD)'}")
            self._ui(f"Target branch: {BRANCH}")
            self._ui(f"Local commit : {local_commit}")
            self._ui(f"GitHub commit: {remote_commit}")

            total, added, updated, removed = self._stats(local_commit, remote_commit)
            self._ui(f"Files affected: {total} | Added: {added} | Updated: {updated} | Removed: {removed}")
            self.root.after(0, self.files_var.set, str(total))
            self.root.after(0, self.added_var.set, str(added))
            self.root.after(0, self.updated_var.set, str(updated))
            self.root.after(0, self.removed_var.set, str(removed))

            if current_branch == BRANCH and local_commit == remote_commit:
                self.root.after(0, self._finish, True, f"المشروع مطابق بالفعل لـ GitHub/{BRANCH}.")
                return

            if not self._confirm(local_commit, remote_commit):
                self.root.after(0, self._cancel)
                return

            self._ui(f"[4/8] التحويل إلى الفرع الهدف {BRANCH}...")
            if current_branch != BRANCH:
                exists, _ = self._git(["show-ref", "--verify", "--quiet", f"refs/heads/{BRANCH}"])
                switch = ["switch", BRANCH] if exists == 0 else ["switch", "-c", BRANCH, "--track", remote_ref]
                code, lines = self._git(switch)
                if code != 0:
                    raise RuntimeError("تعذر التحويل إلى الفرع الهدف.\n" + ("\n".join(lines) or "Git switch failed."))
                for line in lines:
                    self._ui(line)

            self._ui("[5/8] استعادة الملفات المتتبعة...")
            code, lines = self._git(["reset", "--hard", remote_ref])
            if code != 0:
                raise RuntimeError("\n".join(lines) or "فشلت استعادة ملفات المشروع.")
            for line in lines:
                self._ui(line)

            self._ui("[6/8] مزامنة الوحدات الفرعية إن وجدت...")
            code, lines = self._git(["submodule", "update", "--init", "--recursive"])
            if code != 0:
                raise RuntimeError("\n".join(lines) or "فشل تحديث الوحدات الفرعية.")
            for line in lines:
                self._ui(line)

            final_commit = self._git_value(["rev-parse", "HEAD"])
            self._ui(f"[7/8] Commit النهائي: {final_commit}")
            if final_commit != remote_commit:
                raise RuntimeError(f"الـ commit المحلي النهائي لا يطابق GitHub/{BRANCH}.")
            code, _ = self._git(["diff", "--quiet", remote_ref, "HEAD"])
            if code != 0:
                raise RuntimeError("فشل التحقق النهائي من تطابق الملفات.")
            self._ui("[8/8] التحقق النهائي: PASS")
            self.root.after(0, self._finish, True, "تمت الاستعادة بنجاح.")
        except Exception as exc:
            self.root.after(0, self._fail, str(exc))

    def _ui(self, text):
        self.root.after(0, self._write, text)

    def _confirm(self, local_commit, remote_commit):
        event = threading.Event()
        result = {"ok": False}
        def ask():
            result["ok"] = messagebox.askyesno("تأكيد استعادة المشروع", f"الفرع الهدف: GitHub/{BRANCH}\n\nسيتم تبديل الفرع المحلي عند الحاجة ثم تنفيذ reset --hard للفرع الهدف.\n\nالملفات غير المتتبعة لن يتم حذفها.\n\nLocal: {local_commit[:12]}\nGitHub: {remote_commit[:12]}\n\nهل تريد المتابعة؟", icon="warning")
            event.set()
        self.root.after(0, ask)
        event.wait()
        return result["ok"]

    def _finish(self, success, message):
        self._write("=" * 58)
        self._write("ORION RESTORE COMPLETED SUCCESSFULLY" if success else "ORION RESTORE COMPLETED")
        self._write("GitHub → Git → Local")
        self._write(f"الفرع المحلي الحالي: {BRANCH}")
        self._write("الملفات غير المتتبعة تم الحفاظ عليها.")
        self._write("=" * 58)
        self._status(f"{message} ✅", self.success)
        self.running = False
        self.button.configure(state="normal", text="⬇  استعادة الآن")

    def _cancel(self):
        self._write("تم إلغاء الاستعادة بواسطة المستخدم.")
        self._status("تم إلغاء العملية", self.warning)
        self.running = False
        self.button.configure(state="normal", text="⬇  استعادة الآن")

    def _fail(self, message):
        self._write("ORION RESTORE ERROR")
        self._write(message)
        self._status("حدث خطأ ❌", self.error)
        self.running = False
        self.button.configure(state="normal", text="⬇  استعادة الآن")
        messagebox.showerror("ORION Restore", message)


def main():
    if not os.path.isdir(PROJECT_ROOT):
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("ORION Restore", f"مشروع ORION غير موجود:\n\n{PROJECT_ROOT}")
        root.destroy()
        return
    root = tk.Tk()
    OrionRestoreApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
