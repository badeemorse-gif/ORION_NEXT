import os
import subprocess
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox


# ============================================================
# ORION REPOSITORY RESTORE
# ============================================================

PROJECT_ROOT = r"C:\Users\badee\Desktop\ORION_NEXT"
REMOTE = "origin"
BRANCH = "main"


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
        self.restore_running = False

        # Statistics only — does not change the restore mechanism.
        self.files_var = tk.StringVar(value="0")
        self.added_var = tk.StringVar(value="0")
        self.updated_var = tk.StringVar(value="0")
        self.removed_var = tk.StringVar(value="0")

        self._build_ui()

    # ========================================================
    # UI
    # ========================================================

    def _build_ui(self):
        header = tk.Frame(
            self.root,
            bg=self.bg,
        )
        header.pack(
            fill="x",
            padx=28,
            pady=(24, 10),
        )

        title = tk.Label(
            header,
            text="ORION RESTORE",
            font=("Segoe UI", 22, "bold"),
            bg=self.bg,
            fg=self.fg,
        )
        title.pack()

        subtitle = tk.Label(
            header,
            text="GitHub → Git → Local",
            font=("Segoe UI", 10),
            bg=self.bg,
            fg=self.muted,
        )
        subtitle.pack(pady=(2, 0))

        info = tk.Frame(
            self.root,
            bg=self.panel,
        )
        info.pack(
            fill="x",
            padx=28,
            pady=12,
        )

        self._info_row(info, "Repository", "ORION_NEXT")
        self._info_row(info, "Branch", BRANCH)
        self._info_row(info, "Project", PROJECT_ROOT)

        status_frame = tk.Frame(
            self.root,
            bg=self.bg,
        )
        status_frame.pack(
            fill="x",
            padx=28,
            pady=(12, 6),
        )

        tk.Label(
            status_frame,
            text="الحالة:",
            font=("Segoe UI", 10, "bold"),
            bg=self.bg,
            fg=self.muted,
        ).pack(side="left")

        self.status_label = tk.Label(
            status_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 10, "bold"),
            bg=self.bg,
            fg=self.success,
        )
        self.status_label.pack(
            side="left",
            padx=(8, 0),
        )

        # ========================================================
        # RESTORE STATISTICS
        # Read-only information about the difference before restore.
        # ========================================================

        stats_frame = tk.Frame(
            self.root,
            bg=self.bg,
        )
        stats_frame.pack(
            fill="x",
            padx=28,
            pady=(4, 4),
        )

        self._stat_card(
            stats_frame,
            "FILES RESTORED",
            self.files_var,
            self.accent,
            0,
        )
        self._stat_card(
            stats_frame,
            "ADDED",
            self.added_var,
            self.success,
            1,
        )
        self._stat_card(
            stats_frame,
            "UPDATED",
            self.updated_var,
            self.accent,
            2,
        )
        self._stat_card(
            stats_frame,
            "REMOVED",
            self.removed_var,
            self.error,
            3,
        )

        self.restore_button = tk.Button(
            self.root,
            text="⬇  استعادة الآن",
            command=self.start_restore,
            font=("Segoe UI", 14, "bold"),
            bg=self.accent,
            fg="white",
            activebackground=self.accent,
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=30,
            pady=12,
        )
        self.restore_button.pack(
            pady=(10, 8),
        )

        warning = tk.Label(
            self.root,
            text="⚠ الاستعادة تستبدل تعديلات الملفات المتتبعة محليًا ولا تحذف الملفات غير المتتبعة.",
            font=("Segoe UI", 9),
            bg=self.bg,
            fg=self.warning,
        )
        warning.pack(
            pady=(0, 12),
        )

        output_label = tk.Label(
            self.root,
            text="سجل العملية",
            font=("Segoe UI", 10, "bold"),
            bg=self.bg,
            fg=self.muted,
        )
        output_label.pack(
            anchor="w",
            padx=28,
        )

        self.output = scrolledtext.ScrolledText(
            self.root,
            height=12,
            bg="#0b1116",
            fg="#d9e1e6",
            insertbackground="white",
            font=("Consolas", 9),
            relief="flat",
            bd=0,
            wrap="word",
        )
        self.output.pack(
            fill="both",
            expand=True,
            padx=28,
            pady=(6, 20),
        )

        self._write_output("ORION Restore جاهز.")
        self._write_output(f"Project: {PROJECT_ROOT}")
        self._write_output("Source: origin/main")
        self._write_output("اضغط «استعادة الآن» لجلب النسخة الكاملة من GitHub.")

    def _info_row(self, parent, label, value):
        row = tk.Frame(
            parent,
            bg=self.panel,
        )
        row.pack(
            fill="x",
            padx=16,
            pady=5,
        )

        tk.Label(
            row,
            text=f"{label}:",
            width=12,
            anchor="w",
            font=("Segoe UI", 9, "bold"),
            bg=self.panel,
            fg=self.muted,
        ).pack(side="left")

        tk.Label(
            row,
            text=value,
            anchor="w",
            font=("Segoe UI", 9),
            bg=self.panel,
            fg=self.fg,
        ).pack(
            side="left",
            fill="x",
            expand=True,
        )

    def _stat_card(self, parent, title, variable, value_color, column):
        parent.grid_columnconfigure(column, weight=1)

        card = tk.Frame(
            parent,
            bg="#182538",
            highlightthickness=1,
            highlightbackground="#24364b",
        )
        card.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else 4, 4 if column < 3 else 0),
        )

        tk.Label(
            card,
            text=title,
            font=("Segoe UI", 8, "bold"),
            bg="#182538",
            fg=self.muted,
        ).pack(
            anchor="w",
            padx=10,
            pady=(7, 1),
        )

        tk.Label(
            card,
            textvariable=variable,
            font=("Segoe UI", 17, "bold"),
            bg="#182538",
            fg=value_color,
        ).pack(
            anchor="w",
            padx=10,
            pady=(0, 7),
        )

    def _reset_statistics(self):
        self.files_var.set("0")
        self.added_var.set("0")
        self.updated_var.set("0")
        self.removed_var.set("0")

    def _calculate_statistics(self, local_commit, remote_commit):
        # Read-only comparison. No files are changed by this function.
        return_code, lines = self._run_git(
            [
                "diff",
                "--name-status",
                "--find-renames",
                local_commit,
                remote_commit,
            ]
        )

        if return_code != 0:
            raise RuntimeError(
                "\n".join(lines)
                or "تعذر حساب إحصائيات الملفات."
            )

        added = 0
        updated = 0
        removed = 0

        for line in lines:
            if not line.strip():
                continue

            status = line.split("\t", 1)[0].strip()

            if status.startswith("A"):
                added += 1
            elif status.startswith("D"):
                removed += 1
            else:
                updated += 1

        total = added + updated + removed

        return total, added, updated, removed

    def _write_output(self, text):
        self.output.insert(
            "end",
            text + "\n",
        )
        self.output.see("end")

    def _set_status(self, text, color):
        self.status_var.set(text)
        self.status_label.configure(
            fg=color
        )

    # ========================================================
    # GIT
    # ========================================================

    def _run_git(self, arguments):
        process = subprocess.Popen(
            ["git", *arguments],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        output_lines = []

        for line in process.stdout:
            line = line.rstrip()
            if line:
                output_lines.append(line)

        return_code = process.wait()

        return return_code, output_lines

    def _git_value(self, arguments):
        return_code, lines = self._run_git(arguments)

        if return_code != 0:
            raise RuntimeError(
                "\n".join(lines)
                or "Git command failed."
            )

        return lines[-1].strip() if lines else ""

    # ========================================================
    # START RESTORE
    # ========================================================

    def start_restore(self):
        if self.restore_running:
            return

        if not os.path.isdir(PROJECT_ROOT):
            self._set_status(
                "المشروع غير موجود",
                self.error,
            )
            self._write_output("")
            self._write_output(
                "ERROR: ORION_NEXT project directory not found."
            )
            self._write_output(PROJECT_ROOT)
            return

        self.restore_running = True
        self._reset_statistics()

        self.restore_button.configure(
            state="disabled",
            text="⏳  جاري الاستعادة...",
        )

        self._set_status(
            "جاري الفحص...",
            self.accent,
        )

        self._write_output("")
        self._write_output("=" * 58)
        self._write_output("ORION RESTORE STARTED")
        self._write_output("=" * 58)

        thread = threading.Thread(
            target=self._run_restore,
            daemon=True,
        )
        thread.start()

    def _run_restore(self):
        try:
            self.root.after(
                0,
                self._write_output,
                "[1/7] فحص مستودع Git...",
            )

            value = self._git_value(
                ["rev-parse", "--is-inside-work-tree"]
            )

            if value != "true":
                raise RuntimeError(
                    "المجلد المحلي ليس مستودع Git صالحًا."
                )

            self.root.after(
                0,
                self._write_output,
                "OK",
            )

            self.root.after(
                0,
                self._write_output,
                "[2/7] فحص remote origin...",
            )

            remote_url = self._git_value(
                ["remote", "get-url", REMOTE]
            )

            self.root.after(
                0,
                self._write_output,
                f"Remote: {remote_url}",
            )

            self.root.after(
                0,
                self._write_output,
                "[3/7] جلب آخر نسخة من GitHub main...",
            )

            return_code, lines = self._run_git(
                ["fetch", REMOTE, BRANCH]
            )

            if return_code != 0:
                raise RuntimeError(
                    "\n".join(lines)
                    or "فشل جلب البيانات من GitHub."
                )

            for line in lines:
                self.root.after(
                    0,
                    self._write_output,
                    line,
                )

            local_commit = self._git_value(
                ["rev-parse", "HEAD"]
            )

            remote_commit = self._git_value(
                ["rev-parse", f"{REMOTE}/{BRANCH}"]
            )

            self.root.after(
                0,
                self._write_output,
                f"Local commit : {local_commit}",
            )

            self.root.after(
                0,
                self._write_output,
                f"GitHub commit: {remote_commit}",
            )

            # Statistics only. The existing restore sequence remains unchanged.
            total, added, updated, removed = self._calculate_statistics(
                local_commit,
                remote_commit,
            )

            self.root.after(0, self.files_var.set, str(total))
            self.root.after(0, self.added_var.set, str(added))
            self.root.after(0, self.updated_var.set, str(updated))
            self.root.after(0, self.removed_var.set, str(removed))

            self.root.after(
                0,
                self._write_output,
                f"Files affected: {total} | Added: {added} | Updated: {updated} | Removed: {removed}",
            )

            if local_commit == remote_commit:
                self.root.after(
                    0,
                    self._restore_finished,
                    True,
                    "المشروع المحلي مطابق بالفعل لـ GitHub/main.",
                )
                return

            confirmation = self._ask_confirmation(
                local_commit,
                remote_commit,
            )

            if not confirmation:
                self.root.after(
                    0,
                    self._restore_cancelled,
                )
                return

            self.root.after(
                0,
                self._write_output,
                "[4/7] استعادة جميع الملفات المتتبعة...",
            )

            return_code, lines = self._run_git(
                [
                    "reset",
                    "--hard",
                    f"{REMOTE}/{BRANCH}",
                ]
            )

            if return_code != 0:
                raise RuntimeError(
                    "\n".join(lines)
                    or "فشلت استعادة ملفات المشروع."
                )

            for line in lines:
                self.root.after(
                    0,
                    self._write_output,
                    line,
                )

            self.root.after(
                0,
                self._write_output,
                "[5/7] تحديث الوحدات الفرعية إن وجدت...",
            )

            return_code, lines = self._run_git(
                [
                    "submodule",
                    "update",
                    "--init",
                    "--recursive",
                ]
            )

            if return_code != 0:
                raise RuntimeError(
                    "\n".join(lines)
                    or "فشل تحديث الوحدات الفرعية."
                )

            for line in lines:
                self.root.after(
                    0,
                    self._write_output,
                    line,
                )

            final_commit = self._git_value(
                ["rev-parse", "HEAD"]
            )

            self.root.after(
                0,
                self._write_output,
                "[6/7] التحقق من الـ commit النهائي...",
            )

            if final_commit != remote_commit:
                raise RuntimeError(
                    "الـ commit المحلي النهائي لا يطابق GitHub/main."
                )

            self.root.after(
                0,
                self._write_output,
                f"Commit verified: {final_commit}",
            )

            self.root.after(
                0,
                self._write_output,
                "[7/7] التحقق من تطابق الملفات المتتبعة...",
            )

            return_code, _ = self._run_git(
                [
                    "diff",
                    "--quiet",
                    f"{REMOTE}/{BRANCH}",
                    "HEAD",
                ]
            )

            if return_code != 0:
                raise RuntimeError(
                    "فشل التحقق النهائي من تطابق المشروع."
                )

            self.root.after(
                0,
                self._restore_finished,
                True,
                "تمت استعادة المشروع بالكامل بنجاح.",
            )

        except Exception as exc:
            self.root.after(
                0,
                self._restore_failed,
                str(exc),
            )

    # ========================================================
    # CONFIRMATION
    # ========================================================

    def _ask_confirmation(self, local_commit, remote_commit):
        event = threading.Event()
        result = {"value": False}

        def ask():
            result["value"] = messagebox.askyesno(
                "تأكيد استعادة المشروع",
                "GitHub/main يحتوي على نسخة أحدث من المشروع.\n\n"
                "سيتم استبدال جميع تعديلات الملفات المتتبعة "
                "الموجودة محليًا وجعلها مطابقة لـ GitHub/main.\n\n"
                "الملفات غير المتتبعة لن يتم حذفها.\n\n"
                f"Local:\n{local_commit[:12]}\n\n"
                f"GitHub:\n{remote_commit[:12]}\n\n"
                "هل تريد المتابعة؟",
                icon="warning",
            )
            event.set()

        self.root.after(0, ask)
        event.wait()
        return result["value"]

    # ========================================================
    # RESULTS
    # ========================================================

    def _restore_finished(self, success, message):
        self._write_output("")
        self._write_output("=" * 58)

        if success:
            self._write_output(
                "ORION RESTORE COMPLETED SUCCESSFULLY"
            )
            self._set_status(
                f"{message} ✅",
                self.success,
            )
        else:
            self._write_output(
                "ORION RESTORE COMPLETED"
            )
            self._set_status(
                message,
                self.success,
            )

        self._write_output(
            "GitHub → Git → Local"
        )
        self._write_output(
            "الملفات المتتبعة أصبحت مطابقة لـ origin/main."
        )
        self._write_output(
            "الملفات المحلية غير المتتبعة تم الحفاظ عليها."
        )
        self._write_output("=" * 58)

        self.restore_running = False

        self.restore_button.configure(
            state="normal",
            text="⬇  استعادة الآن",
        )

    def _restore_cancelled(self):
        self._write_output("")
        self._write_output(
            "تم إلغاء الاستعادة بواسطة المستخدم."
        )

        self._set_status(
            "تم إلغاء العملية",
            self.warning,
        )

        self.restore_running = False

        self.restore_button.configure(
            state="normal",
            text="⬇  استعادة الآن",
        )

    def _restore_failed(self, message):
        self._write_output("")
        self._write_output(
            "ORION RESTORE ERROR"
        )
        self._write_output(message)

        self._set_status(
            "حدث خطأ ❌",
            self.error,
        )

        self.restore_running = False

        self.restore_button.configure(
            state="normal",
            text="⬇  استعادة الآن",
        )

        messagebox.showerror(
            "ORION Restore",
            message,
        )


def main():
    if not os.path.isdir(PROJECT_ROOT):
        root = tk.Tk()
        root.withdraw()

        messagebox.showerror(
            "ORION Restore",
            f"مشروع ORION غير موجود:\n\n{PROJECT_ROOT}",
        )

        root.destroy()
        return

    root = tk.Tk()
    OrionRestoreApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
