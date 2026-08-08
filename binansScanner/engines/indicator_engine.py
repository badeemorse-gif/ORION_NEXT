"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.indicator_engine
Version      : 3.0.0
Status       : ORION Canonical Indicator Coordinator
===============================================================================

Coordinates indicator calculation without introducing analytical state into
the Market domain models.

===============================================================================
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
import pandas as pd

from enums import Timeframe
from models.market import MarketDataset, TimeframeData
from engines.indicator_calculator import IndicatorCalculator


base_logger = logging.getLogger(__name__)


AVAILABLE_INDICATORS: tuple[str, ...] = (
    "EMA_9",
    "EMA_20",
    "EMA_50",
    "EMA_100",
    "EMA_200",
    "SMA_20",
    "SMA_50",
    "ADX",
    "SuperTrend",
    "Ichimoku",
    "RSI",
    "MACD",
    "Stochastic",
    "CCI",
    "Williams_R",
    "ROC",
    "Momentum_5",
    "Momentum_10",
    "OBV",
    "CMF",
    "VWAP",
    "MFI",
    "ATR",
    "Bollinger_Bands",
    "Keltner_Channel",
    "Donchian_Channel",
    "Typical_Price",
    "Median_Price",
    "HL2",
    "HLC3",
    "OHLC4",
)


class IndicatorEngineError(Exception):
    """Base exception for indicator-engine failures."""


class InvalidIndicatorData(IndicatorEngineError):
    """Raised when indicator input data is invalid."""


class IndicatorEngine:
    """
    Canonical indicator coordinator.

    Important architectural rule:

        IndicatorEngine may transform DataFrames,
        but it must not add runtime state to TimeframeData.

    The Market domain remains a pure market-data contract.
    """

    def __init__(
        self,
        calculator: Optional[IndicatorCalculator] = None,
    ) -> None:
        self._calculator = (
            calculator
            if calculator is not None
            else IndicatorCalculator()
        )

    # =========================================================================
    # Public API
    # =========================================================================

    def calculate_dataset(
        self,
        dataset: MarketDataset,
    ) -> MarketDataset:
        """
        Calculate indicators for every timeframe.

        Returns the same MarketDataset object with transformed DataFrames.
        No analytical readiness flags are stored in the domain model.
        """

        if not isinstance(
            dataset,
            MarketDataset,
        ):
            raise TypeError(
                "calculate_dataset expects MarketDataset."
            )

        symbol = dataset.symbol

        for timeframe_data in dataset.timeframes.values():
            self.calculate_timeframe(
                timeframe_data,
                symbol=symbol,
            )

        return dataset

    def calculate_timeframe(
        self,
        timeframe_data: TimeframeData,
        symbol: Optional[str] = None,
    ) -> TimeframeData:
        """
        Calculate indicators for one timeframe.

        The returned TimeframeData remains canonical market-domain data:
        its DataFrame is transformed, but no `indicators_ready` flag is added.
        """

        if not isinstance(
            timeframe_data,
            TimeframeData,
        ):
            raise TypeError(
                "calculate_timeframe expects TimeframeData."
            )

        timeframe = timeframe_data.timeframe
        timeframe_label = (
            timeframe.value
            if isinstance(timeframe, Timeframe)
            else str(timeframe)
        )

        dataframe = timeframe_data.dataframe

        self._validate_dataframe(
            dataframe,
            timeframe_label,
        )

        start_time = time.perf_counter()

        try:
            calculated = self._calculator.apply_all(
                dataframe
            )

            self._calculator.validate_required_indicators(
                calculated
            )

        except Exception as exc:
            raise IndicatorEngineError(
                "Failed to calculate canonical indicators "
                f"for timeframe {timeframe_label}: {exc}"
            ) from exc

        timeframe_data.dataframe = calculated

        elapsed_ms = (
            time.perf_counter() - start_time
        ) * 1000.0

        base_logger.debug(
            "Indicators calculated: symbol=%s timeframe=%s rows=%d "
            "columns=%d elapsed_ms=%.2f",
            symbol,
            timeframe_label,
            len(calculated),
            len(calculated.columns),
            elapsed_ms,
        )

        return timeframe_data

    def available_indicators(self) -> list[str]:
        """Return a copy of the supported indicator names."""

        return list(AVAILABLE_INDICATORS)

    def clear_indicators(
        self,
        timeframe_data: TimeframeData,
    ) -> TimeframeData:
        """
        Remove derived indicator columns.

        Only canonical OHLCV market columns are retained.

        No readiness state is stored.
        """

        if not isinstance(
            timeframe_data,
            TimeframeData,
        ):
            raise TypeError(
                "clear_indicators expects TimeframeData."
            )

        dataframe = timeframe_data.dataframe

        base_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        missing = [
            column
            for column in base_columns
            if column not in dataframe.columns
        ]

        if missing:
            raise InvalidIndicatorData(
                "Cannot clear indicators because required "
                f"market columns are missing: {missing}"
            )

        timeframe_data.dataframe = dataframe[
            base_columns
        ].copy()

        return timeframe_data

    # =========================================================================
    # Validation
    # =========================================================================

    def _validate_dataframe(
        self,
        dataframe: pd.DataFrame,
        timeframe: str,
    ) -> None:
        """Validate canonical OHLCV input before calculation."""

        if dataframe is None or dataframe.empty:
            raise InvalidIndicatorData(
                f"DataFrame for timeframe {timeframe} is empty."
            )

        if not isinstance(
            dataframe.index,
            pd.DatetimeIndex,
        ):
            raise InvalidIndicatorData(
                f"DataFrame index for timeframe {timeframe} "
                "must be DatetimeIndex."
            )

        if dataframe.index.tz is None:
            raise InvalidIndicatorData(
                f"DataFrame index for timeframe {timeframe} "
                "must be timezone-aware."
            )

        if not dataframe.index.is_monotonic_increasing:
            raise InvalidIndicatorData(
                f"DataFrame index for timeframe {timeframe} "
                "must be chronologically sorted."
            )

        if dataframe.index.duplicated().any():
            raise InvalidIndicatorData(
                f"DataFrame for timeframe {timeframe} "
                "contains duplicate timestamps."
            )

        required_columns = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        missing = required_columns - set(
            dataframe.columns
        )

        if missing:
            raise InvalidIndicatorData(
                f"DataFrame for timeframe {timeframe} "
                f"is missing required columns: {missing}"
            )

        numeric_columns = dataframe[
            list(required_columns)
        ]

        if numeric_columns.isna().any().any():
            raise InvalidIndicatorData(
                f"DataFrame for timeframe {timeframe} "
                "contains NaN OHLCV values."
            )

        if np.isinf(
            numeric_columns.to_numpy()
        ).any():
            raise InvalidIndicatorData(
                f"DataFrame for timeframe {timeframe} "
                "contains infinite OHLCV values."
            )

        if (
            dataframe[
                [
                    "open",
                    "high",
                    "low",
                    "close",
                ]
            ] < 0
        ).any().any():
            raise InvalidIndicatorData(
                f"DataFrame for timeframe {timeframe} "
                "contains negative prices."
            )

        if (
            dataframe["volume"] < 0
        ).any():
            raise InvalidIndicatorData(
                f"DataFrame for timeframe {timeframe} "
                "contains negative volume."
            )