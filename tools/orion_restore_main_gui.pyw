"""Compatibility launcher for the safe ORION synchronization GUI.

The previous implementation could materialize origin/main into PROJECT_ROOT.
That path is retired. All synchronization now goes through the isolated
controller in tools/orion_sync_safe.py and the safe GUI wrapper.
"""
from __future__ import annotations

from pathlib import Path
import runpy

SAFE_GUI = Path(__file__).with_name("orion_restore_main_safe_gui.pyw")
runpy.run_path(str(SAFE_GUI), run_name="__main__")
