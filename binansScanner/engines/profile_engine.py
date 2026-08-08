"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.profile_engine
Version      : 2.0.0
Status       : ORION Production Coordinator V2
===============================================================================

Market Profile Engine Coordinator adhering strictly to SRP, delegating
profile construction to ProfileBuilder.
===============================================================================
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import pandas as pd

from enums import Timeframe
from models.market import (
    MarketDataset,
    TimeframeData,
)
from engines.profile_builder import (
    MarketProfile,
    ProfileBuilder,
    TrendType,
    TrendStrengthType,
    MarketPhaseType,
    VolatilityLevelType,
    MomentumState,
    VolumeStrength,
    RiskLevel,
)

base_logger = logging.getLogger(__name__)


TIMEFRAME_WEIGHTS: dict[str, float] = {
    "1d": 0.40,
    "4h": 0.35,
    "1h": 0.25,
}


class ProfileEngineError(Exception):
    """Base exception for all profile engine related errors."""
    pass


class InvalidProfileData(ProfileEngineError):
    """Raised when data structure is invalid for profile extraction."""
    pass


class LoggerAdapter(logging.LoggerAdapter):
    """
    Custom LoggerAdapter to inject contextual information into every log record.
    """

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        if context_str:
            formatted_msg = f"[{context_str}] {msg}"
        else:
            formatted_msg = msg
        return formatted_msg, kwargs


class ProfileEngine:
    """
    Stateless profile generation engine coordinator adhering to ORION architecture.
    Delegates profile construction to ProfileBuilder.
    """

    def __init__(self, builder: Optional[ProfileBuilder] = None) -> None:
        self._builder = builder if builder is not None else ProfileBuilder()
        self.logger = LoggerAdapter(
            base_logger,
            {"symbol": None, "timeframe": None, "operation": "init"},
        )

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
        tf_str = (
            timeframe.value
            if hasattr(timeframe, "value")
            else str(timeframe)
            if timeframe
            else None
        )
        return LoggerAdapter(
            base_logger,
            {
                "symbol": symbol,
                "timeframe": tf_str,
                "operation": operation,
                "trend": trend,
                "market_phase": market_phase,
                "risk": risk,
                "confidence": confidence,
                "elapsed_ms": elapsed_ms,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def build_dataset_profile(self, dataset: MarketDataset) -> MarketDataset:
        """
        Build profiles for all timeframes in a MarketDataset and merge them using weighted merge.
        """
        symbol = dataset.symbol
        logger = self._get_logger(symbol=symbol, operation="build_dataset_profile")
        logger.info("Building dataset profiles across all timeframes.")

        timeframe_profiles: list[tuple[str, MarketProfile]] = []
        for tf, tf_data in dataset.timeframes.items():
            self.build_timeframe_profile(tf_data, symbol=symbol)
            if hasattr(tf_data, "profile") and tf_data.profile is not None:
                tf_str = tf.value if hasattr(tf, "value") else str(tf)
                timeframe_profiles.append((tf_str, tf_data.profile))

        if timeframe_profiles:
            dataset.profile = self.merge_profiles(timeframe_profiles)
        else:
            dataset.profile = MarketProfile()

        logger.info("Dataset profiles built and merged successfully.")
        return dataset

    def build_timeframe_profile(self, timeframe_data: TimeframeData, symbol: Optional[str] = None) -> TimeframeData:
        """
        Build a MarketProfile from a single TimeframeData dataframe by delegating to ProfileBuilder.
        """
        tf = timeframe_data.timeframe
        tf_str = tf.value if hasattr(tf, "value") else str(tf)
        start_time = time.time()

        df = timeframe_data.dataframe
        self._validate_dataframe(df, tf_str)

        try:
            profile = self._builder.build(df)
            timeframe_data.profile = profile
            timeframe_data.profile_ready = True

            elapsed_ms = (time.time() - start_time) * 1000.0
            logger = self._get_logger(
                symbol=symbol,
                timeframe=tf,
                operation="build_timeframe_profile",
                trend=profile.trend,
                market_phase=profile.market_phase,
                risk=profile.risk_level,
                confidence=profile.confidence,
                elapsed_ms=elapsed_ms,
            )
            logger.info(f"Profile built successfully for timeframe {tf_str}.")

        except Exception as e:
            if isinstance(e, ProfileEngineError):
                raise
            raise ProfileEngineError(f"Failed to build profile for timeframe {tf_str}: {e}") from e

        return timeframe_data

    def merge_profiles(self, tf_profiles: list[tuple[str, MarketProfile]]) -> MarketProfile:
        """
        Merge multiple timeframe profiles into a single consolidated MarketProfile using weighted merge.
        """
        if not tf_profiles:
            return MarketProfile()

        total_weight = 0.0
        weighted_confidence = 0.0
        weighted_volatility = 0.0
        weighted_liquidity = 0.0
        weighted_trend_score = 0.0
        weighted_momentum_score = 0.0
        weighted_volume_score = 0.0
        weighted_volatility_score = 0.0

        trends: list[str] = []
        phases: list[str] = []
        risks: list[str] = []
        supports: list[float] = []
        resistances: list[float] = []

        for tf_str, profile in tf_profiles:
            w = TIMEFRAME_WEIGHTS.get(tf_str, 0.25)
            total_weight += w
            weighted_confidence += profile.confidence * w
            weighted_volatility += profile.volatility * w
            weighted_liquidity += profile.liquidity * w
            weighted_trend_score += profile.trend_score * w
            weighted_momentum_score += profile.momentum_score * w
            weighted_volume_score += profile.volume_score * w
            weighted_volatility_score += profile.volatility_score * w

            trends.append(profile.trend)
            phases.append(profile.market_phase)
            risks.append(profile.risk_level)
            if profile.support > 0:
                supports.append(profile.support)
            if profile.resistance > 0:
                resistances.append(profile.resistance)

        if total_weight > 0:
            confidence = weighted_confidence / total_weight
            volatility = weighted_volatility / total_weight
            liquidity = weighted_liquidity / total_weight
            trend_score = weighted_trend_score / total_weight
            momentum_score = weighted_momentum_score / total_weight
            volume_score = weighted_volume_score / total_weight
            volatility_score = weighted_volatility_score / total_weight
        else:
            confidence = 50.0
            volatility = 0.0
            liquidity = 0.0
            trend_score = 0.0
            momentum_score = 0.0
            volume_score = 0.0
            volatility_score = 0.0

        dominant_trend = max(set(trends), key=trends.count) if trends else TrendType.SIDEWAYS.value
        dominant_phase = max(set(phases), key=phases.count) if phases else MarketPhaseType.RANGE.value
        dominant_risk = max(set(risks), key=risks.count) if risks else RiskLevel.MEDIUM.value

        best_support = min(supports) if supports else 0.0
        best_resistance = max(resistances) if resistances else 0.0

        latest_profile = tf_profiles[-1][1]

        return MarketProfile(
            trend=dominant_trend,
            trend_strength=TrendStrengthType.MEDIUM.value,
            volatility=volatility,
            volatility_level=VolatilityLevelType.NORMAL.value,
            momentum=MomentumState.NEUTRAL.value,
            volume_strength=VolumeStrength.NORMAL.value,
            liquidity=liquidity,
            price_location=latest_profile.price_location,
            support=best_support,
            resistance=best_resistance,
            ema_alignment=all(p.ema_alignment for _, p in tf_profiles),
            market_phase=dominant_phase,
            risk_level=dominant_risk,
            confidence=confidence,
            timestamp=latest_profile.timestamp,
            distance_to_support=latest_profile.distance_to_support,
            distance_to_resistance=latest_profile.distance_to_resistance,
            distance_to_ema200=latest_profile.distance_to_ema200,
            trend_score=trend_score,
            momentum_score=momentum_score,
            volume_score=volume_score,
            volatility_score=volatility_score,
        )

    def profile_summary(self, profile: MarketProfile) -> dict[str, Any]:
        """
        Return a summary dictionary of market profile characteristics.
        """
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
            "timestamp": profile.timestamp.isoformat() if profile.timestamp else None,
            "distance_to_support": profile.distance_to_support,
            "distance_to_resistance": profile.distance_to_resistance,
            "distance_to_ema200": profile.distance_to_ema200,
            "trend_score": profile.trend_score,
            "momentum_score": profile.momentum_score,
            "volume_score": profile.volume_score,
            "volatility_score": profile.volatility_score,
        }

    # -------------------------------------------------------------------------
    # Internal Validation Methods
    # -------------------------------------------------------------------------

    def _validate_dataframe(self, df: pd.DataFrame, tf_str: str) -> None:
        """
        Validate dataframe readiness for profile generation.
        """
        if df is None or df.empty:
            raise InvalidProfileData(f"DataFrame for timeframe {tf_str} is empty or None.")

        required_cols = {"open", "high", "low", "close", "volume"}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise InvalidProfileData(f"DataFrame for timeframe {tf_str} is missing required columns: {missing_cols}")