"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : application.application_models
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

Application layer data models representing immutable structures for high-level
requests, responses, and system execution status snapshots decoupled from any
transport, UI, or core pipeline logic.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ApplicationRequest:
    """Immutable data structure representing a high-level application request payload."""
    request_id: str
    action: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ApplicationResponse:
    """Immutable data structure representing a high-level application execution response."""
    success: bool
    message: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ApplicationStatus:
    """Immutable data structure capturing a real-time runtime status snapshot of the application."""
    running: bool
    current_task: str | None
    active_jobs: int
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# End Of File
# =============================================================================