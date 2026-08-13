"""ORION Safe Synchronization GUI.

All operations delegate to tools/orion_sync_safe.py. No GUI path may write to
PROJECT_ROOT except DEV mode's normal Git commit/push operation.
"""
from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, scrolledtext

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "tools" / "orion_sync_safe.py"
PROJECT_ROOT = ROOT
MAIN_ROOT = ROOT.parent / "ORION_NEXT_MAIN"
ALL_ROOT = ROOT.parent / "ORION_NEXT_ALL_BRANCHES" / "__branches__"


def execute(mode: str, write):
    process = subprocess.Popen([sys.executable, str(CONTROLLER), mode], cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    for line in process.stdout:
        write(line.rstrip())
    return process.wait()


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("ORION — Safe Synchronization")
        self.root.geometry("900x620")
        self.root.configure(bg="#101820")
        self.running = False
        self.build()

    def build(self):
        tk.Label(self.root, text="ORION SAFE SYNCHRONIZATION", font=("Segoe UI", 20, "bold"), bg="#101820", fg="#f2f5f7").pack(pady=(18, 4))
        tk.Label(self.root, text="Branch isolation is enforced by the controller", font=("Segoe UI", 10), bg="#101820", fg="#9aa8b2").pack()
        panel = tk.Frame(self.root, bg="#17232d")
        panel.pack(fill="x", padx=28, pady=14)
        for label, value in (("Development", PROJECT_ROOT), ("MAIN mirror", MAIN_ROOT), ("ALL mirrors", ALL_ROOT)):
            row = tk.Frame(panel, bg="#17232d")
            row.pack(fill="x", padx=16, pady=5)
            tk.Label(row, text=label + ":", width=16, anchor="w", bg="#17232d", fg="#9aa8b2", font=("Segoe UI", 9, "bold")).pack(side="left")
            tk.Label(row, text=str(value), anchor="w", bg="#17232d", fg="#f2f5f7", font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True)
        buttons = tk.Frame(self.root, bg="#101820")
        buttons.pack(pady=5)
        for label, mode in (("DEV SYNC", "dev"), ("MAIN MIRROR", "main"), ("ALL MIRRORS", "all")):
            tk.Button(buttons, text=label, command=lambda m=mode: self.start(m), bg="#2eaadc", fg="white", activebackground="#2eaadc", relief="flat", font=("Segoe UI", 10, "bold"), padx=22, pady=9).pack(side="left", padx=5)
        tk.Label(self.root, text="DEV → current branch. MAIN → ORION_NEXT_MAIN. ALL → isolated branch snapshots. PROJECT_ROOT is never a mirror destination.", wraplength=820, justify="center", font=("Segoe UI", 9), bg="#101820", fg="#e0a52e").pack(pady=10)
        tk.Label(self.root, text="Operation log", bg="#101820", fg="#9aa8b2", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=28)
        self.output = scrolledtext.ScrolledText(self.root, height=17, bg="#0b1116", fg="#d9e1e6", insertbackground="white", font=("Consolas", 9), relief="flat", bd=0)
        self.output.pack(fill="both", expand=True, padx=28, pady=(5, 18))
        self.write("SAFE SYNC READY")
        self.write("Hard invariant: MAIN/ALL never materialize into PROJECT_ROOT.")

    def write(self, text):
        self.output.insert("end", text + "\n")
        self.output.see("end")

    def start(self, mode):
        if self.running:
            return
        self.running = True
        self.write("=" * 72)
        self.write(f"START {mode.upper()}")
        threading.Thread(target=self.worker, args=(mode,), daemon=True).start()

    def worker(self, mode):
        rc = execute(mode, lambda text: self.root.after(0, self.write, text))
        def finish():
            self.running = False
            if rc == 0:
                messagebox.showinfo("ORION SAFE SYNC", f"{mode.upper()} completed successfully.")
            else:
                messagebox.showerror("ORION SAFE SYNC", f"{mode.upper()} refused/failed. See log.")
        self.root.after(0, finish)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
