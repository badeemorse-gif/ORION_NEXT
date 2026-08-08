"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.profile_builder
Version      : 1.0.0
Status       : ORION Production Profile Builder Component
===============================================================================

Standalone profile builder component responsible for raw feature extraction,
technical calculations reading, scoring, and market profile classification.
===============================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


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


@dataclass(slots=True)
class MarketProfile:
    """
    Immutable dataclass representing objective market characteristics, raw scores,
    and metrics.
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
    ema_alignment: bool = False
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


class ProfileBuilder:
    """
    Encapsulates all feature extraction, scoring, and classification logic
    separating profile building from engine orchestration.
    """

    def build(self, df: pd.DataFrame) -> MarketProfile:
        """
        Builds a MarketProfile from a single dataframe.
        """
        if df is None or df.empty:
            return MarketProfile()

        latest = df.iloc[-1]

        # 1. Feature Extraction (Raw Numerical/Logical Metrics)
        trend_features = self._detect_trend(df, latest)
        trend_strength_features = self._detect_trend_strength(df, latest)
        volatility_features = self._detect_volatility(df, latest)
        momentum_features = self._detect_momentum(df, latest)
        volume_features = self._detect_volume_strength(df, latest)
        support, resistance = self._detect_support_resistance(df, latest)
        price_location_features = self._detect_price_location(df, latest, support, resistance)
        risk_features = self._detect_risk(df, latest, volatility_features)

        # 2. Classification Layer (Pure Objectivity mapping to Enum values)
        trend = self._classify_trend(trend_features)
        trend_strength = self._classify_trend_strength(trend_strength_features)
        volatility, volatility_level, volatility_score = self._classify_volatility(volatility_features)
        momentum, momentum_score = self._classify_momentum(momentum_features)
        volume_strength, volume_score = self._classify_volume(volume_features)
        market_phase = self._classify_phase(trend_features, trend)
        risk_level = self._classify_risk(risk_features)
        price_location = self._classify_price_location(price_location_features)

        trend_score = trend_features["trend_score"]
        confidence = self._calculate_confidence(
            trend_score=trend_score,
            momentum_score=momentum_score,
            volume_score=volume_score,
            volatility_score=volatility_score,
            agreement=trend_features["agreement"],
        )

        liquidity = float(latest.get("volume", 0.0) * latest.get("close", 0.0))
        ema_alignment = bool(latest.get("ema_20", 0) > latest.get("ema_50", 0) > latest.get("ema_200", 0))

        return MarketProfile(
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
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None,
            distance_to_support=price_location_features["distance_to_support"],
            distance_to_resistance=price_location_features["distance_to_resistance"],
            distance_to_ema200=price_location_features["distance_to_ema200"],
            trend_score=trend_score,
            momentum_score=momentum_score,
            volume_score=volume_score,
            volatility_score=volatility_score,
        )

    # -------------------------------------------------------------------------
    # Feature Extraction
    # -------------------------------------------------------------------------

    def _detect_trend(self, df: pd.DataFrame, latest: pd.Series) -> dict[str, Any]:
        close = float(latest.get("close", 0.0))
        ema_20 = float(latest.get("ema_20", close))
        ema_50 = float(latest.get("ema_50", close))
        ema_100 = float(latest.get("ema_100", close))
        ema_200 = float(latest.get("ema_200", close))

        ema_20_prev = float(df["ema_20"].iloc[-5]) if len(df) >= 5 else ema_20
        slope_20 = (ema_20 - ema_20_prev) / 5.0

        bullish_alignment = (close > ema_20 > ema_50 > ema_100 > ema_200) and (slope_20 > 0)
        bearish_alignment = (close < ema_20 < ema_50 < ema_100 < ema_200) and (slope_20 < 0)

        adx = float(latest.get("adx_14", 20.0))
        trend_score = 75.0 if bullish_alignment or bearish_alignment else 40.0

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
            "agreement": 1.0 if bullish_alignment or bearish_alignment else 0.5,
        }

    def _detect_trend_strength(self, df: pd.DataFrame, latest: pd.Series) -> dict[str, Any]:
        adx = float(latest.get("adx_14", 20.0))
        close = float(latest.get("close", 1.0))
        ema_20 = float(latest.get("ema_20", close))
        ema_50 = float(latest.get("ema_50", close))
        spacing = abs(ema_20 - ema_50) / close * 100.0
        slope = float(latest.get("ema_20", close)) - float(df["ema_20"].iloc[-3]) if len(df) >= 3 else 0.0

        return {
            "adx": adx,
            "spacing": spacing,
            "slope": slope,
        }

    def _detect_volatility(self, df: pd.DataFrame, latest: pd.Series) -> dict[str, Any]:
        atr = float(latest.get("atr_14", 0.0))
        close = float(latest.get("close", 1.0))
        atr_pct = (atr / close) * 100.0 if close > 0 else 0.0
        bb_width = float(latest.get("bb_bandwidth", 1.0))
        kc_width = float((latest.get("kc_upper", close) - latest.get("kc_lower", close)) / close * 100.0)

        volatility_score = min(max(atr_pct * 25.0, 0.0), 100.0)

        return {
            "atr": atr,
            "atr_pct": atr_pct,
            "bb_width": bb_width,
            "kc_width": kc_width,
            "volatility_score": volatility_score,
        }

    def _detect_momentum(self, df: pd.DataFrame, latest: pd.Series) -> dict[str, Any]:
        rsi = float(latest.get("rsi_14", 50.0))
        macd = float(latest.get("macd", 0.0))
        macd_signal = float(latest.get("macd_signal", 0.0))
        roc = float(latest.get("roc_10", 0.0))
        mom = float(latest.get("momentum_10", 0.0))

        momentum_score = min(max((rsi / 100.0) * 100.0, 0.0), 100.0)

        return {
            "rsi": rsi,
            "macd": macd,
            "macd_signal": macd_signal,
            "roc": roc,
            "mom": mom,
            "momentum_score": momentum_score,
        }

    def _detect_volume_strength(self, df: pd.DataFrame, latest: pd.Series) -> dict[str, Any]:
        mfi = float(latest.get("mfi_14", 50.0))
        cmf = float(latest.get("cmf_20", 0.0))
        obv = float(latest.get("obv", 0.0))
        volume_score = min(max(mfi, 0.0), 100.0)

        return {
            "mfi": mfi,
            "cmf": cmf,
            "obv": obv,
            "volume_score": volume_score,
        }

    def _detect_support_resistance(self, df: pd.DataFrame, latest: pd.Series) -> tuple[float, float]:
        lows = df["low"].tail(20)
        highs = df["high"].tail(20)

        swing_low = float(lows.min()) if not lows.empty else float(latest.get("low", 0.0))
        swing_high = float(highs.max()) if not highs.empty else float(latest.get("high", 0.0))

        dc_lower = float(latest.get("dc_lower", swing_low))
        dc_upper = float(latest.get("dc_upper", swing_high))

        support = min(swing_low, dc_lower)
        resistance = max(swing_high, dc_upper)

        return support, resistance

    def _detect_price_location(self, df: pd.DataFrame, latest: pd.Series, support: float, resistance: float) -> dict[str, Any]:
        close = float(latest.get("close", 0.0))
        ema_200 = float(latest.get("ema_200", close))

        dist_support = (close - support) / close * 100.0 if close > 0 else 0.0
        dist_resistance = (resistance - close) / close * 100.0 if close > 0 else 0.0
        dist_ema200 = (close - ema_200) / close * 100.0 if close > 0 else 0.0

        return {
            "distance_to_support": dist_support,
            "distance_to_resistance": dist_resistance,
            "distance_to_ema200": dist_ema200,
            "close": close,
            "support": support,
            "resistance": resistance,
        }

    def _detect_risk(self, df: pd.DataFrame, latest: pd.Series, volatility_features: dict[str, Any]) -> dict[str, Any]:
        atr_pct = volatility_features["atr_pct"]
        rsi = float(latest.get("rsi_14", 50.0))
        momentum_conflict = rsi > 80 or rsi < 20
        close = float(latest.get("close", 0.0))
        ema_20 = float(latest.get("ema_20", close))
        ema_50 = float(latest.get("ema_50", close))
        trend_conflict = abs(ema_20 - ema_50) / close > 0.05

        return {
            "atr_pct": atr_pct,
            "momentum_conflict": momentum_conflict,
            "trend_conflict": trend_conflict,
        }

    # -------------------------------------------------------------------------
    # Classification Layer
    # -------------------------------------------------------------------------

    def _classify_trend(self, features: dict[str, Any]) -> str:
        if features["bullish_alignment"]:
            return TrendType.BULLISH.value
        elif features["bearish_alignment"]:
            return TrendType.BEARISH.value
        return TrendType.SIDEWAYS.value

    def _classify_trend_strength(self, features: dict[str, Any]) -> str:
        adx = features["adx"]
        spacing = features["spacing"]
        if adx > 40 and spacing > 2.0:
            return TrendStrengthType.VERY_STRONG.value
        elif adx > 25 and spacing > 1.0:
            return TrendStrengthType.STRONG.value
        elif adx > 15:
            return TrendStrengthType.MEDIUM.value
        return TrendStrengthType.WEAK.value

    def _classify_phase(self, trend_features: dict[str, Any], trend: str) -> str:
        adx = trend_features["adx"]
        if trend == TrendType.BULLISH.value:
            return MarketPhaseType.MARKUP.value if adx > 25 else MarketPhaseType.ACCUMULATION.value
        elif trend == TrendType.BEARISH.value:
            return MarketPhaseType.MARKDOWN.value if adx > 25 else MarketPhaseType.DISTRIBUTION.value
        return MarketPhaseType.RANGE.value

    def _classify_volatility(self, features: dict[str, Any]) -> tuple[float, str, float]:
        atr = features["atr"]
        atr_pct = features["atr_pct"]
        vol_score = features["volatility_score"]

        if atr_pct > 3.0:
            level = VolatilityLevelType.EXTREME.value
        elif atr_pct > 1.5:
            level = VolatilityLevelType.HIGH.value
        elif atr_pct > 0.5:
            level = VolatilityLevelType.NORMAL.value
        else:
            level = VolatilityLevelType.LOW.value

        return atr, level, vol_score

    def _classify_momentum(self, features: dict[str, Any]) -> tuple[str, float]:
        rsi = features["rsi"]
        macd = features["macd"]
        macd_signal = features["macd_signal"]
        score = features["momentum_score"]

        if rsi > 70 and macd > macd_signal:
            return MomentumState.STRONG_BUY.value, score
        elif rsi > 55 and macd >= macd_signal:
            return MomentumState.BUY.value, score
        elif rsi < 30 and macd < macd_signal:
            return MomentumState.STRONG_SELL.value, score
        elif rsi < 45 and macd <= macd_signal:
            return MomentumState.SELL.value, score
        return MomentumState.NEUTRAL.value, score

    def _classify_volume(self, features: dict[str, Any]) -> tuple[str, float]:
        mfi = features["mfi"]
        score = features["volume_score"]
        if mfi > 70 or mfi < 30:
            return VolumeStrength.STRONG.value, score
        elif mfi > 50:
            return VolumeStrength.NORMAL.value, score
        return VolumeStrength.WEAK.value, score

    def _classify_risk(self, features: dict[str, Any]) -> str:
        atr_pct = features["atr_pct"]
        if atr_pct > 3.0 or features["momentum_conflict"]:
            return RiskLevel.EXTREME.value
        elif atr_pct > 1.5 or features["trend_conflict"]:
            return RiskLevel.HIGH.value
        elif atr_pct < 0.5:
            return RiskLevel.LOW.value
        return RiskLevel.MEDIUM.value

    def _classify_price_location(self, features: dict[str, Any]) -> str:
        resistance = features["resistance"]
        support = features["support"]
        close = features["close"]
        if resistance > support:
            pos = (close - support) / (resistance - support)
            if pos > 0.8:
                return "Near Resistance"
            elif pos < 0.2:
                return "Near Support"
        return "Middle"

    def _calculate_confidence(
        self,
        trend_score: float,
        momentum_score: float,
        volume_score: float,
        volatility_score: float,
        agreement: float,
    ) -> float:
        conf = (
            (trend_score * 0.30) +
            (momentum_score * 0.25) +
            (volume_score * 0.20) +
            ((100.0 - volatility_score) * 0.15) +
            (agreement * 100.0 * 0.10)
        )
        return float(np.clip(conf, 0.0, 100.0))