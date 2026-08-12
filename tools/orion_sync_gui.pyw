import os
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk


PROJECT_ROOT = r"C:\Users\badee\Desktop\ORION_NEXT"
SYNC_SCRIPT = os.path.join(PROJECT_ROOT, "tools", "orion_sync.bat")
BRANCHES = (
    "main",
    "orion-canonical-pipeline-boundary",
    "phase2/core-intelligence-hardening",
)
DEFAULT_BRANCH = "phase2/core-intelligence-hardening"


class OrionSyncApp:
    """Repository-first GitHub -> Local synchronization UI."""

    def __init__(self, root):
        self.root = root
        self.root.title("ORION Sync")
        self.root.geometry("820x620")
        self.root.minsize(700, 540)

        self.bg = "#101820"
        self.panel = "#17232d"
        self.fg = "#f2f5f7"
        self.muted = "#9aa8b2"
        self.accent = "#2eaadc"
        self.success = "#3fc36b"
        self.error = "#e05252"
        self.warning = "#e0a52e"

        self.root.configure(bg=self.bg)
        self.branch_var = tk.StringVar(value=DEFAULT_BRANCH)
        self.status_var = tk.StringVar(value="جاهز للمزامنة")
        self.running = False

        self._build_ui()

    @property
    def branch(self):
        value = self.branch_var.get().strip()
        return value if value in BRANCHES else DEFAULT_BRANCH

    def _build_ui(self):
        header = tk.Frame(self.root, bg=self.bg)
        header.pack(fill="x", padx=28, pady=(24, 10))

        tk.Label(
            header,
            text="ORION SYNC",
            font=("Segoe UI", 22, "bold"),
            bg=self.bg,
            fg=self.fg,
        ).pack()
        tk.Label(
            header,
            text="GitHub → Git → Local",
            font=("Segoe UI", 10),
            bg=self.bg,
            fg=self.muted,
        ).pack(pady=(2, 0))

        info = tk.Frame(self.root, bg=self.panel)
        info.pack(fill="x", padx=28, pady=12)
        self._info_row(info, "Repository", "ORION_NEXT")

        branch_row = tk.Frame(info, bg=self.panel)
        branch_row.pack(fill="x", padx=16, pady=5)
        tk.Label(
            branch_row,
            text="Branch:",
            width=12,
            anchor="w",
            font=("Segoe UI", 9, "bold"),
            bg=self.panel,
            fg=self.muted,
        ).pack(side="left")
        self.branch_combo = ttk.Combobox(
            branch_row,
            textvariable=self.branch_var,
            values=BRANCHES,
            state="readonly",
            width=42,
            font=("Segoe UI", 9),
        )
        self.branch_combo.pack(side="left", fill="x", expand=True)

        self._info_row(info, "Project", PROJECT_ROOT)

        status_frame = tk.Frame(self.root, bg=self.bg)
        status_frame.pack(fill="x", padx=28, pady=(12, 6))
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
        self.status_label.pack(side="left", padx=(8, 0))

        self.sync_button = tk.Button(
            self.root,
            text="⬇  مزامنة من GitHub إلى المحلي",
            command=self.start_sync,
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
        self.sync_button.pack(pady=(10, 10))

        tk.Label(
            self.root,
            text=(
                "⚠ GitHub هو مصدر الحقيقة. المزامنة تستبدل التعديلات المحلية "
                "وتحذف الملفات غير المتتبعة والـignored خارج نسخة GitHub. "
                ".git محفوظ، ولا يتم commit أو push."
            ),
            font=("Segoe UI", 9),
            bg=self.bg,
            fg=self.warning,
            wraplength=760,
            justify="center",
        ).pack(pady=(0, 14))

        tk.Label(
            self.root,
            text="سجل العملية",
            font=("Segoe UI", 10, "bold"),
            bg=self.bg,
            fg=self.muted,
        ).pack(anchor="w", padx=28)

        self.output = scrolledtext.ScrolledText(
            self.root,
            height=13,
            bg="#0b1116",
            fg="#d9e1e6",
            insertbackground="white",
            font=("Consolas", 9),
            relief="flat",
            bd=0,
            wrap="word",
        )
        self.output.pack(fill="both", expand=True, padx=28, pady=(6, 20))

        self._write_output("ORION Sync جاهز — GitHub هو مصدر الحقيقة.")
        self._write_output(f"Project: {PROJECT_ROOT}")
        self._write_output(f"Target: origin/{self.branch}")
        self._write_output("اختر الفرع ثم اضغط «مزامنة من GitHub إلى المحلي».")

    def _info_row(self, parent, label, value):
        row = tk.Frame(parent, bg=self.panel)
        row.pack(fill="x", padx=16, pady=5)
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
        ).pack(side="left", fill="x", expand=True)

    def _write_output(self, text):
        self.output.insert("end", text + "\n")
        self.output.see("end")

    def _set_status(self, text, color):
        self.status_var.set(text)
        self.status_label.configure(fg=color)

    def start_sync(self):
        if self.running:
            return
        if not os.path.isfile(SYNC_SCRIPT):
            self._set_status("ملف المزامنة غير موجود", self.error)
            self._write_output("")
            self._write_output("ERROR: orion_sync.bat not found.")
            self._write_output(SYNC_SCRIPT)
            return

        branch = self.branch
        if not messagebox.askyesno(
            "تأكيد GitHub → Local",
            (
                f"سيتم جعل المشروع المحلي نسخة مطابقة لـ origin/{branch}.\n\n"
                "سيتم حذف التعديلات المتتبعة والملفات غير المتتبعة والـignored.\n"
                ".git سيبقى محفوظًا.\n\n"
                "لن يتم إنشاء commit ولن يتم تنفيذ push.\n\n"
                "هل تريد المتابعة؟"
            ),
            icon="warning",
        ):
            self._write_output("تم إلغاء المزامنة.")
            return

        self.running = True
        self.sync_button.configure(state="disabled", text="⏳  جاري المزامنة...")
        self.branch_combo.configure(state="disabled")
        self._set_status("جاري المزامنة...", self.accent)
        self._write_output("")
        self._write_output("=" * 60)
        self._write_output("ORION GITHUB -> LOCAL SYNC STARTED")
        self._write_output(f"Target: origin/{branch}")
        self._write_output("=" * 60)

        threading.Thread(target=self._run_sync, args=(branch,), daemon=True).start()

    def _run_sync(self, branch):
        try:
            process = subprocess.Popen(
                ["cmd.exe", "/c", SYNC_SCRIPT, branch],
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            for line in process.stdout:
                line = line.rstrip()
                if line:
                    self.root.after(0, self._write_output, line)

            return_code = process.wait()
            self.root.after(0, self._sync_finished, return_code)

        except Exception as exc:
            self.root.after(0, self._sync_failed, str(exc))

    def _sync_finished(self, return_code):
        self._write_output("")
        self._write_output("=" * 60)
        if return_code == 0:
            self._write_output("ORION GITHUB -> LOCAL SYNC COMPLETED SUCCESSFULLY")
            self._set_status("تمت المزامنة من GitHub بنجاح ✅", self.success)
        else:
            self._write_output(f"ORION SYNC FAILED - Exit Code: {return_code}")
            self._set_status("فشلت المزامنة ❌", self.error)
        self._write_output("=" * 60)
        self.running = False
        self.sync_button.configure(state="normal", text="⬇  مزامنة من GitHub إلى المحلي")
        self.branch_combo.configure(state="readonly")

    def _sync_failed(self, message):
        self._write_output("")
        self._write_output("ORION SYNC ERROR")
        self._write_output(message)
        self._set_status("حدث خطأ ❌", self.error)
        self.running = False
        self.sync_button.configure(state="normal", text="⬇  مزامنة من GitHub إلى المحلي")
        self.branch_combo.configure(state="readonly")
        messagebox.showerror("ORION Sync", message)


def main():
    if not os.path.isdir(PROJECT_ROOT):
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("ORION Sync", f"مشروع ORION غير موجود:\n\n{PROJECT_ROOT}")
        root.destroy()
        return

    root = tk.Tk()
    OrionSyncApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
