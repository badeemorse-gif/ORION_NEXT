"""
===============================================================================
ORION
Module : models.profile
Version: 2.0.0

Canonical Profile domain contracts.

This module owns the result contracts of the Profile layer.

Important boundary:
    MarketDataset is input data.
    ProfileResult is the output of Profile analysis.

Profile results must never be written back into MarketDataset.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# =============================================================================
# Enumerations
# =============================================================================


class TrendType(str, Enum):
    BULLISH = "Bullish"
    BEARISH = "Bearish"
    SIDEWAYS = "Sideways"


class TrendStrengthType(str, Enum):
    WEAK = "Weak"
    MEDIUM = "Medium"
    STRONG = "Strong"
    VERY_STRONG = "Very Strong"


class MarketPhaseType(str, Enum):
    ACCUMULATION = "Accumulation"
    MARKUP = "Markup"
    DISTRIBUTION = "Distribution"
    MARKDOWN = "Markdown"
    RANGE = "Range"


class VolatilityLevelType(str, Enum):
    LOW = "Low"
    NORMAL = "Normal"
    HIGH = "High"
    EXTREME = "Extreme"


class MomentumState(str, Enum):
    STRONG_BUY = "Strong Buy"
    BUY = "Buy"
    NEUTRAL = "Neutral"
    SELL = "Sell"
    STRONG_SELL = "Strong Sell"


class VolumeStrength(str, Enum):
    WEAK = "Weak"
    NORMAL = "Normal"
    STRONG = "Strong"


class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    EXTREME = "Extreme"


class EMAAlignment(str, Enum):
    BULLISH = "Bullish"
    BEARISH = "Bearish"
    NONE = "None"


# =============================================================================
# Canonical Market Characteristics
# =============================================================================


@dataclass(slots=True, frozen=True)
class MarketCharacteristics:
    """
    Objective characteristics extracted from market data.

    This replaces the ambiguous MarketProfile model previously defined
    independently inside profile.py and profile_builder.py.
    """

    trend: str = TrendType.SIDEWAYS.value
    trend_strength: str = TrendStrengthType.WEAK.value

    volatility: float = 0.0
    volatility_level: str = VolatilityLevelType.NORMAL.value

    momentum: str = MomentumState.NEUTRAL.value
    volume_strength: str = VolumeStrength.NORMAL.value

    liquidity: float = 0.0

    price_location: str = "Middle"

    support: float = 0.0
    resistance: float = 0.0

    ema_alignment: str = EMAAlignment.NONE.value

    market_phase: str = MarketPhaseType.RANGE.value
    risk_level: str = RiskLevel.MEDIUM.value

    confidence: float = 50.0

    timestamp: Optional[datetime] = None

    distance_to_support: float = 0.0
    distance_to_resistance: float = 0.0
    distance_to_ema200: float = 0.0

    trend_score: float = 0.0
    momentum_score: float = 0.0
    volume_score: float = 0.0
    volatility_score: float = 0.0

    def __post_init__(self) -> None:
        """
        Enforce basic domain bounds without embedding business rules.
        """

        confidence = min(max(float(self.confidence), 0.0), 100.0)

        trend_score = min(max(float(self.trend_score), 0.0), 100.0)
        momentum_score = min(max(float(self.momentum_score), 0.0), 100.0)
        volume_score = min(max(float(self.volume_score), 0.0), 100.0)
        volatility_score = min(max(float(self.volatility_score), 0.0), 100.0)

        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "trend_score", trend_score)
        object.__setattr__(self, "momentum_score", momentum_score)
        object.__setattr__(self, "volume_score", volume_score)
        object.__setattr__(self, "volatility_score", volatility_score)


# =============================================================================
# Timeframe Profile
# =============================================================================


@dataclass(slots=True, frozen=True)
class TimeframeProfile:
    """
    Profile result for one timeframe.

    The timeframe profile contains characteristics and the minimum metadata
    needed to explain how the result was produced.
    """

    timeframe: str

    characteristics: MarketCharacteristics

    candles_count: int = 0

    first_timestamp: Optional[datetime] = None
    last_timestamp: Optional[datetime] = None

    data_health: Optional[object] = None

    missing_candles: int = 0

    warnings: tuple[str, ...] = ()

    @property
    def trend(self) -> str:
        return self.characteristics.trend

    @property
    def confidence(self) -> float:
        return self.characteristics.confidence

    @property
    def risk_level(self) -> str:
        return self.characteristics.risk_level


# =============================================================================
# Profile Statistics
# =============================================================================


@dataclass(slots=True, frozen=True)
class ProfileStatistics:
    """
    Consolidated statistics for the complete Profile result.
    """

    health_score: float = 0.0

    confidence_limit: float = 0.0

    completion_ratio: float = 0.0

    total_candles: int = 0

    missing_candles: int = 0

    newest_candle: Optional[datetime] = None

    oldest_candle: Optional[datetime] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "health_score",
            min(max(float(self.health_score), 0.0), 100.0),
        )

        object.__setattr__(
            self,
            "confidence_limit",
            min(max(float(self.confidence_limit), 0.0), 100.0),
        )

        object.__setattr__(
            self,
            "completion_ratio",
            min(max(float(self.completion_ratio), 0.0), 1.0),
        )


# =============================================================================
# Canonical Profile Result
# =============================================================================


@dataclass(slots=True, frozen=True)
class ProfileResult:
    """
    Canonical output of ProfileEngine.

    This is the only object that represents the completed Profile stage.

    It is intentionally independent from MarketDataset.
    """

    symbol: str

    market: MarketCharacteristics

    statistics: ProfileStatistics

    timeframes: tuple[TimeframeProfile, ...] = ()

    warnings: tuple[str, ...] = ()

    blocks: tuple[str, ...] = ()

    is_tradeable: bool = False

    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)

    @property
    def has_blocks(self) -> bool:
        return bool(self.blocks)

    @property
    def is_valid(self) -> bool:
        return self.is_tradeable and not self.has_blocks

    @property
    def timeframe_count(self) -> int:
        return len(self.timeframes)


# =============================================================================
# Compatibility Helpers
# =============================================================================


def normalize_timeframe_profiles(
    profiles: list[TimeframeProfile],
) -> tuple[TimeframeProfile, ...]:
    """
    Convert mutable lists produced during construction into the immutable
    canonical representation used by ProfileResult.
    """

    return tuple(profiles)


def normalize_messages(messages: list[str]) -> tuple[str, ...]:
    """
    Normalize warning/block collections into immutable tuples.
    """

    return tuple(str(message) for message in messages)
