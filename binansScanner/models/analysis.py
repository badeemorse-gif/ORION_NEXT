"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : models.analysis
Version      : 2.0.0
===============================================================================

Canonical Analysis Result contract.

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class AnalysisResult:
    """
    Canonical output of AnalysisEngine.

    This model contains analysis results only.
    It must not contain execution or reporting state.
    """

    market_state: str = "NEUTRAL"
    strength: float = 0.0
    signals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)