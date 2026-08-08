"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : api.api_models
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

API data models representing immutable data structures for API requests,
responses, and error payloads without framework or web protocol dependencies.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ApiRequest:
    """Immutable structure representing an incoming API request context."""
    request_id: str
    endpoint: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ApiResponse:
    """Immutable structure representing an outgoing API response payload."""
    success: bool
    message: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ApiError:
    """Immutable structure representing a structured API error status and message."""
    code: str
    message: str


# =============================================================================
# End Of File
# =============================================================================