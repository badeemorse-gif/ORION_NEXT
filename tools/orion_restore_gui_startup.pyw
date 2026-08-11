"""ORION Restore startup launcher.

Loads the repository-side ALL-hardened restore GUI and discovers every remote
branch immediately after startup. Individual branch restore behavior remains
provided by the existing engine; only ALL materialization is hardened.
"""

import importlib.util
import os
import tkinter as tk
from tkinter import messagebox

BASE_NAME = "orion_restore_gui_all_fixed.pyw"
TARGET = os.path.join(os.path.dirname(__file__), BASE_NAME)

if not os.path.isfile(TARGET):
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "ORION Restore",
        f"ORION Restore ALL-fixed file not found:\n\n{TARGET}",
    )
    root.destroy()
    raise SystemExit(1)

spec = importlib.util.spec_from_file_location("orion_restore_all_fixed", TARGET)
if spec is None or spec.loader is None:
    raise RuntimeError("تعذر تحميل ORION Restore ALL-fixed launcher.")

fixed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixed)

if __name__ == "__main__":
    root = tk.Tk()
    app = fixed.base.OrionRestoreApp(root)
    app.source_label.configure(
        text=(
            "GitHub → Git → Local  |  ALL (discovering all branches...)"
            if app.branch == fixed.ALL_BRANCH
            else f"GitHub → Git → Local  |  {app.branch}"
        )
    )
    # Discover all remote branches at startup without starting synchronization.
    root.after(250, app.refresh_branches)
    root.mainloop()
