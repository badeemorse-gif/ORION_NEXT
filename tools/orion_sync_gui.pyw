import os
import subprocess
import threading
import tkinter as tk
from tkinter import scrolledtext


PROJECT_ROOT = r"C:\Users\badee\Desktop\ORION_NEXT"
SYNC_SCRIPT = os.path.join(PROJECT_ROOT, "tools", "orion_sync.bat")


class OrionSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ORION Sync")
        self.root.geometry("720x520")
        self.root.minsize(640, 460)

        self.bg = "#101820"
        self.panel = "#17232d"
        self.fg = "#f2f5f7"
        self.muted = "#9aa8b2"
        self.accent = "#2eaadc"
        self.success = "#3fc36b"
        self.error = "#e05252"

        self.root.configure(bg=self.bg)

        self.status_var = tk.StringVar(value="جاهز للمزامنة")
        self.last_result = None

        self._build_ui()

    def _build_ui(self):
        header = tk.Frame(self.root, bg=self.bg)
        header.pack(fill="x", padx=28, pady=(24, 10))

        title = tk.Label(
            header,
            text="ORION SYNC",
            font=("Segoe UI", 22, "bold"),
            bg=self.bg,
            fg=self.fg,
        )
        title.pack()

        subtitle = tk.Label(
            header,
            text="Local → Git → GitHub",
            font=("Segoe UI", 10),
            bg=self.bg,
            fg=self.muted,
        )
        subtitle.pack(pady=(2, 0))

        info = tk.Frame(self.root, bg=self.panel)
        info.pack(fill="x", padx=28, pady=12)

        self._info_row(info, "Repository", "ORION_NEXT")
        self._info_row(info, "Branch", "main")
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
            text="🔄  مزامنة الآن",
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
        self.sync_button.pack(pady=(10, 18))

        output_label = tk.Label(
            self.root,
            text="سجل العملية",
            font=("Segoe UI", 10, "bold"),
            bg=self.bg,
            fg=self.muted,
        )
        output_label.pack(anchor="w", padx=28)

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
        self.output.pack(fill="both", expand=True, padx=28, pady=(6, 20))

        self._write_output("ORION Sync جاهز.")
        self._write_output(f"Project: {PROJECT_ROOT}")
        self._write_output("اضغط «مزامنة الآن» لبدء العملية.")

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
        if not os.path.isfile(SYNC_SCRIPT):
            self._set_status("ملف المزامنة غير موجود", self.error)
            self._write_output("")
            self._write_output("ERROR: orion_sync.bat not found.")
            self._write_output(SYNC_SCRIPT)
            return

        self.sync_button.configure(
            state="disabled",
            text="⏳  جاري المزامنة..."
        )

        self._set_status("جاري المزامنة...", self.accent)

        self._write_output("")
        self._write_output("=" * 58)
        self._write_output("ORION SYNC STARTED")
        self._write_output("=" * 58)

        thread = threading.Thread(
            target=self._run_sync,
            daemon=True,
        )
        thread.start()

    def _run_sync(self):
        try:
            process = subprocess.Popen(
                ["cmd.exe", "/c", SYNC_SCRIPT],
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            for line in process.stdout:
                line = line.rstrip()
                if line:
                    self.root.after(
                        0,
                        self._write_output,
                        line,
                    )

            return_code = process.wait()

            self.root.after(
                0,
                self._sync_finished,
                return_code,
            )

        except Exception as exc:
            self.root.after(
                0,
                self._sync_failed,
                str(exc),
            )

    def _sync_finished(self, return_code):
        self._write_output("")
        self._write_output("=" * 58)

        if return_code == 0:
            self._write_output("ORION SYNC COMPLETED SUCCESSFULLY")
            self._set_status("تمت المزامنة بنجاح ✅", self.success)
        else:
            self._write_output(
                f"ORION SYNC FAILED - Exit Code: {return_code}"
            )
            self._set_status("فشلت المزامنة ❌", self.error)

        self._write_output("=" * 58)

        self.sync_button.configure(
            state="normal",
            text="🔄  مزامنة الآن"
        )

    def _sync_failed(self, message):
        self._write_output("")
        self._write_output("ORION SYNC ERROR")
        self._write_output(message)

        self._set_status("حدث خطأ ❌", self.error)

        self.sync_button.configure(
            state="normal",
            text="🔄  مزامنة الآن"
        )


def main():
    if not os.path.isdir(PROJECT_ROOT):
        root = tk.Tk()
        root.withdraw()

        from tkinter import messagebox

        messagebox.showerror(
            "ORION Sync",
            f"مشروع ORION غير موجود:\n\n{PROJECT_ROOT}",
        )

        root.destroy()
        return

    root = tk.Tk()
    OrionSyncApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()