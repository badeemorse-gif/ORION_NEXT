"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.indicator_engine
Version      : 3.0.2
Status       : ORION Canonical Indicator Coordinator
===============================================================================

Coordinates indicator calculation and publishes the canonical IndicatorResult
metadata handoff expected by downstream intelligence layers.
===============================================================================
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
import pandas as pd

from enums import Timeframe
from models.indicators import IndicatorResult
from models.market import MarketDataset, TimeframeData
from engines.indicator_calculator import IndicatorCalculator


base_logger = logging.getLogger(__name__)


AVAILABLE_INDICATORS: tuple[str, ...] = (
    "EMA_9", "EMA_20", "EMA_50", "EMA_100", "EMA_200",
    "SMA_20", "SMA_50", "ADX", "SuperTrend", "Ichimoku", "RSI", "MACD",
    "Stochastic", "CCI", "Williams_R", "ROC", "Momentum_5", "Momentum_10",
    "OBV", "CMF", "VWAP", "MFI", "ATR", "Bollinger_Bands", "Keltner_Channel",
    "Donchian_Channel", "Typical_Price", "Median_Price", "HL2", "HLC3", "OHLC4",
)

# These are the canonical profile-facing outputs already calculated by the
# IndicatorCalculator. The engine reports their presence; it does not assess
# latest-row intelligence validity, which remains a Profile responsibility.
PROFILE_INDICATOR_COLUMNS: tuple[str, ...] = (
    "ema_9", "ema_20", "ema_50", "ema_100", "ema_200",
    "adx_14", "rsi_14", "momentum_5", "momentum_10", "mfi_14", "atr_14",
)


class IndicatorEngineError(Exception):
    """Base exception for indicator-engine failures."""


class InvalidIndicatorData(IndicatorEngineError):
    """Raised when indicator input data is invalid."""


class IndicatorEngine:
    """Canonical indicator coordinator."""

    def __init__(self, calculator: Optional[IndicatorCalculator] = None) -> None:
        self._calculator = calculator if calculator is not None else IndicatorCalculator()

    def execute(self, dataset: MarketDataset) -> MarketDataset:
        """Canonical Core/Orchestrator entry point for indicator processing."""
        return self.calculate_dataset(dataset)

    def calculate_dataset(self, dataset: MarketDataset) -> MarketDataset:
        if not isinstance(dataset, MarketDataset):
            raise TypeError("calculate_dataset expects MarketDataset.")
        symbol = dataset.symbol
        for timeframe_data in dataset.timeframes.values():
            self.calculate_timeframe(timeframe_data, symbol=symbol)
        return dataset

    def calculate_timeframe(self, timeframe_data: TimeframeData, symbol: Optional[str] = None) -> TimeframeData:
        if not isinstance(timeframe_data, TimeframeData):
            raise TypeError("calculate_timeframe expects TimeframeData.")
        timeframe = timeframe_data.timeframe
        timeframe_label = timeframe.value if isinstance(timeframe, Timeframe) else str(timeframe)
        dataframe = timeframe_data.dataframe
        self._validate_dataframe(dataframe, timeframe_label)
        start_time = time.perf_counter()
        try:
            calculated = self._calculator.apply_all(dataframe)
            self._calculator.validate_required_indicators(calculated)
        except Exception as exc:
            warning = f"Indicator calculation failed for timeframe {timeframe_label}: {exc}"
            metadata = IndicatorResult(
                quality="INSUFFICIENT",
                failed_indicators=list(PROFILE_INDICATOR_COLUMNS),
                calculated_indicators=[],
                warnings=[warning],
            )
            dataframe.attrs["indicator_result"] = metadata
            raise IndicatorEngineError(
                f"Failed to calculate canonical indicators for timeframe {timeframe_label}: {exc}"
            ) from exc

        calculated_indicators = [
            name for name in PROFILE_INDICATOR_COLUMNS
            if name in calculated.columns
        ]
        failed_indicators = [
            name for name in PROFILE_INDICATOR_COLUMNS
            if name not in calculated.columns
        ]
        warnings: list[str] = []
        if failed_indicators:
            warnings.append(
                "Missing calculated profile indicators: "
                + ", ".join(failed_indicators)
            )

        metadata = IndicatorResult(
            quality="SUFFICIENT" if not failed_indicators else "INSUFFICIENT",
            failed_indicators=failed_indicators,
            calculated_indicators=calculated_indicators,
            warnings=warnings,
        )
        calculated.attrs["indicator_result"] = metadata
        timeframe_data.dataframe = calculated
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        base_logger.debug(
            "Indicators calculated: symbol=%s timeframe=%s rows=%d columns=%d quality=%s elapsed_ms=%.2f",
            symbol, timeframe_label, len(calculated), len(calculated.columns),
            metadata.quality, elapsed_ms,
        )
        if metadata.quality != "SUFFICIENT":
            raise IndicatorEngineError(
                f"Indicator metadata insufficient for timeframe {timeframe_label}: "
                + ", ".join(metadata.failed_indicators)
            )
        return timeframe_data

    def available_indicators(self) -> list[str]:
        return list(AVAILABLE_INDICATORS)

    def clear_indicators(self, timeframe_data: TimeframeData) -> TimeframeData:
        if not isinstance(timeframe_data, TimeframeData):
            raise TypeError("clear_indicators expects TimeframeData.")
        dataframe = timeframe_data.dataframe
        base_columns = ["open", "high", "low", "close", "volume"]
        missing = [column for column in base_columns if column not in dataframe.columns]
        if missing:
            raise InvalidIndicatorData(
                f"Cannot clear indicators because required market columns are missing: {missing}"
            )
        timeframe_data.dataframe = dataframe[base_columns].copy()
        return timeframe_data

    def _validate_dataframe(self, dataframe: pd.DataFrame, timeframe: str) -> None:
        if dataframe is None or dataframe.empty:
            raise InvalidIndicatorData(f"DataFrame for timeframe {timeframe} is empty.")
        if not isinstance(dataframe.index, pd.DatetimeIndex):
            raise InvalidIndicatorData(f"DataFrame index for timeframe {timeframe} must be DatetimeIndex.")
        if dataframe.index.tz is None:
            raise InvalidIndicatorData(f"DataFrame index for timeframe {timeframe} must be timezone-aware.")
        if not dataframe.index.is_monotonic_increasing:
            raise InvalidIndicatorData(f"DataFrame index for timeframe {timeframe} must be chronologically sorted.")
        if dataframe.index.duplicated().any():
            raise InvalidIndicatorData(f"DataFrame for timeframe {timeframe} contains duplicate timestamps.")
        required_columns = {"open", "high", "low", "close", "volume"}
        missing = required_columns - set(dataframe.columns)
        if missing:
            raise InvalidIndicatorData(f"DataFrame for timeframe {timeframe} is missing required columns: {missing}")
        numeric_columns = dataframe[list(required_columns)]
        if numeric_columns.isna().any().any():
            raise InvalidIndicatorData(f"DataFrame for timeframe {timeframe} contains NaN OHLCV values.")
        if np.isinf(numeric_columns.to_numpy()).any():
            raise InvalidIndicatorData(f"DataFrame for timeframe {timeframe} contains infinite OHLCV values.")
        if (dataframe[["open", "high", "low", "close"]] < 0).any().any():
            raise InvalidIndicatorData(f"DataFrame for timeframe {timeframe} contains negative prices.")
        if (dataframe["volume"] < 0).any():
            raise InvalidIndicatorData(f"DataFrame for timeframe {timeframe} contains negative volume.")
