"""ORION Restore startup compatibility launcher.

This launcher fixes Windows .pyw import compatibility without modifying the
proven dynamic/ALL synchronization engines. It loads the existing ALL-fixed
engine with a .pyw-aware import loader, then discovers all remote branches at
startup while keeping the UI responsive.
"""
import importlib.abc
import importlib.util
import os
import tkinter as tk

TARGET = os.path.join(os.path.dirname(__file__), "orion_restore_gui_all_fixed.pyw")


class _PywLoader(importlib.abc.Loader):
    def __init__(self, name, path):
        self.name = name
        self.path = path

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = self.path
        module.__package__ = ""
        with open(self.path, "r", encoding="utf-8") as fh:
            source = fh.read()
        exec(compile(source, self.path, "exec"), module.__dict__)


_original = importlib.util.spec_from_file_location


def _spec_from_file_location(name, location, *args, **kwargs):
    if str(location).lower().endswith(".pyw"):
        return importlib.util.spec_from_loader(
            name, _PywLoader(name, location), origin=location
        )
    return _original(name, location, *args, **kwargs)


# The existing ALL-fixed layer imports the existing dynamic .pyw engine, which
# in turn imports the original GUI .pyw. Patch only this launcher process so
# those existing files remain unchanged.
importlib.util.spec_from_file_location = _spec_from_file_location

spec = importlib.util.spec_from_file_location("orion_restore_all_fixed", TARGET)
if spec is None or spec.loader is None:
    raise RuntimeError(f"تعذر تحميل ORION Restore: {TARGET}")

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
    root.after(250, app.refresh_branches)
    root.mainloop()
