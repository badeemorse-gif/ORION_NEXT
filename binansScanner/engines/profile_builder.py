"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.profile_builder
Version      : 2.0.0
Status       : Canonical Profile Builder

Responsibility
--------------
Build objective market characteristics from one canonical market DataFrame.

Boundary
--------
MarketDataset / DataFrame
        |
        v
ProfileBuilder
        |
        v
MarketCharacteristics

ProfileBuilder does not:
- own ProfileResult
- mutate MarketDataset
- orchestrate other engines
- persist data
- make trading decisions

The canonical domain contracts live in models.profile.
===============================================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd

from models.indicators import IndicatorResult
from models.profile import (
    EMAAlignment,
    MarketCharacteristics,
    MarketPhaseType,
    MomentumState,
    RiskLevel,
    TrendStrengthType,
    TrendType,
    VolatilityLevelType,
    VolumeStrength,
)

logger = logging.getLogger(__name__)

CRITICAL_PROFILE_INDICATORS: tuple[str, ...] = (
    "ema_9", "ema_20", "ema_50", "ema_100", "ema_200",
    "adx_14", "rsi_14", "momentum_5", "momentum_10",
    "mfi_14", "atr_14",
)

# -----------------------------------------------------------------------------
# Compatibility export
# -----------------------------------------------------------------------------
#
# Existing consumers that still import MarketProfile from this module should
# receive the canonical domain model instead of a second local definition.
#
# New code must import MarketCharacteristics from models.profile directly.
#
MarketProfile = MarketCharacteristics


class ProfileBuilder:
    """
    Build canonical MarketCharacteristics from a single market DataFrame.

    All feature extraction and classification logic remains here.
    The domain result itself is owned by models.profile.
    """

    def build(self, df: pd.DataFrame) -> MarketCharacteristics:
        """
        Build a MarketCharacteristics instance from one canonical DataFrame.

        Empty or missing input is safe and returns the canonical default
        MarketCharacteristics object.
        """

        if df is None or df.empty:
            return MarketCharacteristics()

        self._validate_intelligence_input(df)
        latest = df.iloc[-1]

        # ------------------------------------------------------------------
        # 1. Feature extraction
        # ------------------------------------------------------------------

        trend_features = self._detect_trend(df, latest)
        trend_strength_features = self._detect_trend_strength(df, latest)
        volatility_features = self._detect_volatility(df, latest)
        momentum_features = self._detect_momentum(df, latest)
        volume_features = self._detect_volume_strength(df, latest)

        support, resistance = self._detect_support_resistance(
            df,
            latest,
        )

        price_location_features = self._detect_price_location(
            df,
            latest,
            support,
            resistance,
        )

        risk_features = self._detect_risk(
            df,
            latest,
            volatility_features,
        )

        # ------------------------------------------------------------------
        # 2. Classification
        # ------------------------------------------------------------------

        trend = self._classify_trend(trend_features)

        trend_strength = self._classify_trend_strength(
            trend_strength_features,
        )

        volatility, volatility_level, volatility_score = (
            self._classify_volatility(
                volatility_features,
            )
        )

        momentum, momentum_score = self._classify_momentum(
            momentum_features,
        )

        volume_strength, volume_score = self._classify_volume(
            volume_features,
        )

        market_phase = self._classify_phase(
            trend_features,
            trend,
        )

        risk_level = self._classify_risk(
            risk_features,
        )

        price_location = self._classify_price_location(
            price_location_features,
        )

        # ------------------------------------------------------------------
        # 3. Composite confidence
        # ------------------------------------------------------------------

        trend_score = trend_features["trend_score"]

        confidence = self._calculate_confidence(
            trend_score=trend_score,
            momentum_score=momentum_score,
            volume_score=volume_score,
            volatility_score=volatility_score,
            agreement=trend_features["agreement"],
        )

        # ------------------------------------------------------------------
        # 4. Derived objective metrics
        # ------------------------------------------------------------------

        close = float(latest.get("close", 0.0))
        volume = float(latest.get("volume", 0.0))

        liquidity = float(volume * close)

        ema_alignment = self._classify_ema_alignment(
            latest,
        )

        timestamp: Optional[datetime] = None

        if isinstance(df.index, pd.DatetimeIndex) and len(df.index) > 0:
            timestamp = df.index[-1].to_pydatetime()

        # ------------------------------------------------------------------
        # 5. Canonical result
        # ------------------------------------------------------------------

        return MarketCharacteristics(
            trend=trend,
            trend_strength=trend_strength,
            volatility=volatility,
            volatility_level=volatility_level,
            momentum=momentum,
            volume_strength=volume_strength,
            liquidity=liquidity,
            price_location=price_location,
            support=support,
            resistance=resistance,
            ema_alignment=ema_alignment,
            market_phase=market_phase,
            risk_level=risk_level,
            confidence=confidence,
            timestamp=timestamp,
            distance_to_support=price_location_features[
                "distance_to_support"
            ],
            distance_to_resistance=price_location_features[
                "distance_to_resistance"
            ],
            distance_to_ema200=price_location_features[
                "distance_to_ema200"
            ],
            trend_score=trend_score,
            momentum_score=momentum_score,
            volume_score=volume_score,
            volatility_score=volatility_score,
        )

    def _validate_intelligence_input(self, df: pd.DataFrame) -> None:
        """Reject incomplete indicator intelligence before classification."""
        missing = [
            name
            for name in CRITICAL_PROFILE_INDICATORS
            if name not in df.columns
        ]
        if missing:
            raise ValueError(
                "Profile intelligence blocked: missing critical indicators: "
                + ", ".join(missing)
            )

        metadata = df.attrs.get("indicator_result")
        if metadata is not None:
            if not isinstance(metadata, IndicatorResult):
                raise ValueError(
                    "Profile intelligence blocked: invalid indicator metadata."
                )
            if metadata.quality != "SUFFICIENT" or metadata.failed_indicators:
                raise ValueError(
                    "Profile intelligence blocked: indicator metadata reports "
                    "failed or insufficient indicators."
                )

        latest = df.iloc[-1]
        invalid = [
            name
            for name in CRITICAL_PROFILE_INDICATORS
            if not np.isfinite(float(latest[name]))
        ]
        if invalid:
            raise ValueError(
                "Profile intelligence blocked: invalid critical indicators: "
                + ", ".join(invalid)
            )

        if len(df) >= 5 and not np.isfinite(
            df["ema_20"].tail(5).astype(float).to_numpy()
        ).all():
            raise ValueError(
                "Profile intelligence blocked: invalid ema_20 slope history."
            )

    # =========================================================================
    # Feature Extraction
    # =========================================================================

    def _detect_trend(
        self,
        df: pd.DataFrame,
        latest: pd.Series,
    ) -> dict[str, Any]:

        close = float(latest.get("close", 0.0))

        ema_20 = float(
            latest.get("ema_20", close)
        )

        ema_50 = float(
            latest.get("ema_50", close)
        )

        ema_100 = float(
            latest.get("ema_100", close)
        )

        ema_200 = float(
            latest.get("ema_200", close)
        )

        if "ema_20" in df.columns and len(df) >= 5:
            ema_20_prev = float(
                df["ema_20"].iloc[-5]
            )
        else:
            ema_20_prev = ema_20

        slope_20 = (
            ema_20 - ema_20_prev
        ) / 5.0

        bullish_alignment = (
            close
            > ema_20
            > ema_50
            > ema_100
            > ema_200
        ) and slope_20 > 0

        bearish_alignment = (
            close
            < ema_20
            < ema_50
            < ema_100
            < ema_200
        ) and slope_20 < 0

        adx = float(
            latest.get("adx_14", 20.0)
        )

        trend_score = (
            75.0
            if bullish_alignment or bearish_alignment
            else 40.0
        )

        return {
            "close": close,
            "ema_20": ema_20,
            "ema_50": ema_50,
            "ema_200": ema_200,
            "slope_20": slope_20,
            "bullish_alignment": bullish_alignment,
            "bearish_alignment": bearish_alignment,
            "adx": adx,
            "trend_score": trend_score,
            "agreement": (
                1.0
                if bullish_alignment or bearish_alignment
                else 0.5
            ),
        }

    def _detect_trend_strength(
        self,
        df: pd.DataFrame,
        latest: pd.Series,
    ) -> dict[str, Any]:

        adx = float(
            latest.get("adx_14", 20.0)
        )

        close = float(
            latest.get("close", 1.0)
        )

        ema_20 = float(
            latest.get("ema_20", close)
        )

        ema_50 = float(
            latest.get("ema_50", close)
        )

        if close > 0:
            spacing = (
                abs(ema_20 - ema_50)
                / close
                * 100.0
            )
        else:
            spacing = 0.0

        if "ema_20" in df.columns and len(df) >= 3:
            slope = (
                float(df["ema_20"].iloc[-1])
                - float(df["ema_20"].iloc[-3])
            )
        else:
            slope = 0.0

        return {
            "adx": adx,
            "spacing": spacing,
            "slope": slope,
        }

    def _detect_volatility(
        self,
        df: pd.DataFrame,
        latest: pd.Series,
    ) -> dict[str, Any]:

        atr = float(
            latest.get("atr_14", 0.0)
        )

        close = float(
            latest.get("close", 1.0)
        )

        atr_pct = (
            (atr / close) * 100.0
            if close > 0
            else 0.0
        )

        bb_width = float(
            latest.get("bb_bandwidth", 1.0)
        )

        kc_upper = float(
            latest.get("kc_upper", close)
        )

        kc_lower = float(
            latest.get("kc_lower", close)
        )

        kc_width = (
            (kc_upper - kc_lower)
            / close
            * 100.0
            if close > 0
            else 0.0
        )

        volatility_score = float(
            np.clip(
                atr_pct * 25.0,
                0.0,
                100.0,
            )
        )

        return {
            "atr": atr,
            "atr_pct": atr_pct,
            "bb_width": bb_width,
            "kc_width": kc_width,
            "volatility_score": volatility_score,
        }

    def _detect_momentum(
        self,
        df: pd.DataFrame,
        latest: pd.Series,
    ) -> dict[str, Any]:

        rsi = float(
            latest.get("rsi_14", 50.0)
        )

        macd = float(
            latest.get("macd", 0.0)
        )

        macd_signal = float(
            latest.get("macd_signal", 0.0)
        )

        roc = float(
            latest.get("roc_10", 0.0)
        )

        mom = float(
            latest.get("momentum_10", 0.0)
        )

        momentum_score = float(
            np.clip(
                rsi,
                0.0,
                100.0,
            )
        )

        return {
            "rsi": rsi,
            "macd": macd,
            "macd_signal": macd_signal,
            "roc": roc,
            "mom": mom,
            "momentum_score": momentum_score,
        }

    def _detect_volume_strength(
        self,
        df: pd.DataFrame,
        latest: pd.Series,
    ) -> dict[str, Any]:

        mfi = float(
            latest.get("mfi_14", 50.0)
        )

        cmf = float(
            latest.get("cmf_20", 0.0)
        )

        obv = float(
            latest.get("obv", 0.0)
        )

        volume_score = float(
            np.clip(
                mfi,
                0.0,
                100.0,
            )
        )

        return {
            "mfi": mfi,
            "cmf": cmf,
            "obv": obv,
            "volume_score": volume_score,
        }

    def _detect_support_resistance(
        self,
        df: pd.DataFrame,
        latest: pd.Series,
    ) -> tuple[float, float]:

        if "low" in df.columns:
            lows = df["low"].tail(20)
        else:
            lows = pd.Series(dtype=float)

        if "high" in df.columns:
            highs = df["high"].tail(20)
        else:
            highs = pd.Series(dtype=float)

        swing_low = (
            float(lows.min())
            if not lows.empty
            else float(latest.get("low", 0.0))
        )

        swing_high = (
            float(highs.max())
            if not highs.empty
            else float(latest.get("high", 0.0))
        )

        dc_lower = float(
            latest.get("dc_lower", swing_low)
        )

        dc_upper = float(
            latest.get("dc_upper", swing_high)
        )

        support = min(
            swing_low,
            dc_lower,
        )

        resistance = max(
            swing_high,
            dc_upper,
        )

        return support, resistance

    def _detect_price_location(
        self,
        df: pd.DataFrame,
        latest: pd.Series,
        support: float,
        resistance: float,
    ) -> dict[str, Any]:

        close = float(
            latest.get("close", 0.0)
        )

        ema_200 = float(
            latest.get("ema_200", close)
        )

        if close > 0:
            distance_to_support = (
                (close - support)
                / close
                * 100.0
            )

            distance_to_resistance = (
                (resistance - close)
                / close
                * 100.0
            )

            distance_to_ema200 = (
                (close - ema_200)
                / close
                * 100.0
            )
        else:
            distance_to_support = 0.0
            distance_to_resistance = 0.0
            distance_to_ema200 = 0.0

        return {
            "distance_to_support": distance_to_support,
            "distance_to_resistance": distance_to_resistance,
            "distance_to_ema200": distance_to_ema200,
            "close": close,
            "support": support,
            "resistance": resistance,
        }

    def _detect_risk(
        self,
        df: pd.DataFrame,
        latest: pd.Series,
        volatility_features: dict[str, Any],
    ) -> dict[str, Any]:

        atr_pct = volatility_features["atr_pct"]

        rsi = float(
            latest.get("rsi_14", 50.0)
        )

        momentum_conflict = (
            rsi > 80
            or rsi < 20
        )

        close = float(
            latest.get("close", 0.0)
        )

        ema_20 = float(
            latest.get("ema_20", close)
        )

        ema_50 = float(
            latest.get("ema_50", close)
        )

        trend_conflict = (
            abs(ema_20 - ema_50)
            / close > 0.05
            if close > 0
            else False
        )

        return {
            "atr_pct": atr_pct,
            "momentum_conflict": momentum_conflict,
            "trend_conflict": trend_conflict,
        }

    # =========================================================================
    # Classification
    # =========================================================================

    def _classify_trend(
        self,
        features: dict[str, Any],
    ) -> str:

        if features["bullish_alignment"]:
            return TrendType.BULLISH.value

        if features["bearish_alignment"]:
            return TrendType.BEARISH.value

        return TrendType.SIDEWAYS.value

    def _classify_trend_strength(
        self,
        features: dict[str, Any],
    ) -> str:

        adx = features["adx"]
        spacing = features["spacing"]

        if adx > 40 and spacing > 2.0:
            return TrendStrengthType.VERY_STRONG.value

        if adx > 25 and spacing > 1.0:
            return TrendStrengthType.STRONG.value

        if adx > 15:
            return TrendStrengthType.MEDIUM.value

        return TrendStrengthType.WEAK.value

    def _classify_phase(
        self,
        trend_features: dict[str, Any],
        trend: str,
    ) -> str:

        adx = trend_features["adx"]

        if trend == TrendType.BULLISH.value:
            if adx > 25:
                return MarketPhaseType.MARKUP.value

            return MarketPhaseType.ACCUMULATION.value

        if trend == TrendType.BEARISH.value:
            if adx > 25:
                return MarketPhaseType.MARKDOWN.value

            return MarketPhaseType.DISTRIBUTION.value

        return MarketPhaseType.RANGE.value

    def _classify_volatility(
        self,
        features: dict[str, Any],
    ) -> tuple[float, str, float]:

        atr = features["atr"]
        atr_pct = features["atr_pct"]
        volatility_score = features["volatility_score"]

        if atr_pct > 3.0:
            level = VolatilityLevelType.EXTREME.value

        elif atr_pct > 1.5:
            level = VolatilityLevelType.HIGH.value

        elif atr_pct > 0.5:
            level = VolatilityLevelType.NORMAL.value

        else:
            level = VolatilityLevelType.LOW.value

        return (
            atr,
            level,
            volatility_score,
        )

    def _classify_momentum(
        self,
        features: dict[str, Any],
    ) -> tuple[str, float]:

        rsi = features["rsi"]
        macd = features["macd"]
        macd_signal = features["macd_signal"]
        score = features["momentum_score"]

        if rsi > 70 and macd > macd_signal:
            return (
                MomentumState.STRONG_BUY.value,
                score,
            )

        if rsi > 55 and macd >= macd_signal:
            return (
                MomentumState.BUY.value,
                score,
            )

        if rsi < 30 and macd < macd_signal:
            return (
                MomentumState.STRONG_SELL.value,
                score,
            )

        if rsi < 45 and macd <= macd_signal:
            return (
                MomentumState.SELL.value,
                score,
            )

        return (
            MomentumState.NEUTRAL.value,
            score,
        )

    def _classify_volume(
        self,
        features: dict[str, Any],
    ) -> tuple[str, float]:

        mfi = features["mfi"]
        score = features["volume_score"]

        if mfi > 70 or mfi < 30:
            return (
                VolumeStrength.STRONG.value,
                score,
            )

        if mfi > 50:
            return (
                VolumeStrength.NORMAL.value,
                score,
            )

        return (
            VolumeStrength.WEAK.value,
            score,
        )

    def _classify_risk(
        self,
        features: dict[str, Any],
    ) -> str:

        atr_pct = features["atr_pct"]

        if (
            atr_pct > 3.0
            or features["momentum_conflict"]
        ):
            return RiskLevel.EXTREME.value

        if (
            atr_pct > 1.5
            or features["trend_conflict"]
        ):
            return RiskLevel.HIGH.value

        if atr_pct < 0.5:
            return RiskLevel.LOW.value

        return RiskLevel.MEDIUM.value

    def _classify_price_location(
        self,
        features: dict[str, Any],
    ) -> str:

        resistance = features["resistance"]
        support = features["support"]
        close = features["close"]

        if resistance > support:
            position = (
                (close - support)
                / (resistance - support)
            )

            if position > 0.8:
                return "Near Resistance"

            if position < 0.2:
                return "Near Support"

        return "Middle"

    def _classify_ema_alignment(
        self,
        latest: pd.Series,
    ) -> str:

        close = float(
            latest.get("close", 0.0)
        )

        ema_20 = float(
            latest.get("ema_20", close)
        )

        ema_50 = float(
            latest.get("ema_50", close)
        )

        ema_200 = float(
            latest.get("ema_200", close)
        )

        bullish = (
            close > ema_20 > ema_50 > ema_200
        )

        bearish = (
            close < ema_20 < ema_50 < ema_200
        )

        if bullish:
            return EMAAlignment.BULLISH.value

        if bearish:
            return EMAAlignment.BEARISH.value

        return EMAAlignment.NONE.value

    # =========================================================================
    # Confidence
    # =========================================================================

    def _calculate_confidence(
        self,
        trend_score: float,
        momentum_score: float,
        volume_score: float,
        volatility_score: float,
        agreement: float,
    ) -> float:

        confidence = (
            (trend_score * 0.30)
            + (momentum_score * 0.25)
            + (volume_score * 0.20)
            + ((100.0 - volatility_score) * 0.15)
            + (agreement * 100.0 * 0.10)
        )

        return float(
            np.clip(
                confidence,
                0.0,
                100.0,
            )
        )


__all__ = [
    "EMAAlignment",
    "MarketCharacteristics",
    "MarketPhaseType",
    "MarketProfile",
    "MomentumState",
    "ProfileBuilder",
    "RiskLevel",
    "TrendStrengthType",
    "TrendType",
    "VolatilityLevelType",
    "VolumeStrength",
]