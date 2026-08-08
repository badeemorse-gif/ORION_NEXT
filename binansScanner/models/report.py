"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : models.report
Version      : 1.0.0
===============================================================================

Report domain models.

These models represent the final report generated after all analysis
engines complete their work.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from enums import (
    DecisionPriority,
    DecisionType,
)


# =============================================================================
# Report Statistics
# =============================================================================

@dataclass(slots=True)
class ReportStatistics:
    """
    Summary statistics for the generated report.
    """

    total_score: float

    confidence: float

    health_score: float

    risk_reward_ratio: float

    generated_at: datetime


# =============================================================================
# Trade Levels
# =============================================================================

@dataclass(slots=True)
class TradeLevels:
    """
    Trading price levels.
    """

    entry_price: float

    stop_loss: float

    take_profit_1: float

    take_profit_2: float

    take_profit_3: float


# =============================================================================
# Report Summary
# =============================================================================

@dataclass(slots=True)
class ReportSummary:
    """
    High-level report summary.
    """

    symbol: str

    decision: DecisionType

    priority: DecisionPriority

    score: float

    confidence: float

    generated_at: datetime


# =============================================================================
# Report Result
# =============================================================================

@dataclass(slots=True)
class ReportResult:
    """
    Final report produced by Report Engine.
    """

    summary: ReportSummary

    statistics: ReportStatistics

    trade_levels: Optional[TradeLevels]

    highlights: list[str]

    warnings: list[str]

    generated_at: datetime

    @property
    def symbol(self) -> str:
        """
        Returns report symbol.
        """
        return self.summary.symbol

    @property
    def decision(self) -> DecisionType:
        """
        Returns final decision.
        """
        return self.summary.decision

    @property
    def priority(self) -> DecisionPriority:
        """
        Returns decision priority.
        """
        return self.summary.priority

    @property
    def has_warnings(self) -> bool:
        """
        Returns True if warnings exist.
        """
        return len(self.warnings) > 0

    @property
    def is_entry_candidate(self) -> bool:
        """
        Returns True if the report recommends immediate entry.
        """
        return self.summary.decision == DecisionType.ENTRY_NOW


# =============================================================================
# End Of File
# =============================================================================
