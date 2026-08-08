"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.indicator_engine
Version      : 2.0.0
Status       : ORION Production Coordinator V2
===============================================================================

Technical Indicator Engine Coordinator adhering strictly to SRP, delegating
mathematical calculations to IndicatorCalculator.
===============================================================================
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import numpy as np
import pandas as pd

from enums import Timeframe
from models.market import (
    MarketDataset,
    TimeframeData,
)
from engines.indicator_calculator import IndicatorCalculator

base_logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

AVAILABLE_INDICATORS: list[str] = [
    "EMA_20", "EMA_50", "EMA_100", "EMA_200",
    "SMA_20", "SMA_50",
    "ADX", "SuperTrend", "Ichimoku",
    "RSI", "MACD", "Stochastic", "CCI", "Williams_R", "ROC", "Momentum",
    "OBV", "CMF", "VWAP", "MFI",
    "ATR", "Bollinger_Bands", "Keltner_Channel", "Donchian_Channel",
    "Typical_Price", "Median_Price", "HL2", "HLC3", "OHLC4"
]


# =============================================================================
# Custom Exceptions
# =============================================================================

class IndicatorEngineError(Exception):
    """Base exception for all indicator engine related errors."""
    pass


class InvalidIndicatorData(IndicatorEngineError):
    """Raised when indicator input data or calculation structure is invalid."""
    pass


# =============================================================================
# Logger Adapter
# =============================================================================

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


# =============================================================================
# Indicator Engine Coordinator
# =============================================================================

class IndicatorEngine:
    """
    Stateless technical indicator coordinator adhering to ORION architecture.
    Delegates all mathematical computations to IndicatorCalculator.
    """

    def __init__(self, calculator: Optional[IndicatorCalculator] = None) -> None:
        self._calculator = calculator if calculator is not None else IndicatorCalculator()
        self.logger = LoggerAdapter(
            base_logger,
            {"symbol": None, "timeframe": None, "operation": "init"},
        )

    def _get_logger(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[Timeframe | str] = None,
        operation: Optional[str] = None,
        rows: Optional[int] = None,
        indicator_count: Optional[int] = None,
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
                "rows": rows,
                "indicator_count": indicator_count,
                "elapsed_ms": elapsed_ms,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def calculate_dataset(self, dataset: MarketDataset) -> MarketDataset:
        """
        Calculate technical indicators for all available timeframes in a MarketDataset.
        """
        symbol = dataset.symbol
        logger = self._get_logger(symbol=symbol, operation="calculate_dataset")
        logger.info("Calculating technical indicators for dataset across all timeframes.")

        for tf, tf_data in dataset.timeframes.items():
            self.calculate_timeframe(tf_data, symbol=symbol)

        logger.info("Dataset technical indicators calculation completed successfully.")
        return dataset

    def calculate_timeframe(self, timeframe_data: TimeframeData, symbol: Optional[str] = None) -> TimeframeData:
        """
        Calculate and append all technical indicators to a single TimeframeData dataframe.
        """
        tf = timeframe_data.timeframe
        tf_str = tf.value if hasattr(tf, "value") else str(tf)
        
        start_time = time.time()
        df = timeframe_data.dataframe
        self._validate_dataframe(df, tf_str)

        original_cols = set(df.columns)

        try:
            df = self._calculator.apply_all(df)
        except Exception as e:
            if isinstance(e, IndicatorEngineError):
                raise
            raise IndicatorEngineError(f"Failed to calculate indicators for timeframe {tf_str}: {e}") from e

        timeframe_data.dataframe = df
        timeframe_data.indicators_ready = True

        elapsed_ms = (time.time() - start_time) * 1000.0
        new_indicator_count = len(df.columns) - len(original_cols)

        logger = self._get_logger(
            symbol=symbol,
            timeframe=tf,
            operation="calculate_timeframe",
            rows=len(df),
            indicator_count=new_indicator_count,
            elapsed_ms=elapsed_ms,
        )
        logger.info(f"Indicators calculated successfully for timeframe {tf_str}.")

        return timeframe_data

    def available_indicators(self) -> list[str]:
        """
        Return a list of supported indicator categories and names.
        """
        return AVAILABLE_INDICATORS.copy()

    def clear_indicators(self, timeframe_data: TimeframeData) -> TimeframeData:
        """
        Remove calculated indicators by identifying and dropping columns with specific indicator prefixes,
        retaining core columns and non-indicator system columns safely.
        """
        df = timeframe_data.dataframe
        base_cols = {"open", "high", "low", "close", "volume"}
        
        retained_cols = [col for col in df.columns if col in base_cols]
        timeframe_data.dataframe = df[retained_cols]
        timeframe_data.indicators_ready = False
        return timeframe_data

    # -------------------------------------------------------------------------
    # Internal Validation Methods
    # -------------------------------------------------------------------------

    def _validate_dataframe(self, df: pd.DataFrame, tf_str: str) -> None:
        """
        Validate input dataframe for strict indicator calculation readiness.
        """
        if df is None or df.empty:
            raise InvalidIndicatorData(f"DataFrame for timeframe {tf_str} is empty or None.")

        if not isinstance(df.index, pd.DatetimeIndex):
            raise InvalidIndicatorData(f"DataFrame index for timeframe {tf_str} must be a DatetimeIndex.")

        if df.index.tz is None:
            raise InvalidIndicatorData(f"DataFrame index for timeframe {tf_str} must be timezone-aware (UTC).")

        if not df.index.is_monotonic_increasing:
            raise InvalidIndicatorData(f"DataFrame index for timeframe {tf_str} must be chronologically sorted.")

        if df.index.duplicated().any():
            raise InvalidIndicatorData(f"DataFrame for timeframe {tf_str} contains duplicate index timestamps.")

        if df.columns.duplicated().any():
            raise InvalidIndicatorData(f"DataFrame for timeframe {tf_str} contains duplicate column names.")

        required_columns = {"open", "high", "low", "close", "volume"}
        missing_cols = required_columns - set(df.columns)
        if missing_cols:
            raise InvalidIndicatorData(f"DataFrame for timeframe {tf_str} is missing required columns: {missing_cols}")

        for col in required_columns:
            if not np.issubdtype(df[col].dtype, np.floating):
                raise InvalidIndicatorData(f"Column '{col}' for timeframe {tf_str} must have float dtype.")

        sub_df = df[list(required_columns)]
        if sub_df.isna().all().all():
            raise InvalidIndicatorData(f"DataFrame for timeframe {tf_str} contains only NaN values across OHLCV.")

        if (sub_df[["open", "high", "low", "close"]] < 0).any().any():
            raise InvalidIndicatorData(f"DataFrame for timeframe {tf_str} contains negative prices.")

        if (df["volume"] < 0).any():
            raise InvalidIndicatorData(f"DataFrame for timeframe {tf_str} contains negative volume.")

        if np.isinf(sub_df.to_numpy()).any():
            raise InvalidIndicatorData(f"DataFrame for timeframe {tf_str} contains INF values.")