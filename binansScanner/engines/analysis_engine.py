"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.analysis_engine
Version      : 3.0.0
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

import pandas as pd

from enums import Timeframe
from models.analysis import AnalysisResult
from models.market import MarketDataset, TimeframeData


logger = logging.getLogger(__name__)


class AnalysisEngine:
    """
    Canonical ORION analysis engine.

    The engine consumes market data after IndicatorEngine processing.

    It never adds analysis state to MarketDataset or TimeframeData.
    """

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
        """
        Initialize the AnalysisEngine.

        default_timeframe may be supplied as either:
            Timeframe.H1
        or:
            "1h"

        Timeframe is preferred by the canonical contract.
        """

        self.default_timeframe = self._normalize_timeframe(
            default_timeframe
        )

    # =========================================================================
    # Public API
    # =========================================================================

    def analyze(
        self,
        dataset: MarketDataset,
    ) -> AnalysisResult:
        """
        Analyze a canonical MarketDataset.

        The method does not mutate the dataset or its TimeframeData objects.
        """

        if not isinstance(dataset, MarketDataset):
            raise TypeError(
                "AnalysisEngine.analyze expects MarketDataset."
            )

        if not dataset.timeframes:
            return AnalysisResult(
                market_state="NEUTRAL",
                strength=0.0,
                warnings=["EMPTY_DATASET"],
            )

        timeframe_data, timeframe = (
            self._select_primary_timeframe(dataset)
        )

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
                warnings=[
                    "NO_VALID_TIMEFRAME_DATA",
                ],
            )

        signals: list[str] = []
        warnings: list[str] = []

        missing_indicators = self._missing_required_indicators(
            dataframe
        )

        if missing_indicators:
            logger.warning(
                "Missing required indicators for %s: %s",
                timeframe.value,
                missing_indicators,
            )

            warnings.append(
                "MISSING_REQUIRED_INDICATORS"
            )
            signals.append(
                "LOW_CONFIDENCE_DATA"
            )

        market_state = self._determine_market_state(
            dataframe,
            signals,
        )

        strength = self._calculate_market_strength(
            dataframe,
            signals,
        )

        return AnalysisResult(
            market_state=market_state,
            strength=round(
                strength,
                2,
            ),
            signals=signals,
            warnings=warnings,
        )

    # =========================================================================
    # Timeframe Selection
    # =========================================================================

    def _select_primary_timeframe(
        self,
        dataset: MarketDataset,
    ) -> tuple[
        Optional[TimeframeData],
        Optional[Timeframe],
    ]:
        """
        Select the primary timeframe using canonical Timeframe values.

        Selection order:
            1. Explicit default timeframe.
            2. Canonical preferred order.
            3. First available timeframe.
        """

        if self.default_timeframe is not None:
            selected = dataset.get_timeframe(
                self.default_timeframe
            )

            if selected is not None:
                return (
                    selected,
                    self.default_timeframe,
                )

        for timeframe in self.DEFAULT_TIMEFRAME_ORDER:
            selected = dataset.get_timeframe(
                timeframe
            )

            if selected is not None:
                return (
                    selected,
                    timeframe,
                )

        available = dataset.available_timeframes()

        if not available:
            return None, None

        first_timeframe = available[0]

        return (
            dataset.get_timeframe(
                first_timeframe
            ),
            first_timeframe,
        )

    @staticmethod
    def _normalize_timeframe(
        timeframe: Optional[Timeframe | str],
    ) -> Optional[Timeframe]:
        """Normalize a timeframe value to the canonical enum."""

        if timeframe is None:
            return None

        if isinstance(
            timeframe,
            Timeframe,
        ):
            return timeframe

        if isinstance(
            timeframe,
            str,
        ):
            for candidate in Timeframe:
                if candidate.value == timeframe:
                    return candidate

        raise ValueError(
            "Unsupported timeframe: "
            f"{timeframe!r}"
        )

    # =========================================================================
    # Indicator Contract
    # =========================================================================

    def _missing_required_indicators(
        self,
        dataframe: pd.DataFrame,
    ) -> list[str]:
        """Return required indicators missing from the DataFrame."""

        return [
            indicator
            for indicator in self.REQUIRED_INDICATORS
            if indicator not in dataframe.columns
        ]

    # =========================================================================
    # Market State
    # =========================================================================

    def _determine_market_state(
        self,
        dataframe: pd.DataFrame,
        signals: list[str],
    ) -> str:
        """
        Determine market state from canonical EMA alignment.

        Results:
            BULLISH
            BEARISH
            NEUTRAL
        """

        required_emas = (
            "ema_9",
            "ema_20",
            "ema_50",
        )

        if any(
            column not in dataframe.columns
            for column in required_emas
        ):
            signals.append(
                "EMA_DATA_UNAVAILABLE"
            )
            return "NEUTRAL"

        last_row = dataframe.iloc[-1]

        ema_9 = last_row["ema_9"]
        ema_20 = last_row["ema_20"]
        ema_50 = last_row["ema_50"]

        if any(
            pd.isna(value)
            for value in (
                ema_9,
                ema_20,
                ema_50,
            )
        ):
            signals.append(
                "EMA_DATA_UNAVAILABLE"
            )
            return "NEUTRAL"

        if ema_9 > ema_20 > ema_50:
            signals.append(
                "EMA_ALIGNMENT_BULLISH"
            )
            return "BULLISH"

        if ema_9 < ema_20 < ema_50:
            signals.append(
                "EMA_ALIGNMENT_BEARISH"
            )
            return "BEARISH"

        signals.append(
            "EMA_MIXED"
        )

        return "NEUTRAL"

    # =========================================================================
    # Market Strength
    # =========================================================================

    def _calculate_market_strength(
        self,
        dataframe: pd.DataFrame,
        signals: list[str],
    ) -> float:
        """
        Calculate analysis-level strength in the range 0..100.

        Components:
            RSI
            ADX
            Momentum

        This is an analysis result only.

        It is NOT the Score layer.
        """

        components: list[float] = []

        # ---------------------------------------------------------------------
        # RSI
        # ---------------------------------------------------------------------

        if "rsi_14" in dataframe.columns:
            rsi = dataframe["rsi_14"].iloc[-1]

            if not pd.isna(rsi):
                rsi = float(rsi)

                if rsi >= 70:
                    signals.append(
                        "RSI_OVERBOUGHT"
                    )
                elif rsi <= 30:
                    signals.append(
                        "RSI_OVERSOLD"
                    )

                rsi_strength = min(
                    abs(rsi - 50.0) * 2.0,
                    100.0,
                )

                components.append(
                    rsi_strength
                )

        # ---------------------------------------------------------------------
        # ADX
        # ---------------------------------------------------------------------

        if "adx_14" in dataframe.columns:
            adx = dataframe["adx_14"].iloc[-1]

            if not pd.isna(adx):
                adx = float(adx)

                if adx > 25.0:
                    signals.append(
                        "STRONG_TREND"
                    )
                else:
                    signals.append(
                        "WEAK_TREND"
                    )

                components.append(
                    min(
                        max(
                            adx,
                            0.0,
                        ),
                        100.0,
                    )
                )

        # ---------------------------------------------------------------------
        # Momentum
        # ---------------------------------------------------------------------

        if (
            "momentum_5" in dataframe.columns
            and "close" in dataframe.columns
        ):
            momentum = dataframe[
                "momentum_5"
            ].iloc[-1]

            close = dataframe[
                "close"
            ].iloc[-1]

            if (
                not pd.isna(momentum)
                and not pd.isna(close)
                and float(close) > 0.0
            ):
                relative_momentum = (
                    float(momentum)
                    / float(close)
                ) * 100.0

                if relative_momentum > 0:
                    signals.append(
                        "MOMENTUM_POSITIVE"
                    )
                elif relative_momentum < 0:
                    signals.append(
                        "MOMENTUM_NEGATIVE"
                    )

                momentum_strength = min(
                    abs(relative_momentum) * 20.0,
                    100.0,
                )

                components.append(
                    momentum_strength
                )

        if not components:
            return 50.0

        return min(
            max(
                sum(components)
                / len(components),
                0.0,
            ),
            100.0,
        )