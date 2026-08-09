"""
ORION CLEAN
===========

Safe cleanup utility for the ORION_NEXT project.

This application removes ONLY:
    - __pycache__ directories
    - *.pyc files
    - *.pyo files

It NEVER:
    - modifies source code
    - modifies project data
    - modifies documentation
    - modifies configuration
    - executes Git
    - performs commit/push
    - deletes arbitrary files
    - works outside the ORION_NEXT project root
"""

from __future__ import annotations

import os
import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox


# ============================================================
# PROJECT CONFIGURATION
# ============================================================

APP_TITLE = "ORION CLEAN"

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SAFE_CACHE_DIRECTORY = "__pycache__"

SAFE_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
}

MAX_SINGLE_FILE_SIZE = 50 * 1024 * 1024
MAX_CLEANUP_TARGETS = 100000


# ============================================================
# DARK UI THEME
# ============================================================

BG = "#111827"
BG_DARK = "#0B1220"
PANEL = "#182235"
PANEL_2 = "#202D42"

BORDER = "#2E3D55"

TEXT = "#F3F4F6"
TEXT_SECONDARY = "#9CA3AF"
TEXT_MUTED = "#6B7280"

ACCENT = "#38BDF8"
ACCENT_HOVER = "#67E8F9"

SUCCESS = "#34D399"
WARNING = "#FBBF24"
DANGER = "#F87171"

BUTTON_TEXT = "#07111F"


# ============================================================
# SAFETY FUNCTIONS
# ============================================================

def is_inside_project(path: Path) -> bool:
    """
    Returns True only when the path is inside ORION_NEXT.
    """
    try:
        path.resolve().relative_to(PROJECT_ROOT.resolve())
        return True
    except ValueError:
        return False


def is_safe_cache_directory(path: Path) -> bool:
    """
    Only __pycache__ directories inside ORION_NEXT are allowed.
    """
    if not path.is_dir():
        return False

    if path.name != SAFE_CACHE_DIRECTORY:
        return False

    if not is_inside_project(path):
        return False

    if path.resolve() == PROJECT_ROOT.resolve():
        return False

    return True


def is_safe_bytecode_file(path: Path) -> bool:
    """
    Only .pyc and .pyo files inside ORION_NEXT are allowed.
    """
    if not path.is_file():
        return False

    if not is_inside_project(path):
        return False

    if path.suffix.lower() not in SAFE_FILE_SUFFIXES:
        return False

    try:
        if path.stat().st_size > MAX_SINGLE_FILE_SIZE:
            return False
    except OSError:
        return False

    return True


# ============================================================
# SCAN
# ============================================================

def scan_project():
    """
    Scan the project without deleting anything.
    """

    cache_dirs = []
    bytecode_files = []
    total_bytes = 0

    if not PROJECT_ROOT.exists():
        raise RuntimeError(
            f"Project directory was not found:\n{PROJECT_ROOT}"
        )

    if not PROJECT_ROOT.is_dir():
        raise RuntimeError(
            f"Project root is not a directory:\n{PROJECT_ROOT}"
        )

    if PROJECT_ROOT.name.lower() != "orion_next":
        raise RuntimeError(
            "Safety check failed.\n"
            "The detected project directory is not ORION_NEXT."
        )

    for root, dirs, files in os.walk(
        PROJECT_ROOT,
        topdown=True,
        followlinks=False,
    ):
        root_path = Path(root)

        # Never follow symbolic-link directories.
        dirs[:] = [
            name
            for name in dirs
            if not (root_path / name).is_symlink()
        ]

        # Detect __pycache__.
        for directory_name in list(dirs):
            candidate = root_path / directory_name

            if is_safe_cache_directory(candidate):
                cache_dirs.append(candidate)

                # Do not descend into a cache directory.
                dirs.remove(directory_name)

        # Detect .pyc / .pyo files.
        for filename in files:
            candidate = root_path / filename

            if not is_safe_bytecode_file(candidate):
                continue

            bytecode_files.append(candidate)

            try:
                total_bytes += candidate.stat().st_size
            except OSError:
                pass

            if (
                len(cache_dirs) + len(bytecode_files)
                > MAX_CLEANUP_TARGETS
            ):
                raise RuntimeError(
                    "The number of cleanup targets is unexpectedly high."
                )

    return {
        "cache_dirs": cache_dirs,
        "bytecode_files": bytecode_files,
        "total": len(cache_dirs) + len(bytecode_files),
        "bytes": total_bytes,
    }


# ============================================================
# DELETE
# ============================================================

def delete_targets(scan_result, log_callback):
    """
    Delete ONLY targets produced by scan_project().
    """

    deleted_dirs = 0
    deleted_files = 0
    failed = []

    # --------------------------------------------------------
    # __pycache__
    # --------------------------------------------------------

    for directory in scan_result["cache_dirs"]:
        try:
            if not is_safe_cache_directory(directory):
                failed.append(
                    (directory, "Safety validation failed")
                )
                continue

            shutil.rmtree(directory)

            deleted_dirs += 1

            log_callback(
                f"REMOVED  {directory}"
            )

        except Exception as exc:
            failed.append(
                (directory, str(exc))
            )

            log_callback(
                f"FAILED   {directory} -> {exc}"
            )

    # --------------------------------------------------------
    # .pyc / .pyo
    # --------------------------------------------------------

    for file_path in scan_result["bytecode_files"]:
        try:
            if not is_safe_bytecode_file(file_path):
                failed.append(
                    (file_path, "Safety validation failed")
                )
                continue

            # Parent __pycache__ may already have been removed.
            if not file_path.exists():
                continue

            file_path.unlink()

            deleted_files += 1

            log_callback(
                f"REMOVED  {file_path}"
            )

        except Exception as exc:
            failed.append(
                (file_path, str(exc))
            )

            log_callback(
                f"FAILED   {file_path} -> {exc}"
            )

    return {
        "deleted_dirs": deleted_dirs,
        "deleted_files": deleted_files,
        "failed": failed,
    }


# ============================================================
# FORMATTING
# ============================================================

def format_size(size: int) -> str:
    units = (
        "B",
        "KB",
        "MB",
        "GB",
    )

    value = float(size)

    for unit in units:
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{size} B"


# ============================================================
# GUI
# ============================================================

class OrionCleanApp:

    def __init__(self, root: tk.Tk):

        self.root = root

        self.running = False

        # ----------------------------------------------------
        # Window
        # ----------------------------------------------------

        self.root.title(APP_TITLE)

        self.root.geometry("900x650")

        self.root.minsize(
            820,
            580,
        )

        self.root.configure(
            bg=BG_DARK
        )

        # ----------------------------------------------------
        # Fonts
        # ----------------------------------------------------

        self.FONT_TITLE = (
            "Segoe UI",
            22,
            "bold",
        )

        self.FONT_SUBTITLE = (
            "Segoe UI",
            10,
        )

        self.FONT_LABEL = (
            "Segoe UI",
            9,
            "bold",
        )

        self.FONT_NORMAL = (
            "Segoe UI",
            9,
        )

        self.FONT_MONO = (
            "Consolas",
            9,
        )

        # ----------------------------------------------------
        # Variables
        # ----------------------------------------------------

        self.status_var = tk.StringVar(
            value="READY"
        )

        self.target_var = tk.StringVar(
            value="0"
        )

        self.removed_var = tk.StringVar(
            value="0"
        )

        self.size_var = tk.StringVar(
            value="0 B"
        )

        # ----------------------------------------------------
        # Build
        # ----------------------------------------------------

        self.build_ui()

    # ========================================================
    # UI
    # ========================================================

    def build_ui(self):

        # Main background.
        outer = tk.Frame(
            self.root,
            bg=BG_DARK,
        )

        outer.pack(
            fill="both",
            expand=True,
        )

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        header = tk.Frame(
            outer,
            bg=BG,
            height=92,
        )

        header.pack(
            fill="x",
        )

        header.pack_propagate(
            False
        )

        # Logo block.
        logo = tk.Frame(
            header,
            bg=ACCENT,
            width=54,
            height=54,
        )

        logo.pack(
            side="left",
            padx=(24, 14),
            pady=18,
        )

        logo.pack_propagate(
            False
        )

        logo_text = tk.Label(
            logo,
            text="OC",
            bg=ACCENT,
            fg=BUTTON_TEXT,
            font=(
                "Segoe UI",
                13,
                "bold",
            ),
        )

        logo_text.pack(
            expand=True
        )

        # Title.
        title_area = tk.Frame(
            header,
            bg=BG,
        )

        title_area.pack(
            side="left",
            fill="y",
            pady=15,
        )

        title = tk.Label(
            title_area,
            text="ORION CLEAN",
            bg=BG,
            fg=TEXT,
            font=self.FONT_TITLE,
        )

        title.pack(
            anchor="w"
        )

        subtitle = tk.Label(
            title_area,
            text="Safe project maintenance utility",
            bg=BG,
            fg=TEXT_SECONDARY,
            font=self.FONT_SUBTITLE,
        )

        subtitle.pack(
            anchor="w"
        )

        # ----------------------------------------------------
        # Main content
        # ----------------------------------------------------

        content = tk.Frame(
            outer,
            bg=BG_DARK,
        )

        content.pack(
            fill="both",
            expand=True,
            padx=22,
            pady=18,
        )

        # ----------------------------------------------------
        # Project panel
        # ----------------------------------------------------

        project_panel = tk.Frame(
            content,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

        project_panel.pack(
            fill="x",
            pady=(0, 14),
        )

        project_title = tk.Label(
            project_panel,
            text="PROJECT",
            bg=PANEL,
            fg=ACCENT,
            font=self.FONT_LABEL,
        )

        project_title.pack(
            anchor="w",
            padx=16,
            pady=(12, 3),
        )

        project_path = tk.Label(
            project_panel,
            text=str(PROJECT_ROOT),
            bg=PANEL,
            fg=TEXT,
            font=self.FONT_MONO,
            anchor="w",
        )

        project_path.pack(
            fill="x",
            padx=16,
            pady=(0, 13),
        )

        # ----------------------------------------------------
        # Statistics
        # ----------------------------------------------------

        stats = tk.Frame(
            content,
            bg=BG_DARK,
        )

        stats.pack(
            fill="x",
            pady=(0, 14),
        )

        self.create_stat_card(
            stats,
            "TARGETS",
            self.target_var,
            ACCENT,
        )

        self.create_stat_card(
            stats,
            "REMOVED",
            self.removed_var,
            SUCCESS,
        )

        self.create_stat_card(
            stats,
            "SIZE",
            self.size_var,
            WARNING,
        )

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        status_panel = tk.Frame(
            content,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

        status_panel.pack(
            fill="x",
            pady=(0, 14),
        )

        status_caption = tk.Label(
            status_panel,
            text="STATUS",
            bg=PANEL,
            fg=TEXT_MUTED,
            font=self.FONT_LABEL,
        )

        status_caption.pack(
            side="left",
            padx=(16, 8),
            pady=13,
        )

        self.status_label = tk.Label(
            status_panel,
            textvariable=self.status_var,
            bg=PANEL,
            fg=SUCCESS,
            font=(
                "Segoe UI",
                9,
                "bold",
            ),
        )

        self.status_label.pack(
            side="left",
            pady=13,
        )

        # ----------------------------------------------------
        # Clean button
        # ----------------------------------------------------

        self.clean_button = tk.Button(
            content,
            text="CLEAN PROJECT",
            command=self.start_cleanup,
            bg=ACCENT,
            fg=BUTTON_TEXT,
            activebackground=ACCENT_HOVER,
            activeforeground=BUTTON_TEXT,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            font=(
                "Segoe UI",
                11,
                "bold",
            ),
        )

        self.clean_button.pack(
            fill="x",
            ipady=13,
            pady=(0, 14),
        )

        self.clean_button.bind(
            "<Enter>",
            self.button_enter,
        )

        self.clean_button.bind(
            "<Leave>",
            self.button_leave,
        )

        # ----------------------------------------------------
        # Protection
        # ----------------------------------------------------

        protection = tk.Frame(
            content,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

        protection.pack(
            fill="x",
            pady=(0, 14),
        )

        protection_icon = tk.Label(
            protection,
            text="SAFE",
            bg=PANEL_2,
            fg=SUCCESS,
            font=(
                "Segoe UI",
                8,
                "bold",
            ),
            padx=10,
            pady=6,
        )

        protection_icon.pack(
            side="left",
            padx=12,
            pady=10,
        )

        protection_text = tk.Label(
            protection,
            text=(
                "Only Python-generated cache files are removed. "
                "Source code and project data are protected."
            ),
            bg=PANEL,
            fg=TEXT_SECONDARY,
            font=self.FONT_NORMAL,
            anchor="w",
        )

        protection_text.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 12),
        )

        # ----------------------------------------------------
        # Output panel
        # ----------------------------------------------------

        output_panel = tk.Frame(
            content,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

        output_panel.pack(
            fill="both",
            expand=True,
        )

        output_header = tk.Frame(
            output_panel,
            bg=PANEL,
            height=34,
        )

        output_header.pack(
            fill="x",
        )

        output_header.pack_propagate(
            False
        )

        output_title = tk.Label(
            output_header,
            text="ACTIVITY",
            bg=PANEL,
            fg=ACCENT,
            font=self.FONT_LABEL,
        )

        output_title.pack(
            side="left",
            padx=14,
        )

        # Text + scrollbar.
        text_container = tk.Frame(
            output_panel,
            bg=BG,
        )

        text_container.pack(
            fill="both",
            expand=True,
            padx=1,
            pady=1,
        )

        self.output = tk.Text(
            text_container,
            bg=BG,
            fg=TEXT_SECONDARY,
            insertbackground=ACCENT,
            selectbackground=ACCENT,
            selectforeground=BUTTON_TEXT,
            relief="flat",
            borderwidth=0,
            wrap="none",
            font=self.FONT_MONO,
            padx=12,
            pady=10,
            state="disabled",
        )

        scrollbar = tk.Scrollbar(
            text_container,
            orient="vertical",
            command=self.output.yview,
            bg=PANEL_2,
            troughcolor=BG,
            activebackground=ACCENT,
            relief="flat",
            borderwidth=0,
        )

        self.output.configure(
            yscrollcommand=scrollbar.set
        )

        self.output.pack(
            side="left",
            fill="both",
            expand=True,
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )

        # Initial log.
        self.log("ORION CLEAN initialized.")
        self.log(f"Project: {PROJECT_ROOT}")
        self.log("")
        self.log("SAFE TARGETS")
        self.log("  __pycache__")
        self.log("  *.pyc")
        self.log("  *.pyo")
        self.log("")
        self.log("Git commands: DISABLED")
        self.log("Source/data modification: DISABLED")
        self.log("")
        self.log("Ready.")

    # ========================================================
    # Stat cards
    # ========================================================

    def create_stat_card(
        self,
        parent,
        title,
        variable,
        accent,
    ):

        card = tk.Frame(
            parent,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

        card.pack(
            side="left",
            fill="x",
            expand=True,
            padx=5,
        )

        label = tk.Label(
            card,
            text=title,
            bg=PANEL,
            fg=TEXT_MUTED,
            font=self.FONT_LABEL,
        )

        label.pack(
            anchor="w",
            padx=14,
            pady=(10, 0),
        )

        value = tk.Label(
            card,
            textvariable=variable,
            bg=PANEL,
            fg=accent,
            font=(
                "Segoe UI",
                17,
                "bold",
            ),
        )

        value.pack(
            anchor="w",
            padx=14,
            pady=(0, 10),
        )

    # ========================================================
    # Button effects
    # ========================================================

    def button_enter(self, _event):

        if not self.running:
            self.clean_button.configure(
                bg=ACCENT_HOVER
            )

    def button_leave(self, _event):

        if not self.running:
            self.clean_button.configure(
                bg=ACCENT
            )

    # ========================================================
    # Logging
    # ========================================================

    def log(self, message: str):

        self.root.after(
            0,
            self._append_log,
            message,
        )

    def _append_log(self, message: str):

        self.output.configure(
            state="normal"
        )

        self.output.insert(
            "end",
            message + "\n",
        )

        self.output.see(
            "end"
        )

        self.output.configure(
            state="disabled"
        )

    # ========================================================
    # Status
    # ========================================================

    def set_status(
        self,
        value: str,
        color=SUCCESS,
    ):

        def update():

            self.status_var.set(
                value
            )

            self.status_label.configure(
                fg=color
            )

        self.root.after(
            0,
            update,
        )

    # ========================================================
    # Cleanup
    # ========================================================

    def start_cleanup(self):

        if self.running:
            return

        # ----------------------------------------------------
        # Final project identity check.
        # ----------------------------------------------------

        if PROJECT_ROOT.name.lower() != "orion_next":

            messagebox.showerror(
                APP_TITLE,
                "Safety check failed.\n\n"
                "The detected project folder is not ORION_NEXT.\n\n"
                "Cleanup cancelled.",
            )

            return

        if not PROJECT_ROOT.exists():

            messagebox.showerror(
                APP_TITLE,
                "Project directory does not exist:\n\n"
                + str(PROJECT_ROOT),
            )

            return

        # ----------------------------------------------------
        # Start
        # ----------------------------------------------------

        self.running = True

        self.clean_button.configure(
            state="disabled",
            bg=PANEL_2,
            fg=TEXT_MUTED,
            cursor="arrow",
        )

        self.set_status(
            "SCANNING...",
            ACCENT,
        )

        self.target_var.set(
            "..."
        )

        self.removed_var.set(
            "0"
        )

        self.size_var.set(
            "..."
        )

        self.log("")
        self.log("=" * 70)
        self.log("STARTING SAFE CLEANUP")
        self.log("=" * 70)

        worker = threading.Thread(
            target=self.cleanup_worker,
            daemon=True,
        )

        worker.start()

    # ========================================================
    # Worker
    # ========================================================

    def cleanup_worker(self):

        try:

            self.log("Scanning project...")
            self.set_status(
                "SCANNING...",
                ACCENT,
            )

            result = scan_project()

            cache_count = len(
                result["cache_dirs"]
            )

            bytecode_count = len(
                result["bytecode_files"]
            )

            self.root.after(
                0,
                self.target_var.set,
                str(result["total"]),
            )

            self.root.after(
                0,
                self.size_var.set,
                format_size(
                    result["bytes"]
                ),
            )

            self.log("")
            self.log(
                f"__pycache__ directories : {cache_count}"
            )

            self.log(
                f"Bytecode files          : {bytecode_count}"
            )

            self.log(
                f"Total eligible targets  : {result['total']}"
            )

            self.log(
                f"Total eligible size     : "
                f"{format_size(result['bytes'])}"
            )

            if result["total"] == 0:

                self.log("")
                self.log(
                    "Nothing to clean."
                )

                self.root.after(
                    0,
                    self.removed_var.set,
                    "0",
                )

                self.set_status(
                    "CLEAN - NOTHING FOUND",
                    SUCCESS,
                )

                self.root.after(
                    0,
                    self.cleanup_finished,
                    0,
                    0,
                    [],
                )

                return

            self.log("")
            self.log(
                "Removing approved cleanup targets..."
            )

            self.set_status(
                "CLEANING...",
                ACCENT,
            )

            deleted = delete_targets(
                result,
                self.log,
            )

            total_removed = (
                deleted["deleted_dirs"]
                + deleted["deleted_files"]
            )

            self.root.after(
                0,
                self.removed_var.set,
                str(total_removed),
            )

            self.root.after(
                0,
                self.size_var.set,
                "DONE",
            )

            self.root.after(
                0,
                self.cleanup_finished,
                deleted["deleted_dirs"],
                deleted["deleted_files"],
                deleted["failed"],
            )

        except Exception as exc:

            self.log("")
            self.log(
                f"ERROR: {exc}"
            )

            self.root.after(
                0,
                self.cleanup_error,
                str(exc),
            )

    # ========================================================
    # Finished
    # ========================================================

    def cleanup_finished(
        self,
        deleted_dirs,
        deleted_files,
        failed,
    ):

        self.running = False

        self.clean_button.configure(
            state="normal",
            bg=ACCENT,
            fg=BUTTON_TEXT,
            cursor="hand2",
        )

        total_removed = (
            deleted_dirs
            + deleted_files
        )

        if failed:

            self.set_status(
                "COMPLETED WITH WARNINGS",
                WARNING,
            )

            self.log("")
            self.log("=" * 70)
            self.log(
                "CLEANUP COMPLETED WITH WARNINGS"
            )
            self.log("=" * 70)

            self.log(
                f"Directories removed : {deleted_dirs}"
            )

            self.log(
                f"Files removed       : {deleted_files}"
            )

            self.log(
                f"Failed targets      : {len(failed)}"
            )

            messagebox.showwarning(
                APP_TITLE,
                "Cleanup completed with warnings.\n\n"
                f"Directories removed: {deleted_dirs}\n"
                f"Files removed: {deleted_files}\n"
                f"Failed: {len(failed)}",
            )

            return

        self.set_status(
            "CLEAN COMPLETED SUCCESSFULLY",
            SUCCESS,
        )

        self.log("")
        self.log("=" * 70)
        self.log(
            "CLEANUP COMPLETED SUCCESSFULLY"
        )
        self.log("=" * 70)

        self.log(
            f"Directories removed : {deleted_dirs}"
        )

        self.log(
            f"Files removed       : {deleted_files}"
        )

        self.log("")
        self.log(
            "Source code         : PROTECTED"
        )

        self.log(
            "Project data        : PROTECTED"
        )

        self.log(
            "Git commands        : NOT EXECUTED"
        )

        self.log("=" * 70)

        messagebox.showinfo(
            APP_TITLE,
            "ORION CLEAN completed successfully.\n\n"
            f"Directories removed: {deleted_dirs}\n"
            f"Files removed: {deleted_files}\n\n"
            "Source code and project data were not targeted.",
        )

    # ========================================================
    # Error
    # ========================================================

    def cleanup_error(
        self,
        error_message,
    ):

        self.running = False

        self.clean_button.configure(
            state="normal",
            bg=ACCENT,
            fg=BUTTON_TEXT,
            cursor="hand2",
        )

        self.set_status(
            "STOPPED - ERROR",
            DANGER,
        )

        messagebox.showerror(
            APP_TITLE,
            "Cleanup was stopped safely.\n\n"
            + error_message,
        )


# ============================================================
# MAIN
# ============================================================

def main():

    root = tk.Tk()

    try:
        root.tk.call(
            "tk",
            "scaling",
            1.0,
        )
    except Exception:
        pass

    OrionCleanApp(
        root
    )

    root.mainloop()


if __name__ == "__main__":
    main()