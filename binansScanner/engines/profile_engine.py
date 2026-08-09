"""
===============================================================================
ORION
Module : engines.profile_engine
Version: 3.0.0

Canonical Profile Engine.

Boundary
--------
MarketDataset
    |
    v
ProfileEngine
    |
    v
ProfileResult

The engine never mutates MarketDataset or TimeframeData.
ProfileBuilder remains responsible for the actual market-characteristics
calculation.
===============================================================================
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from typing import Any, Optional

import pandas as pd

from enums import Timeframe
from models.market import MarketDataset, TimeframeData
from models.profile import (
    EMAAlignment,
    MarketCharacteristics,
    MarketPhaseType,
    MomentumState,
    ProfileResult,
    ProfileStatistics,
    RiskLevel,
    TimeframeProfile,
    TrendStrengthType,
    TrendType,
    VolatilityLevelType,
    VolumeStrength,
)
from engines.profile_builder import ProfileBuilder


base_logger = logging.getLogger(__name__)


TIMEFRAME_WEIGHTS: dict[str, float] = {
    "1d": 0.40,
    "4h": 0.35,
    "1h": 0.25,
}


class ProfileEngineError(Exception):
    """Base exception for ProfileEngine failures."""


class InvalidProfileData(ProfileEngineError):
    """Raised when market data cannot be used to build a profile."""


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter carrying Profile execution context."""

    def process(
        self,
        msg: str,
        kwargs: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(
            f"{key}={value}"
            for key, value in context.items()
            if value is not None
        )

        if context_str:
            return f"[{context_str}] {msg}", kwargs

        return msg, kwargs


class ProfileEngine:
    """
    Stateless coordinator for Profile generation.

    The engine owns ProfileResult construction only.
    ProfileBuilder owns market-characteristics calculation.
    """

    def __init__(
        self,
        builder: Optional[ProfileBuilder] = None,
    ) -> None:
        self._builder = builder or ProfileBuilder()

        self.logger = LoggerAdapter(
            base_logger,
            {
                "symbol": None,
                "timeframe": None,
                "operation": "init",
            },
        )

    # =========================================================================
    # Canonical Public Contract
    # =========================================================================

    def build_profile(
        self,
        dataset: MarketDataset,
    ) -> ProfileResult:
        """
        Build the canonical ProfileResult from a MarketDataset.

        MarketDataset is read-only from the Profile layer.
        No profile state is written back to the dataset or its timeframes.
        """

        if not isinstance(dataset, MarketDataset):
            raise TypeError(
                "ProfileEngine.build_profile() requires MarketDataset."
            )

        symbol = dataset.symbol
        started = time.perf_counter()

        logger = self._get_logger(
            symbol=symbol,
            operation="build_profile",
        )

        logger.info("Building canonical profile result.")

        timeframe_profiles: list[TimeframeProfile] = []
        warnings: list[str] = []
        blocks: list[str] = []

        for timeframe, timeframe_data in dataset.timeframes.items():
            try:
                profile = self.build_timeframe_profile(
                    timeframe_data,
                    symbol=symbol,
                )

                timeframe_profiles.append(profile)
                warnings.extend(profile.warnings)

            except InvalidProfileData as exc:
                message = str(exc)
                warnings.append(message)
                blocks.append(message)

            except ProfileEngineError as exc:
                message = str(exc)
                warnings.append(message)
                blocks.append(message)

        market = self.merge_characteristics(
            [
                (
                    profile.timeframe,
                    profile.characteristics,
                )
                for profile in timeframe_profiles
            ]
        )

        statistics = self._build_statistics(
            timeframe_profiles=timeframe_profiles,
        )

        if not timeframe_profiles:
            blocks.append(
                "No valid timeframe data was available for profile generation."
            )

        is_tradeable = bool(
            timeframe_profiles
            and not blocks
            and market.confidence > 0.0
        )

        elapsed_ms = (time.perf_counter() - started) * 1000.0

        logger = self._get_logger(
            symbol=symbol,
            operation="build_profile",
            trend=market.trend,
            market_phase=market.market_phase,
            risk=market.risk_level,
            confidence=market.confidence,
            elapsed_ms=elapsed_ms,
        )

        logger.info(
            "Canonical profile result built successfully."
        )

        return ProfileResult(
            symbol=symbol,
            market=market,
            statistics=statistics,
            timeframes=tuple(timeframe_profiles),
            warnings=tuple(dict.fromkeys(warnings)),
            blocks=tuple(dict.fromkeys(blocks)),
            is_tradeable=is_tradeable,
        )

    # =========================================================================
    # Timeframe Contract
    # =========================================================================

    def build_timeframe_profile(
        self,
        timeframe_data: TimeframeData,
        symbol: Optional[str] = None,
    ) -> TimeframeProfile:
        """
        Build an immutable TimeframeProfile.

        This method never mutates TimeframeData.
        """

        if not isinstance(timeframe_data, TimeframeData):
            raise TypeError(
                "build_timeframe_profile() requires TimeframeData."
            )

        timeframe = timeframe_data.timeframe

        timeframe_str = (
            timeframe.value
            if hasattr(timeframe, "value")
            else str(timeframe)
        )

        started = time.perf_counter()

        dataframe = timeframe_data.dataframe

        self._validate_dataframe(
            dataframe,
            timeframe_str,
        )

        try:
            characteristics = self._builder.build(dataframe)

        except Exception as exc:
            if isinstance(exc, ProfileEngineError):
                raise

            raise ProfileEngineError(
                f"Failed to build profile for timeframe "
                f"{timeframe_str}: {exc}"
            ) from exc

        elapsed_ms = (time.perf_counter() - started) * 1000.0

        logger = self._get_logger(
            symbol=symbol,
            timeframe=timeframe,
            operation="build_timeframe_profile",
            trend=characteristics.trend,
            market_phase=characteristics.market_phase,
            risk=characteristics.risk_level,
            confidence=characteristics.confidence,
            elapsed_ms=elapsed_ms,
        )

        logger.info(
            f"Profile built successfully for timeframe {timeframe_str}."
        )

        return TimeframeProfile(
            timeframe=timeframe_str,
            characteristics=characteristics,
            candles_count=int(timeframe_data.candles_count),
            first_timestamp=timeframe_data.first_timestamp,
            last_timestamp=timeframe_data.last_timestamp,
            data_health=timeframe_data.data_health,
            missing_candles=0,
            warnings=(),
        )

    # =========================================================================
    # Characteristics Merge
    # =========================================================================

    def merge_characteristics(
        self,
        tf_profiles: list[
            tuple[str, MarketCharacteristics]
        ],
    ) -> MarketCharacteristics:
        """
        Merge timeframe-level characteristics into one canonical
        MarketCharacteristics instance.
        """

        if not tf_profiles:
            return MarketCharacteristics()

        total_weight = 0.0

        weighted_confidence = 0.0
        weighted_volatility = 0.0
        weighted_liquidity = 0.0
        weighted_trend_score = 0.0
        weighted_momentum_score = 0.0
        weighted_volume_score = 0.0
        weighted_volatility_score = 0.0

        trends: list[str] = []
        trend_strengths: list[str] = []
        phases: list[str] = []
        risks: list[str] = []
        momentums: list[str] = []
        volume_strengths: list[str] = []
        volatility_levels: list[str] = []
        price_locations: list[str] = []
        ema_alignments: list[str] = []

        supports: list[float] = []
        resistances: list[float] = []

        latest_characteristics = tf_profiles[-1][1]

        for timeframe_str, characteristics in tf_profiles:
            weight = TIMEFRAME_WEIGHTS.get(
                timeframe_str,
                0.25,
            )

            total_weight += weight

            weighted_confidence += (
                characteristics.confidence * weight
            )

            weighted_volatility += (
                characteristics.volatility * weight
            )

            weighted_liquidity += (
                characteristics.liquidity * weight
            )

            weighted_trend_score += (
                characteristics.trend_score * weight
            )

            weighted_momentum_score += (
                characteristics.momentum_score * weight
            )

            weighted_volume_score += (
                characteristics.volume_score * weight
            )

            weighted_volatility_score += (
                characteristics.volatility_score * weight
            )

            trends.append(characteristics.trend)
            trend_strengths.append(
                characteristics.trend_strength
            )
            phases.append(characteristics.market_phase)
            risks.append(characteristics.risk_level)
            momentums.append(characteristics.momentum)
            volume_strengths.append(
                characteristics.volume_strength
            )
            volatility_levels.append(
                characteristics.volatility_level
            )
            price_locations.append(
                characteristics.price_location
            )
            ema_alignments.append(
                characteristics.ema_alignment
            )

            if characteristics.support > 0:
                supports.append(characteristics.support)

            if characteristics.resistance > 0:
                resistances.append(
                    characteristics.resistance
                )

        if total_weight <= 0:
            return MarketCharacteristics()

        confidence = (
            weighted_confidence / total_weight
        )

        volatility = (
            weighted_volatility / total_weight
        )

        liquidity = (
            weighted_liquidity / total_weight
        )

        trend_score = (
            weighted_trend_score / total_weight
        )

        momentum_score = (
            weighted_momentum_score / total_weight
        )

        volume_score = (
            weighted_volume_score / total_weight
        )

        volatility_score = (
            weighted_volatility_score / total_weight
        )

        return MarketCharacteristics(
            trend=self._dominant_value(
                trends,
                TrendType.SIDEWAYS.value,
            ),
            trend_strength=self._dominant_value(
                trend_strengths,
                TrendStrengthType.WEAK.value,
            ),
            volatility=volatility,
            volatility_level=self._dominant_value(
                volatility_levels,
                VolatilityLevelType.NORMAL.value,
            ),
            momentum=self._dominant_value(
                momentums,
                MomentumState.NEUTRAL.value,
            ),
            volume_strength=self._dominant_value(
                volume_strengths,
                VolumeStrength.NORMAL.value,
            ),
            liquidity=liquidity,
            price_location=self._dominant_value(
                price_locations,
                "Middle",
            ),
            support=min(supports) if supports else 0.0,
            resistance=(
                max(resistances)
                if resistances
                else 0.0
            ),
            ema_alignment=self._merge_ema_alignment(
                ema_alignments
            ),
            market_phase=self._dominant_value(
                phases,
                MarketPhaseType.RANGE.value,
            ),
            risk_level=self._dominant_value(
                risks,
                RiskLevel.MEDIUM.value,
            ),
            confidence=confidence,
            timestamp=latest_characteristics.timestamp,
            distance_to_support=(
                latest_characteristics.distance_to_support
            ),
            distance_to_resistance=(
                latest_characteristics.distance_to_resistance
            ),
            distance_to_ema200=(
                latest_characteristics.distance_to_ema200
            ),
            trend_score=trend_score,
            momentum_score=momentum_score,
            volume_score=volume_score,
            volatility_score=volatility_score,
        )

    # =========================================================================
    # Compatibility Helper
    # =========================================================================

    def merge_profiles(
        self,
        tf_profiles: list[
            tuple[str, MarketCharacteristics]
        ],
    ) -> MarketCharacteristics:
        """
        Compatibility alias for the old merge_profiles name.

        The returned object is the canonical MarketCharacteristics contract.
        """

        return self.merge_characteristics(tf_profiles)

    def profile_summary(
        self,
        profile: MarketCharacteristics,
    ) -> dict[str, Any]:
        """Return a serializable summary of MarketCharacteristics."""

        return {
            "trend": profile.trend,
            "trend_strength": profile.trend_strength,
            "volatility": profile.volatility,
            "volatility_level": profile.volatility_level,
            "momentum": profile.momentum,
            "volume_strength": profile.volume_strength,
            "liquidity": profile.liquidity,
            "price_location": profile.price_location,
            "support": profile.support,
            "resistance": profile.resistance,
            "ema_alignment": profile.ema_alignment,
            "market_phase": profile.market_phase,
            "risk_level": profile.risk_level,
            "confidence": profile.confidence,
            "timestamp": (
                profile.timestamp.isoformat()
                if profile.timestamp
                else None
            ),
            "distance_to_support": (
                profile.distance_to_support
            ),
            "distance_to_resistance": (
                profile.distance_to_resistance
            ),
            "distance_to_ema200": (
                profile.distance_to_ema200
            ),
            "trend_score": profile.trend_score,
            "momentum_score": profile.momentum_score,
            "volume_score": profile.volume_score,
            "volatility_score": profile.volatility_score,
        }

    # =========================================================================
    # Statistics
    # =========================================================================

    def _build_statistics(
        self,
        timeframe_profiles: list[TimeframeProfile],
    ) -> ProfileStatistics:
        """Build consolidated Profile statistics."""

        if not timeframe_profiles:
            return ProfileStatistics()

        total_candles = sum(
            max(profile.candles_count, 0)
            for profile in timeframe_profiles
        )

        total_missing = sum(
            max(profile.missing_candles, 0)
            for profile in timeframe_profiles
        )

        newest_values = [
            profile.last_timestamp
            for profile in timeframe_profiles
            if profile.last_timestamp is not None
        ]

        oldest_values = [
            profile.first_timestamp
            for profile in timeframe_profiles
            if profile.first_timestamp is not None
        ]

        confidence_values = [
            profile.confidence
            for profile in timeframe_profiles
        ]

        health_score = (
            sum(confidence_values)
            / len(confidence_values)
            if confidence_values
            else 0.0
        )

        confidence_limit = (
            min(confidence_values)
            if confidence_values
            else 0.0
        )

        completion_ratio = (
            max(
                0.0,
                min(
                    1.0,
                    (
                        total_candles - total_missing
                    )
                    / total_candles,
                ),
            )
            if total_candles > 0
            else 0.0
        )

        return ProfileStatistics(
            health_score=health_score,
            confidence_limit=confidence_limit,
            completion_ratio=completion_ratio,
            total_candles=total_candles,
            missing_candles=total_missing,
            newest_candle=(
                max(newest_values)
                if newest_values
                else None
            ),
            oldest_candle=(
                min(oldest_values)
                if oldest_values
                else None
            ),
        )

    # =========================================================================
    # Validation
    # =========================================================================

    def _validate_dataframe(
        self,
        dataframe: pd.DataFrame,
        timeframe: str,
    ) -> None:
        """
        Validate the minimum OHLCV contract required by ProfileBuilder.
        """

        if dataframe is None or dataframe.empty:
            raise InvalidProfileData(
                f"DataFrame for timeframe "
                f"{timeframe} is empty or None."
            )

        required_columns = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        missing_columns = (
            required_columns
            - set(dataframe.columns)
        )

        if missing_columns:
            raise InvalidProfileData(
                f"DataFrame for timeframe "
                f"{timeframe} is missing required "
                f"columns: {sorted(missing_columns)}"
            )

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    @staticmethod
    def _dominant_value(
        values: list[str],
        default: str,
    ) -> str:
        if not values:
            return default

        return Counter(values).most_common(1)[0][0]

    @staticmethod
    def _merge_ema_alignment(
        values: list[str],
    ) -> str:
        if not values:
            return EMAAlignment.NONE.value

        normalized = {
            str(value)
            for value in values
        }

        if normalized == {
            EMAAlignment.BULLISH.value
        }:
            return EMAAlignment.BULLISH.value

        if normalized == {
            EMAAlignment.BEARISH.value
        }:
            return EMAAlignment.BEARISH.value

        return EMAAlignment.NONE.value

    def _get_logger(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[Timeframe | str] = None,
        operation: Optional[str] = None,
        trend: Optional[str] = None,
        market_phase: Optional[str] = None,
        risk: Optional[str] = None,
        confidence: Optional[float] = None,
        elapsed_ms: Optional[float] = None,
    ) -> LoggerAdapter:
        timeframe_value = (
            timeframe.value
            if hasattr(timeframe, "value")
            else str(timeframe)
            if timeframe is not None
            else None
        )

        return LoggerAdapter(
            base_logger,
            {
                "symbol": symbol,
                "timeframe": timeframe_value,
                "operation": operation,
                "trend": trend,
                "market_phase": market_phase,
                "risk": risk,
                "confidence": confidence,
                "elapsed_ms": elapsed_ms,
            },
        )


__all__ = [
    "ProfileEngine",
    "ProfileEngineError",
    "InvalidProfileData",
    "TIMEFRAME_WEIGHTS",
]