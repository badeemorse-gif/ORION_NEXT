"""ORION Restore startup launcher.

Loads the dynamic restore GUI from the repository and performs the existing
remote-branch discovery immediately after the window is created. The restore
engine itself remains unchanged.
"""

import importlib.util
import os
import tkinter as tk
from tkinter import messagebox


BASE_NAME = "orion_restore_gui_dynamic.pyw"
TARGET = os.path.join(os.path.dirname(__file__), BASE_NAME)


if not os.path.isfile(TARGET):
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "ORION Restore",
        f"ORION Restore dynamic file not found:\n\n{TARGET}",
    )
    root.destroy()
    raise SystemExit(1)

spec = importlib.util.spec_from_file_location("orion_restore_dynamic", TARGET)
if spec is None or spec.loader is None:
    raise RuntimeError("تعذر تحميل ORION Restore dynamic launcher.")

dynamic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dynamic)


if __name__ == "__main__":
    root = tk.Tk()
    app = dynamic.base.OrionRestoreApp(root)
    app.source_label.configure(
        text=(
            "GitHub → Git → Local  |  ALL (discovering branches...)"
            if app.branch == dynamic.ALL_BRANCH
            else f"GitHub → Git → Local  |  {app.branch}"
        )
    )
    # Branch discovery already exists in the dynamic GUI. The missing piece
    # was invoking it at startup. Run it asynchronously so the window stays
    # responsive and no synchronization is started implicitly.
    root.after(250, app.refresh_branches)
    root.mainloop()
