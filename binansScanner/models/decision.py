"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : models.decision
Version      : 2.0.0
===============================================================================

Canonical Decision Result contract.

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DecisionResult:
    """
    Canonical output of DecisionEngine.
    """

    decision: str = "WAIT"
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)