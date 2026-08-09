"""
ORION CLEAN
============

Safe cleanup utility for the ORION_NEXT project.

Purpose:
    Remove only Python-generated cache/bytecode artifacts.

Allowed removals:
    - __pycache__ directories
    - *.pyc files
    - *.pyo files

Never touches:
    - Python source files (*.py)
    - project data
    - documentation
    - configuration files
    - Git files
    - executables
    - databases
    - spreadsheets
    - ORION project-management documents
    - any file outside the configured project root

Important:
    This program DOES NOT execute Git commands.
    It DOES NOT perform add / commit / push.
"""

from __future__ import annotations

import os
import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


# ============================================================
# Configuration
# ============================================================

APP_TITLE = "ORION CLEAN"

# The project root is the directory one level above "tools".
# This makes the program portable inside the ORION_NEXT repository.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Only these standalone file extensions are eligible for deletion.
SAFE_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
}

# Only this directory name is eligible for recursive directory deletion.
SAFE_CACHE_DIRECTORY = "__pycache__"

# Safety limits.
MAX_SINGLE_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_FILES_TO_DELETE = 100000


# ============================================================
# Utility functions
# ============================================================

def is_inside_project(path: Path) -> bool:
    """
    Return True only if path is located inside PROJECT_ROOT.
    """
    try:
        path.resolve().relative_to(PROJECT_ROOT.resolve())
        return True
    except ValueError:
        return False


def is_safe_bytecode_file(path: Path) -> bool:
    """
    Check whether a file is explicitly allowed to be removed.
    """
    if not path.is_file():
        return False

    if not is_inside_project(path):
        return False

    if path.name in {".", ".."}:
        return False

    if path.suffix.lower() not in SAFE_FILE_SUFFIXES:
        return False

    try:
        if path.stat().st_size > MAX_SINGLE_FILE_SIZE:
            return False
    except OSError:
        return False

    return True


def is_safe_cache_directory(path: Path) -> bool:
    """
    Check whether a directory is an explicitly allowed Python cache
    directory.
    """
    if not path.is_dir():
        return False

    if path.name != SAFE_CACHE_DIRECTORY:
        return False

    if not is_inside_project(path):
        return False

    # Never allow deleting the project root itself.
    if path.resolve() == PROJECT_ROOT.resolve():
        return False

    return True


# ============================================================
# Scanner
# ============================================================

def scan_project():
    """
    Scan the project and return only explicitly allowed cleanup targets.

    Returns:
        {
            "cache_dirs": [Path, ...],
            "bytecode_files": [Path, ...],
            "total": int,
            "bytes": int,
        }
    """

    cache_dirs = []
    bytecode_files = []
    total_bytes = 0

    if not PROJECT_ROOT.exists() or not PROJECT_ROOT.is_dir():
        raise RuntimeError(
            f"Project directory was not found:\n{PROJECT_ROOT}"
        )

    # os.walk is used instead of deleting while scanning.
    # This keeps scanning and deletion completely separate.
    for root, dirs, files in os.walk(
        PROJECT_ROOT,
        topdown=True,
        followlinks=False,
    ):
        root_path = Path(root)

        # Remove unsafe/special traversal entries from consideration.
        # We do not follow symbolic links.
        dirs[:] = [
            d for d in dirs
            if not (root_path / d).is_symlink()
        ]

        # Detect __pycache__ directories.
        for directory_name in list(dirs):
            candidate = root_path / directory_name

            if is_safe_cache_directory(candidate):
                cache_dirs.append(candidate)

                # Do not descend into __pycache__ after identifying it.
                dirs.remove(directory_name)

        # Detect standalone .pyc / .pyo files.
        for filename in files:
            candidate = root_path / filename

            if not is_safe_bytecode_file(candidate):
                continue

            bytecode_files.append(candidate)

            try:
                total_bytes += candidate.stat().st_size
            except OSError:
                pass

            if len(cache_dirs) + len(bytecode_files) > MAX_FILES_TO_DELETE:
                raise RuntimeError(
                    "The number of cleanup targets is unexpectedly large. "
                    "Cleanup was stopped for safety."
                )

    return {
        "cache_dirs": cache_dirs,
        "bytecode_files": bytecode_files,
        "total": len(cache_dirs) + len(bytecode_files),
        "bytes": total_bytes,
    }


# ============================================================
# Safe deletion
# ============================================================

def delete_targets(scan_result, log_callback):
    """
    Delete only targets previously identified by scan_project().
    """

    deleted_dirs = 0
    deleted_files = 0
    failed = []

    # Delete __pycache__ directories.
    for directory in scan_result["cache_dirs"]:
        try:
            # Final safety check immediately before deletion.
            if not is_safe_cache_directory(directory):
                failed.append((directory, "Safety check failed"))
                continue

            shutil.rmtree(directory)

            deleted_dirs += 1
            log_callback(f"Removed: {directory}")

        except Exception as exc:
            failed.append((directory, str(exc)))
            log_callback(f"FAILED: {directory} -> {exc}")

    # Delete standalone .pyc / .pyo files.
    #
    # These are normally inside __pycache__, but we handle them
    # separately in case old/generated files exist elsewhere.
    for file_path in scan_result["bytecode_files"]:
        try:
            if not is_safe_bytecode_file(file_path):
                failed.append((file_path, "Safety check failed"))
                continue

            # The file may already have disappeared because its
            # containing __pycache__ directory was removed.
            if not file_path.exists():
                continue

            file_path.unlink()

            deleted_files += 1
            log_callback(f"Removed: {file_path}")

        except Exception as exc:
            failed.append((file_path, str(exc)))
            log_callback(f"FAILED: {file_path} -> {exc}")

    return {
        "deleted_dirs": deleted_dirs,
        "deleted_files": deleted_files,
        "failed": failed,
    }


# ============================================================
# Formatting
# ============================================================

def format_size(size: int) -> str:
    """
    Convert byte count to a human-readable value.
    """
    units = ["B", "KB", "MB", "GB"]

    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{size} B"


# ============================================================
# GUI
# ============================================================

class OrionCleanApp:
    def __init__(self, root: tk.Tk):
        self.root = root

        self.root.title(APP_TITLE)
        self.root.geometry("760x560")
        self.root.minsize(680, 500)

        self.running = False

        self.status_var = tk.StringVar(value="Ready")
        self.found_var = tk.StringVar(value="Found: 0")
        self.removed_var = tk.StringVar(value="Removed: 0")
        self.protected_var = tk.StringVar(
            value="Protection: Source and data files are untouched"
        )

        self._build_ui()

    # --------------------------------------------------------
    # UI construction
    # --------------------------------------------------------

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=18)
        main.pack(fill="both", expand=True)

        # Header
        header = ttk.Frame(main)
        header.pack(fill="x")

        title = ttk.Label(
            header,
            text="ORION CLEAN",
            font=("Segoe UI", 20, "bold"),
        )
        title.pack(anchor="w")

        subtitle = ttk.Label(
            header,
            text="Safe cleanup of Python-generated cache files",
            font=("Segoe UI", 10),
        )
        subtitle.pack(anchor="w", pady=(3, 12))

        # Project path
        project_frame = ttk.LabelFrame(
            main,
            text="Project",
            padding=10,
        )
        project_frame.pack(fill="x", pady=(0, 12))

        project_label = ttk.Label(
            project_frame,
            text=str(PROJECT_ROOT),
            font=("Consolas", 9),
        )
        project_label.pack(anchor="w")

        # Status
        status_frame = ttk.Frame(main)
        status_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(
            status_frame,
            text="Status:",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
        )
        self.status_label.pack(side="left", padx=(8, 0))

        # Main button
        self.clean_button = ttk.Button(
            main,
            text="🧹  CLEAN PROJECT",
            command=self.start_cleanup,
        )
        self.clean_button.pack(
            fill="x",
            ipady=10,
            pady=(4, 14),
        )

        # Statistics
        stats = ttk.Frame(main)
        stats.pack(fill="x", pady=(0, 12))

        ttk.Label(
            stats,
            textvariable=self.found_var,
        ).pack(side="left", padx=(0, 20))

        ttk.Label(
            stats,
            textvariable=self.removed_var,
        ).pack(side="left")

        # Protection message
        protection = ttk.Label(
            main,
            textvariable=self.protected_var,
            font=("Segoe UI", 9, "bold"),
        )
        protection.pack(anchor="w", pady=(0, 8))

        # Output
        output_frame = ttk.LabelFrame(
            main,
            text="Output",
            padding=8,
        )
        output_frame.pack(
            fill="both",
            expand=True,
        )

        self.output = tk.Text(
            output_frame,
            wrap="none",
            font=("Consolas", 9),
            state="disabled",
        )

        scrollbar_y = ttk.Scrollbar(
            output_frame,
            orient="vertical",
            command=self.output.yview,
        )

        scrollbar_x = ttk.Scrollbar(
            output_frame,
            orient="horizontal",
            command=self.output.xview,
        )

        self.output.configure(
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
        )

        self.output.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        scrollbar_y.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        scrollbar_x.grid(
            row=1,
            column=0,
            sticky="ew",
        )

        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)

        self.log("ORION CLEAN ready.")
        self.log(f"Project: {PROJECT_ROOT}")
        self.log("")
        self.log("Safe targets:")
        self.log("  - __pycache__ directories")
        self.log("  - *.pyc files")
        self.log("  - *.pyo files")
        self.log("")
        self.log("No Git commands are executed.")
        self.log("Source and project data are protected.")

    # --------------------------------------------------------
    # Logging
    # --------------------------------------------------------

    def log(self, message: str):
        """
        Thread-safe logging to the GUI.
        """
        self.root.after(
            0,
            self._append_log,
            message,
        )

    def _append_log(self, message: str):
        self.output.configure(state="normal")
        self.output.insert("end", message + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    def set_status(self, value: str):
        self.root.after(
            0,
            self.status_var.set,
            value,
        )

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

    def start_cleanup(self):
        if self.running:
            return

        # Confirm that the configured project directory is really
        # the ORION_NEXT project root.
        if PROJECT_ROOT.name.lower() != "orion_next":
            messagebox.showerror(
                APP_TITLE,
                "Safety check failed.\n\n"
                "The detected project folder is not named ORION_NEXT.\n"
                "Cleanup was cancelled.",
            )
            return

        if not PROJECT_ROOT.exists():
            messagebox.showerror(
                APP_TITLE,
                f"Project directory does not exist:\n\n{PROJECT_ROOT}",
            )
            return

        self.running = True
        self.clean_button.configure(state="disabled")

        self.status_var.set("Cleaning...")

        self.found_var.set("Found: scanning...")
        self.removed_var.set("Removed: 0")

        self.log("")
        self.log("=" * 60)
        self.log("Starting safe cleanup...")
        self.log("=" * 60)

        worker = threading.Thread(
            target=self._cleanup_worker,
            daemon=True,
        )

        worker.start()

    def _cleanup_worker(self):
        try:
            self.log("Scanning project...")
            self.set_status("Scanning...")

            result = scan_project()

            cache_count = len(result["cache_dirs"])
            file_count = len(result["bytecode_files"])

            self.root.after(
                0,
                self.found_var.set,
                f"Found: {result['total']} targets",
            )

            self.log("")
            self.log(f"__pycache__ directories: {cache_count}")
            self.log(f"Bytecode files: {file_count}")
            self.log(
                f"Total eligible size: "
                f"{format_size(result['bytes'])}"
            )

            if result["total"] == 0:
                self.log("")
                self.log("Nothing to clean.")
                self.set_status("Clean - nothing found")

                self.root.after(
                    0,
                    self._cleanup_finished,
                    0,
                    0,
                    [],
                )
                return

            self.log("")
            self.log("Deleting only approved cleanup targets...")

            self.set_status("Removing safe targets...")

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
                f"Removed: {total_removed}",
            )

            self.root.after(
                0,
                self._cleanup_finished,
                deleted["deleted_dirs"],
                deleted["deleted_files"],
                deleted["failed"],
            )

        except Exception as exc:
            self.log("")
            self.log(f"ERROR: {exc}")

            self.root.after(
                0,
                self._cleanup_error,
                str(exc),
            )

    def _cleanup_finished(
        self,
        deleted_dirs: int,
        deleted_files: int,
        failed,
    ):
        self.running = False
        self.clean_button.configure(state="normal")

        if failed:
            self.status_var.set("Completed with warnings")

            self.log("")
            self.log("=" * 60)
            self.log("Cleanup completed with warnings.")
            self.log(
                f"Directories removed: {deleted_dirs}"
            )
            self.log(
                f"Files removed: {deleted_files}"
            )
            self.log(
                f"Failed targets: {len(failed)}"
            )
            self.log("=" * 60)

            messagebox.showwarning(
                APP_TITLE,
                "Cleanup completed, but some targets could not be removed.\n\n"
                f"Directories removed: {deleted_dirs}\n"
                f"Files removed: {deleted_files}\n"
                f"Failed: {len(failed)}",
            )

        else:
            self.status_var.set("Clean completed successfully")

            self.log("")
            self.log("=" * 60)
            self.log("Cleanup completed successfully.")
            self.log(
                f"Directories removed: {deleted_dirs}"
            )
            self.log(
                f"Files removed: {deleted_files}"
            )
            self.log("")
            self.log(
                "No source code or project data was targeted."
            )
            self.log(
                "No Git commands were executed."
            )
            self.log("=" * 60)

            messagebox.showinfo(
                APP_TITLE,
                "ORION CLEAN completed successfully.\n\n"
                f"__pycache__ directories removed: {deleted_dirs}\n"
                f"Bytecode files removed: {deleted_files}\n\n"
                "Source code and project data were not targeted.",
            )

    def _cleanup_error(self, error_message: str):
        self.running = False
        self.clean_button.configure(state="normal")

        self.status_var.set("Error")

        messagebox.showerror(
            APP_TITLE,
            "Cleanup was stopped safely.\n\n"
            + error_message,
        )


# ============================================================
# Application entry point
# ============================================================

def main():
    root = tk.Tk()

    # Basic Windows-friendly appearance.
    try:
        root.tk.call(
            "tk",
            "scaling",
            1.0,
        )
    except Exception:
        pass

    app = OrionCleanApp(root)

    root.mainloop()


if __name__ == "__main__":
    main()