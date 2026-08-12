from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT = PROJECT_ROOT / "tools" / "orion_sync.bat"
VERIFY_SCRIPT = PROJECT_ROOT / "tools" / "orion_sync_verify.py"
DEFAULT_BRANCH = "phase2/core-intelligence-hardening"


class OrionSyncApp:
    """Repository-first GitHub -> Local synchronization UI."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ORION Sync")
        self.root.geometry("860x680")
        self.root.minsize(720, 590)

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
        self.status_var = tk.StringVar(value="جاهز")
        self.running = False

        self._build_ui()

    @property
    def branch(self) -> str:
        value = self.branch_var.get().strip()
        return value or DEFAULT_BRANCH

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg=self.bg)
        header.pack(fill="x", padx=28, pady=(22, 10))
        tk.Label(
            header,
            text="ORION SYNC",
            font=("Segoe UI", 22, "bold"),
            bg=self.bg,
            fg=self.fg,
        ).pack()
        tk.Label(
            header,
            text="GitHub → Git → Local | repository-first",
            font=("Segoe UI", 10),
            bg=self.bg,
            fg=self.muted,
        ).pack(pady=(2, 0))

        info = tk.Frame(self.root, bg=self.panel)
        info.pack(fill="x", padx=28, pady=12)
        self._info_row(info, "Repository", "badeemorse-gif/ORION_NEXT")
        self._info_row(info, "Project root", str(PROJECT_ROOT))

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
            values=(DEFAULT_BRANCH,),
            state="normal",
            width=48,
            font=("Segoe UI", 9),
        )
        self.branch_combo.pack(side="left", fill="x", expand=True)
        tk.Button(
            branch_row,
            text="تحديث الفروع",
            command=self.refresh_branches,
            font=("Segoe UI", 9, "bold"),
            bg=self.panel,
            fg=self.fg,
            activebackground=self.panel,
            activeforeground=self.fg,
            relief="groove",
        ).pack(side="left", padx=(8, 0))

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

        actions = tk.Frame(self.root, bg=self.bg)
        actions.pack(pady=(8, 10))
        self.sync_button = tk.Button(
            actions,
            text="⬇  مزامنة GitHub → المحلي",
            command=self.start_sync,
            font=("Segoe UI", 13, "bold"),
            bg=self.accent,
            fg="white",
            activebackground=self.accent,
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=24,
            pady=11,
        )
        self.sync_button.pack(side="left", padx=5)
        self.verify_button = tk.Button(
            actions,
            text="✓  فحص التطابق فقط",
            command=self.start_verify,
            font=("Segoe UI", 11, "bold"),
            bg=self.panel,
            fg=self.fg,
            activebackground=self.panel,
            activeforeground=self.fg,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=20,
            pady=10,
        )
        self.verify_button.pack(side="left", padx=5)

        tk.Label(
            self.root,
            text=(
                "GitHub هو مصدر الحقيقة. المزامنة تستبدل حالة المشروع المحلي بعد إنشاء "
                "نسخة أمان خارج المشروع عند وجود تغييرات. .git محفوظ، ولا يتم commit أو push. "
                "الأداة تحدّث نفسها من فرع GitHub المطلوب قبل تنفيذ المزامنة."
            ),
            font=("Segoe UI", 9),
            bg=self.bg,
            fg=self.warning,
            wraplength=800,
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
            height=14,
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
        self._write_output(f"Project root: {PROJECT_ROOT}")
        self._write_output(f"Default target: origin/{DEFAULT_BRANCH}")
        self._write_output("الأداة لا تفترض مسارًا ثابتًا؛ تحدد جذر المشروع من موقعها داخل tools.")
        self.refresh_branches(log=False)

    def _info_row(self, parent: tk.Widget, label: str, value: str) -> None:
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

    def _write_output(self, text: str) -> None:
        self.output.insert("end", text + "\n")
        self.output.see("end")

    def _set_status(self, text: str, color: str) -> None:
        self.status_var.set(text)
        self.status_label.configure(fg=color)

    def refresh_branches(self, log: bool = True) -> None:
        try:
            result = subprocess.run(
                ["git", "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin"],
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            branches = []
            for line in result.stdout.splitlines():
                name = line.strip()
                if not name or name == "origin/HEAD":
                    continue
                if name.startswith("origin/"):
                    branches.append(name[len("origin/"):])
            values = tuple(dict.fromkeys([DEFAULT_BRANCH, *sorted(branches)]))
            self.branch_combo["values"] = values
            if log:
                self._write_output(f"تم تحديث قائمة الفروع: {len(values)} فرعًا متاحًا محليًا.")
        except Exception as exc:
            if log:
                self._write_output(f"تعذر تحديث قائمة الفروع: {exc}")

    def _set_running(self, running: bool) -> None:
        self.running = running
        state = "disabled" if running else "normal"
        self.sync_button.configure(state=state)
        self.verify_button.configure(state=state)
        self.branch_combo.configure(state=state)

    def start_sync(self) -> None:
        if self.running:
            return
        if not SYNC_SCRIPT.is_file():
            self._set_status("ملف المزامنة غير موجود", self.error)
            self._write_output(f"ERROR: {SYNC_SCRIPT}")
            return

        branch = self.branch
        if not messagebox.askyesno(
            "تأكيد GitHub → Local",
            (
                f"سيتم جعل المشروع المحلي نسخة مطابقة لـ origin/{branch}.\n\n"
                "إذا كانت هناك تغييرات محلية، ستُحفظ نسخة أمان خارج المشروع أولًا.\n"
                "بعدها سيُعاد ضبط المشروع إلى GitHub، بما في ذلك الملفات غير المتتبعة والـignored.\n\n"
                ".git سيبقى محفوظًا، ولن يتم commit أو push.\n\n"
                "هل تريد المتابعة؟"
            ),
            icon="warning",
        ):
            self._write_output("تم إلغاء المزامنة — لم يحدث أي تغيير.")
            return

        self._start_process("sync", branch)

    def start_verify(self) -> None:
        if self.running:
            return
        if not VERIFY_SCRIPT.is_file():
            self._set_status("أداة التحقق غير موجودة", self.error)
            self._write_output(f"ERROR: {VERIFY_SCRIPT}")
            return
        self._start_process("verify", self.branch)

    def _start_process(self, mode: str, branch: str) -> None:
        self._set_running(True)
        self._set_status("جاري التنفيذ...", self.accent)
        self._write_output("")
        self._write_output("=" * 64)
        self._write_output(f"ORION {mode.upper()} — origin/{branch}")
        self._write_output(f"Root: {PROJECT_ROOT}")
        self._write_output("=" * 64)
        threading.Thread(target=self._run_process, args=(mode, branch), daemon=True).start()

    def _run_process(self, mode: str, branch: str) -> None:
        try:
            if mode == "sync":
                command = ["cmd.exe", "/c", str(SYNC_SCRIPT), branch]
            else:
                command = ["python", str(VERIFY_SCRIPT), "--branch", branch]

            process = subprocess.Popen(
                command,
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            assert process.stdout is not None
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    self.root.after(0, self._write_output, line)
            return_code = process.wait()
            self.root.after(0, self._process_finished, mode, return_code)
        except Exception as exc:
            self.root.after(0, self._process_failed, str(exc))

    def _process_finished(self, mode: str, return_code: int) -> None:
        self._write_output("")
        self._write_output("=" * 64)
        if return_code == 0:
            self._write_output(f"ORION {mode.upper()} COMPLETED SUCCESSFULLY")
            self._set_status("نجاح ✅", self.success)
        else:
            self._write_output(f"ORION {mode.upper()} FAILED — Exit Code: {return_code}")
            self._set_status("فشل ❌", self.error)
        self._write_output("=" * 64)
        self._set_running(False)

    def _process_failed(self, message: str) -> None:
        self._write_output("")
        self._write_output("ORION TOOL ERROR")
        self._write_output(message)
        self._set_status("حدث خطأ ❌", self.error)
        self._set_running(False)
        messagebox.showerror("ORION Sync", message)


def main() -> None:
    if not PROJECT_ROOT.is_dir():
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("ORION Sync", f"ORION project root not found:\n\n{PROJECT_ROOT}")
        root.destroy()
        return

    root = tk.Tk()
    OrionSyncApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
