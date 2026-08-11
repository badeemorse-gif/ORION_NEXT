"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.analysis_engine
Version      : 3.2.0
Status       : Canonical Analysis Contract
===============================================================================

Analysis layer.

Responsibilities:
    - consume canonical MarketDataset data;
    - consume canonical indicator columns;
    - derive market-state observations;
    - calculate analysis-level strength;
    - return AnalysisResult.

Explicit non-responsibilities:
    - no Binance/provider access;
    - no persistence;
    - no profile construction;
    - no score calculation;
    - no decision making;
    - no execution;
    - no reporting;
    - no mutation of MarketDataset domain state.

===============================================================================
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from enums import Timeframe
from models.analysis import AnalysisResult
from models.market import MarketDataset, TimeframeData


logger = logging.getLogger(__name__)


class AnalysisEngine:
    """Canonical ORION analysis engine."""

    REQUIRED_INDICATORS: tuple[str, ...] = (
        "ema_9",
        "ema_20",
        "ema_50",
        "rsi_14",
        "adx_14",
        "momentum_5",
    )

    DEFAULT_TIMEFRAME_ORDER: tuple[Timeframe, ...] = (
        Timeframe.H1,
        Timeframe.H4,
        Timeframe.M15,
        Timeframe.D1,
        Timeframe.M1,
        Timeframe.M5,
    )

    def __init__(
        self,
        default_timeframe: Optional[Timeframe | str] = None,
    ) -> None:
        self.default_timeframe = self._normalize_timeframe(default_timeframe)

    def analyze(self, dataset: MarketDataset) -> AnalysisResult:
        """Analyze a canonical MarketDataset without mutating it."""
        if not isinstance(dataset, MarketDataset):
            raise TypeError("AnalysisEngine.analyze expects MarketDataset.")

        if not dataset.timeframes:
            return AnalysisResult(
                market_state="NEUTRAL",
                strength=0.0,
                warnings=["EMPTY_DATASET"],
            )

        timeframe_data, timeframe = self._select_primary_timeframe(dataset)
        if timeframe_data is None or timeframe is None:
            return AnalysisResult(
                market_state="NEUTRAL",
                strength=0.0,
                warnings=["NO_VALID_TIMEFRAME_DATA"],
            )

        dataframe = timeframe_data.dataframe
        if dataframe is None or dataframe.empty:
            return AnalysisResult(
                market_state="NEUTRAL",
                strength=0.0,
                warnings=["NO_VALID_TIMEFRAME_DATA"],
            )

        signals: list[str] = []
        warnings: list[str] = []
        missing_indicators = self._missing_required_indicators(dataframe)

        if missing_indicators:
            logger.warning(
                "Missing required indicators for %s: %s",
                timeframe.value,
                missing_indicators,
            )
            warnings.append("MISSING_REQUIRED_INDICATORS")
            signals.append("LOW_CONFIDENCE_DATA")

            # Phase 2 intelligence boundary: incomplete indicator input is not
            # actionable intelligence. Preserve the diagnostic contract, but
            # fail closed so Score/Decision cannot turn partial data into a
            # directional trading signal.
            return AnalysisResult(
                market_state="NEUTRAL",
                strength=0.0,
                signals=signals,
                warnings=warnings,
            )

        invalid_indicators = self._invalid_required_indicators(dataframe)
        if invalid_indicators:
            logger.warning(
                "Invalid required indicators for %s: %s",
                timeframe.value,
                invalid_indicators,
            )
            warnings.append("INVALID_REQUIRED_INDICATORS")
            signals.append("LOW_CONFIDENCE_DATA")

            # NaN, Inf, and non-numeric required inputs are equally unsafe as
            # missing indicators. Never allow partial/invalid intelligence to
            # become directional output.
            return AnalysisResult(
                market_state="NEUTRAL",
                strength=0.0,
                signals=signals,
                warnings=warnings,
            )

        market_state = self._determine_market_state(dataframe, signals)
        strength = self._calculate_market_strength(dataframe, signals)

        return AnalysisResult(
            market_state=market_state,
            strength=round(strength, 2),
            signals=signals,
            warnings=warnings,
        )

    def _select_primary_timeframe(
        self,
        dataset: MarketDataset,
    ) -> tuple[Optional[TimeframeData], Optional[Timeframe]]:
        if self.default_timeframe is not None:
            selected = dataset.get_timeframe(self.default_timeframe)
            if selected is not None:
                return selected, self.default_timeframe

        for timeframe in self.DEFAULT_TIMEFRAME_ORDER:
            selected = dataset.get_timeframe(timeframe)
            if selected is not None:
                return selected, timeframe

        available = dataset.available_timeframes()
        if not available:
            return None, None

        first_timeframe = available[0]
        return dataset.get_timeframe(first_timeframe), first_timeframe

    @staticmethod
    def _normalize_timeframe(
        timeframe: Optional[Timeframe | str],
    ) -> Optional[Timeframe]:
        if timeframe is None:
            return None
        if isinstance(timeframe, Timeframe):
            return timeframe
        if isinstance(timeframe, str):
            for candidate in Timeframe:
                if candidate.value == timeframe:
                    return candidate
        raise ValueError(f"Unsupported timeframe: {timeframe!r}")

    def _missing_required_indicators(self, dataframe: pd.DataFrame) -> list[str]:
        return [
            indicator
            for indicator in self.REQUIRED_INDICATORS
            if indicator not in dataframe.columns
        ]

    def _invalid_required_indicators(self, dataframe: pd.DataFrame) -> list[str]:
        """Return required indicators whose latest value is not finite numeric data."""
        latest = dataframe.iloc[-1]
        invalid: list[str] = []

        for indicator in self.REQUIRED_INDICATORS:
            value = latest[indicator]
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                invalid.append(indicator)
                continue

            if not np.isfinite(numeric_value):
                invalid.append(indicator)

        return invalid

    def _determine_market_state(
        self,
        dataframe: pd.DataFrame,
        signals: list[str],
    ) -> str:
        required_emas = ("ema_9", "ema_20", "ema_50")
        if any(column not in dataframe.columns for column in required_emas):
            signals.append("EMA_DATA_UNAVAILABLE")
            return "NEUTRAL"

        last_row = dataframe.iloc[-1]
        ema_9, ema_20, ema_50 = (
            last_row["ema_9"],
            last_row["ema_20"],
            last_row["ema_50"],
        )
        if any(pd.isna(value) for value in (ema_9, ema_20, ema_50)):
            signals.append("EMA_DATA_UNAVAILABLE")
            return "NEUTRAL"

        if ema_9 > ema_20 > ema_50:
            signals.append("EMA_ALIGNMENT_BULLISH")
            return "BULLISH"
        if ema_9 < ema_20 < ema_50:
            signals.append("EMA_ALIGNMENT_BEARISH")
            return "BEARISH"

        signals.append("EMA_MIXED")
        return "NEUTRAL"

    def _calculate_market_strength(
        self,
        dataframe: pd.DataFrame,
        signals: list[str],
    ) -> float:
        components: list[float] = []

        if "rsi_14" in dataframe.columns:
            rsi = dataframe["rsi_14"].iloc[-1]
            if not pd.isna(rsi):
                rsi = float(rsi)
                if rsi >= 70:
                    signals.append("RSI_OVERBOUGHT")
                elif rsi <= 30:
                    signals.append("RSI_OVERSOLD")
                components.append(min(abs(rsi - 50.0) * 2.0, 100.0))

        if "adx_14" in dataframe.columns:
            adx = dataframe["adx_14"].iloc[-1]
            if not pd.isna(adx):
                adx = float(adx)
                signals.append("STRONG_TREND" if adx > 25.0 else "WEAK_TREND")
                components.append(min(max(adx, 0.0), 100.0))

        if "momentum_5" in dataframe.columns and "close" in dataframe.columns:
            momentum = dataframe["momentum_5"].iloc[-1]
            close = dataframe["close"].iloc[-1]
            if not pd.isna(momentum) and not pd.isna(close) and float(close) > 0.0:
                relative_momentum = (float(momentum) / float(close)) * 100.0
                if relative_momentum > 0:
                    signals.append("MOMENTUM_POSITIVE")
                elif relative_momentum < 0:
                    signals.append("MOMENTUM_NEGATIVE")
                components.append(min(abs(relative_momentum) * 20.0, 100.0))

        if not components:
            return 50.0

        return min(max(sum(components) / len(components), 0.0), 100.0)


__all__ = ["AnalysisEngine"]
