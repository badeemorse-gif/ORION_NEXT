"""Compatibility launcher for the canonical isolated synchronization GUI."""
from __future__ import annotations
from pathlib import Path
import runpy
SAFE_GUI = Path(__file__).with_name("orion_safe_sync_gui.pyw")
runpy.run_path(str(SAFE_GUI), run_name="__main__")
