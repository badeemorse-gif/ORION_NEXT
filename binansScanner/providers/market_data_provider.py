"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : providers.market_data_provider
Version      : 1.1.0
Status       : ORION Production V1.1 REFACTORED
===============================================================================

Market Data Provider responsible solely for fetching market datasets from an
injected data source and mapping them into standard MarketDataset models without
performing any technical analysis, calculations, or evaluations.
===============================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from models.market import MarketDataset, TimeframeData

base_logger = logging.getLogger(__name__)


# =============================================================================
# Protocols / Interfaces for Data Source Injection
# =============================================================================

class DataSourceProtocol(Protocol):
    """Protocol defining the required interface for injected underlying data sources."""

    def fetch_ohlcv(self, symbol: str, timeframe: str) -> Any:
        ...


# =============================================================================
# Custom Exceptions
# =============================================================================

class ProviderError(Exception):
    """Base exception class for all market data provider related errors."""
    pass


class InvalidSymbolError(ProviderError):
    """Raised when a symbol format or value is invalid."""
    pass


class InvalidTimeframeError(ProviderError):
    """Raised when a timeframe format or value is invalid."""
    pass


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting provider operation context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Market Data Provider
# =============================================================================

class MarketDataProvider:
    """
    Stateless market data provider utilizing pure dependency injection to fetch
    and construct MarketDataset instances from an underlying data source.
    """

    def __init__(
        self,
        data_source: DataSourceProtocol,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._data_source = data_source
        self._logger_instance = logger if logger is not None else base_logger

        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "MarketDataProvider",
                "operation": "init",
            },
        )
        self._logger.info("MarketDataProvider initialized successfully.")

    def _get_logger(
        self,
        symbol: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "MarketDataProvider",
                "symbol": symbol,
                "operation": operation,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def fetch_symbol(self, symbol: str, timeframes: list[str]) -> MarketDataset:
        """
        Fetches market data for a single symbol across specified timeframes
        and returns a fully constructed MarketDataset without analysis.
        """
        self._validate_symbol(symbol)
        self._validate_timeframes(timeframes)

        logger = self._get_logger(symbol=symbol, operation="fetch_symbol")
        logger.info(f"Fetching market data for symbol '{symbol}' across timeframes: {timeframes}")

        timeframe_dict: dict[str, TimeframeData] = {}

        for tf in timeframes:
            try:
                raw_df = self._data_source.fetch_ohlcv(symbol, tf)
                timeframe_dict[tf] = TimeframeData(
                    timeframe=tf,
                    df=raw_df,
                )
            except Exception as e:
                logger.error(f"Failed to fetch data for symbol {symbol} on timeframe {tf}: {e}")
                raise ProviderError(f"Failed to fetch {symbol} {tf}") from e

        dataset = MarketDataset(
            symbol=symbol,
            timeframes=timeframe_dict,
        )

        logger.info(f"Successfully constructed MarketDataset for symbol '{symbol}'.")
        return dataset

    def fetch_symbols(self, symbols: list[str], timeframes: list[str]) -> list[MarketDataset]:
        """
        Fetches market data for a list of symbols independently, returning a list of MarketDatasets.
        """
        if not symbols:
            self._logger.warning("fetch_symbols called with empty symbols list.")
            return []

        logger = self._get_logger(operation="fetch_symbols")
        logger.info(f"Batch fetching market data for {len(symbols)} symbols.")

        datasets: list[MarketDataset] = []
        for symbol in symbols:
            try:
                dataset = self.fetch_symbol(symbol, timeframes)
                datasets.append(dataset)
            except Exception as e:
                logger.error(f"Skipping symbol '{symbol}' due to fetch error: {e}")

        return datasets

    # -------------------------------------------------------------------------
    # Internal Validation Methods
    # -------------------------------------------------------------------------

    def _validate_symbol(self, symbol: str) -> None:
        """Validates that the provided symbol is a non-empty string."""
        if not symbol or not isinstance(symbol, str) or not symbol.strip():
            raise InvalidSymbolError(f"Invalid symbol provided: '{symbol}'. Must be a non-empty string.")

    def _validate_timeframes(self, timeframes: list[str]) -> None:
        """Validates that the provided timeframes list is non-empty and contains valid strings."""
        if not timeframes or not isinstance(timeframes, list):
            raise InvalidTimeframeError(f"Invalid timeframes provided: '{timeframes}'. Must be a non-empty list.")
        for tf in timeframes:
            if not tf or not isinstance(tf, str) or not tf.strip():
                raise InvalidTimeframeError(f"Invalid timeframe element found: '{tf}'.")


# =============================================================================
# End Of File
# =============================================================================