"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : bootstrap.bootstrap_models
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

Bootstrap layer data models representing immutable configuration options,
execution results, and initialization status snapshots decoupled from all
core services, infrastructure components, and UI entry points.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class BootstrapOptions:
    """Immutable structure representing system bootstrap configuration options."""
    environment: str
    debug: bool
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Immutable structure representing the final outcome of the system bootstrap sequence."""
    success: bool
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BootstrapStatus:
    """Immutable structure capturing a real-time status snapshot of the bootstrap engine."""
    initialized: bool
    loaded_components: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# End Of File
# =============================================================================