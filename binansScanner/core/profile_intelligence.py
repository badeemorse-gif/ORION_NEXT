"""
===============================================================================
ORION
Module : core.profile_intelligence
Version: 1.2.0

Profile Intelligence — Fail-Closed
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Optional

from models.profile import (
    EMAAlignment,
    MarketCharacteristics,
    MarketPhaseType,
    MomentumState,
    ProfileResult,
    RiskLevel,
    TrendStrengthType,
    TrendType,
    VolatilityLevelType,
    VolumeStrength,
)


class ProfileRecommendation(str, Enum):
    """Canonical recommendation state produced by ProfileIntelligence."""

    BULLISH = "Bullish"
    BEARISH = "Bearish"
    NEUTRAL = "Neutral"
    BLOCKED = "Blocked"


@dataclass(frozen=True, slots=True)
class ProfileIntelligenceResult:
    """Immutable result of ProfileIntelligence evaluation."""

    recommendation: str
    confidence: float
    reasons: tuple[str, ...] = ()
    blocked: bool = False

    @property
    def is_directional(self) -> bool:
        return self.recommendation in {
            ProfileRecommendation.BULLISH.value,
            ProfileRecommendation.BEARISH.value,
        }

    @property
    def is_valid(self) -> bool:
        return (
            self.recommendation in {
                ProfileRecommendation.BULLISH.value,
                ProfileRecommendation.BEARISH.value,
                ProfileRecommendation.NEUTRAL.value,
            }
            and not self.blocked
            and isfinite(self.confidence)
            and 0.0 <= self.confidence <= 100.0
        )


class ProfileIntelligence:
    """Deterministic interpreter for the canonical ProfileResult."""

    _VALID_TRENDS = {item.value for item in TrendType}
    _VALID_MOMENTUM = {item.value for item in MomentumState}
    _VALID_RISKS = {item.value for item in RiskLevel}
    _VALID_EMA = {item.value for item in EMAAlignment}
    _VALID_PHASES = {item.value for item in MarketPhaseType}
    _VALID_TREND_STRENGTH = {item.value for item in TrendStrengthType}
    _VALID_VOLATILITY = {item.value for item in VolatilityLevelType}
    _VALID_VOLUME = {item.value for item in VolumeStrength}

    _BULLISH_MOMENTUM = {
        MomentumState.STRONG_BUY.value,
        MomentumState.BUY.value,
    }
    _BEARISH_MOMENTUM = {
        MomentumState.STRONG_SELL.value,
        MomentumState.SELL.value,
    }

    def evaluate(self, profile: Optional[ProfileResult]) -> ProfileIntelligenceResult:
        """Evaluate a profile and fail closed on every invalid boundary."""
        invalid_reason = self._validate_profile(profile)
        if invalid_reason is not None:
            return self._blocked(invalid_reason)

        assert profile is not None
        market = profile.market

        if market.risk_level == RiskLevel.EXTREME.value:
            return ProfileIntelligenceResult(
                recommendation=ProfileRecommendation.NEUTRAL.value,
                confidence=0.0,
                reasons=("Extreme market risk blocks directional profile intelligence.",),
                blocked=True,
            )

        if (
            market.trend == TrendType.BULLISH.value
            and market.momentum in self._BULLISH_MOMENTUM
        ):
            return self._directional_result(
                ProfileRecommendation.BULLISH.value,
                profile,
                "Trend and momentum are aligned bullishly.",
            )

        if (
            market.trend == TrendType.BEARISH.value
            and market.momentum in self._BEARISH_MOMENTUM
        ):
            return self._directional_result(
                ProfileRecommendation.BEARISH.value,
                profile,
                "Trend and momentum are aligned bearishly.",
            )

        return ProfileIntelligenceResult(
            recommendation=ProfileRecommendation.NEUTRAL.value,
            confidence=self._safe_confidence(profile),
            reasons=("Profile conditions do not support a validated directional recommendation.",),
            blocked=False,
        )

    def analyze(self, profile: Optional[ProfileResult]) -> ProfileIntelligenceResult:
        """Compatibility alias for evaluate()."""
        return self.evaluate(profile)

    def _directional_result(
        self,
        recommendation: str,
        profile: ProfileResult,
        reason: str,
    ) -> ProfileIntelligenceResult:
        confidence = self._safe_confidence(profile)
        if confidence <= 0.0:
            return self._blocked(
                "Directional profile intelligence requires positive confidence across the complete profile."
            )

        return ProfileIntelligenceResult(
            recommendation=recommendation,
            confidence=confidence,
            reasons=(reason,),
            blocked=False,
        )

    def _safe_confidence(self, profile: ProfileResult) -> float:
        values = (
            profile.market.confidence,
            profile.statistics.confidence_limit,
            *(timeframe.characteristics.confidence for timeframe in profile.timeframes),
        )
        if any(not self._finite_number(value) for value in values):
            return 0.0
        confidence = min(values)
        return min(max(float(confidence), 0.0), 100.0)

    def _validate_profile(self, profile: Optional[ProfileResult]) -> Optional[str]:
        if profile is None:
            return "ProfileResult is missing; directional intelligence is blocked."
        if not isinstance(profile, ProfileResult):
            return "Profile intelligence requires the canonical ProfileResult contract."
        if not profile.is_valid:
            return "ProfileResult is not valid/tradeable; directional intelligence is blocked."
        if not profile.timeframes:
            return "ProfileResult contains no timeframe profiles."

        if profile.market is None or profile.statistics is None:
            return "ProfileResult contains incomplete canonical market/statistics data."

        market_reason = self._validate_characteristics(profile.market, "market")
        if market_reason is not None:
            return market_reason

        statistics_reason = self._validate_statistics(profile.statistics)
        if statistics_reason is not None:
            return statistics_reason

        for timeframe in profile.timeframes:
            timeframe_name = getattr(timeframe, "timeframe", None)
            if not timeframe_name:
                return "ProfileResult contains a malformed timeframe profile."

            characteristics = getattr(timeframe, "characteristics", None)
            if not isinstance(characteristics, MarketCharacteristics):
                return (
                    f"ProfileResult contains invalid characteristics "
                    f"in timeframe {timeframe_name}."
                )

            timeframe_reason = self._validate_characteristics(
                characteristics,
                f"timeframe {timeframe_name}",
            )
            if timeframe_reason is not None:
                return timeframe_reason

            for field_name, value in (
                ("candles_count", timeframe.candles_count),
                ("missing_candles", timeframe.missing_candles),
            ):
                if not self._finite_number(value):
                    return (
                        f"ProfileResult contains non-finite {field_name} "
                        f"in timeframe {timeframe_name}."
                    )
                if float(value) < 0.0:
                    return (
                        f"ProfileResult contains out-of-range {field_name} "
                        f"in timeframe {timeframe_name}."
                    )

            if timeframe.candles_count <= 0:
                return (
                    f"ProfileResult contains no candle coverage "
                    f"in timeframe {timeframe_name}."
                )

            if timeframe.missing_candles >= timeframe.candles_count:
                return (
                    f"ProfileResult contains incomplete candle coverage "
                    f"in timeframe {timeframe_name}."
                )

        return None

    def _validate_characteristics(
        self,
        characteristics: Any,
        prefix: str,
    ) -> Optional[str]:
        if not isinstance(characteristics, MarketCharacteristics):
            return f"ProfileResult contains invalid {prefix} characteristics."

        categorical_fields = (
            ("trend", characteristics.trend, self._VALID_TRENDS),
            ("trend_strength", characteristics.trend_strength, self._VALID_TREND_STRENGTH),
            ("momentum", characteristics.momentum, self._VALID_MOMENTUM),
            ("volume_strength", characteristics.volume_strength, self._VALID_VOLUME),
            ("volatility_level", characteristics.volatility_level, self._VALID_VOLATILITY),
            ("ema_alignment", characteristics.ema_alignment, self._VALID_EMA),
            ("market_phase", characteristics.market_phase, self._VALID_PHASES),
            ("risk_level", characteristics.risk_level, self._VALID_RISKS),
        )
        for field_name, value, valid_values in categorical_fields:
            if value not in valid_values:
                return f"ProfileResult contains invalid {prefix} {field_name}: {value!r}."

        numeric_fields = (
            ("confidence", characteristics.confidence, 0.0, 100.0),
            ("trend_score", characteristics.trend_score, 0.0, 100.0),
            ("momentum_score", characteristics.momentum_score, 0.0, 100.0),
            ("volume_score", characteristics.volume_score, 0.0, 100.0),
            ("volatility_score", characteristics.volatility_score, 0.0, 100.0),
        )
        for field_name, value, lower, upper in numeric_fields:
            if not self._finite_number(value):
                return f"ProfileResult contains non-finite {prefix} {field_name}."
            if not lower <= float(value) <= upper:
                return f"ProfileResult contains out-of-range {prefix} {field_name}."

        return None

    def _validate_statistics(self, statistics: Any) -> Optional[str]:
        numeric_fields = (
            ("statistics.confidence_limit", statistics.confidence_limit, 0.0, 100.0),
            ("statistics.health_score", statistics.health_score, 0.0, 100.0),
            ("statistics.completion_ratio", statistics.completion_ratio, 0.0, 1.0),
            ("statistics.total_candles", statistics.total_candles, 0.0, None),
            ("statistics.missing_candles", statistics.missing_candles, 0.0, None),
        )
        for field_name, value, lower, upper in numeric_fields:
            if not self._finite_number(value):
                return f"ProfileResult contains non-finite {field_name}."
            numeric_value = float(value)
            if numeric_value < lower or (upper is not None and numeric_value > upper):
                return f"ProfileResult contains out-of-range {field_name}."

        if statistics.total_candles <= 0:
            return "ProfileResult contains no aggregate candle coverage."
        if statistics.missing_candles >= statistics.total_candles:
            return "ProfileResult contains incomplete aggregate candle coverage."
        if statistics.completion_ratio <= 0.0:
            return "ProfileResult has no completed market-data coverage."
        return None

    @staticmethod
    def _finite_number(value: Any) -> bool:
        try:
            return isfinite(float(value))
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _blocked(reason: str) -> ProfileIntelligenceResult:
        return ProfileIntelligenceResult(
            recommendation=ProfileRecommendation.BLOCKED.value,
            confidence=0.0,
            reasons=(reason,),
            blocked=True,
        )
