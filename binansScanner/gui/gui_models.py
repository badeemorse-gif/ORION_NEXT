"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : gui.gui_models
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

GUI layer data models representing immutable data structures for UI state,
notifications, actions, and operation results completely decoupled from any
GUI frameworks, widgets, or core backend services.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class GuiState:
    """Immutable data structure representing the current state of the GUI application."""
    connected: bool
    running: bool
    busy: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GuiNotification:
    """Immutable data structure representing a notification message displayed in the GUI."""
    title: str
    message: str
    level: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GuiAction:
    """Immutable data structure representing an interactive action state in the GUI."""
    name: str
    enabled: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GuiResult:
    """Immutable data structure representing the outcome of a GUI-triggered operation."""
    success: bool
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# End Of File
# =============================================================================