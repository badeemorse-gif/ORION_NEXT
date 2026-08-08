"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : models.profile
Version      : 1.0.0
===============================================================================

Profile domain models.

These models describe the quality and characteristics of market data
before indicator calculation and scoring.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from enums import (
    DataHealth,
    ProfileStatus,
    TradeMode,
)


# =============================================================================
# Timeframe Profile
# =============================================================================

@dataclass(slots=True)
class TimeframeProfile:
    """
    Analysis profile for a single timeframe.
    """

    timeframe: str

    candles_count: int

    first_timestamp: Optional[datetime]

    last_timestamp: Optional[datetime]

    data_health: DataHealth

    profile_status: ProfileStatus

    is_complete: bool

    missing_candles: int = 0


# =============================================================================
# Market Profile
# =============================================================================

@dataclass(slots=True)
class MarketProfile:
    """
    Overall profile for one trading pair.
    """

    symbol: str

    trade_mode: TradeMode

    profile_status: ProfileStatus

    overall_health: DataHealth

    total_timeframes: int

    valid_timeframes: int

    generated_at: datetime


# =============================================================================
# Profile Statistics
# =============================================================================

@dataclass(slots=True)
class ProfileStatistics:
    """
    Summary statistics describing the generated profile.
    """

    health_score: float

    confidence_limit: float

    completion_ratio: float

    total_candles: int

    missing_candles: int

    newest_candle: Optional[datetime]

    oldest_candle: Optional[datetime]


# =============================================================================
# Profile Result
# =============================================================================

@dataclass(slots=True)
class ProfileResult:
    """
    Final output produced by Data Profile Engine.
    """

    market: MarketProfile

    statistics: ProfileStatistics

    timeframes: list[TimeframeProfile]

    warnings: list[str]

    blocks: list[str]

    is_tradeable: bool

    generated_at: datetime

    @property
    def has_warnings(self) -> bool:
        """
        Returns True if profile contains warnings.
        """
        return len(self.warnings) > 0

    @property
    def has_blocks(self) -> bool:
        """
        Returns True if profile contains blocking issues.
        """
        return len(self.blocks) > 0

    @property
    def is_valid(self) -> bool:
        """
        Returns overall validation state.
        """
        return (
            self.market.profile_status == ProfileStatus.VALID
            and self.is_tradeable
            and not self.has_blocks
        )


# =============================================================================
# End Of File
# =============================================================================
