"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : models.score
Version      : 2.0.0
===============================================================================

Canonical Score Result contract.

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ScoreResult:
    """
    Canonical output of ScoreEngine.
    """

    score: float = 0.0
    category: str = "NEUTRAL"
    factors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)