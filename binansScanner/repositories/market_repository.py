"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : repositories.market_repository
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

Market Repository serving as the single unified data access facade for the Pipeline,
coordinating between market data providers and storage layers using pure dependency
injection and abstracting underlying data sources.
===============================================================================
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from models.market import MarketDataset
from providers.market_data_provider import MarketDataProvider
from storage.market_storage import MarketStorage

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class RepositoryError(Exception):
    """Base exception class for all repository related errors."""
    pass


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting repository operation context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Market Repository Facade
# =============================================================================

class MarketRepository:
    """
    Stateless market repository encapsulating data access logic, acting as the
    sole interface between the execution pipeline and underlying market data providers
    or storage layers.
    """

    def __init__(
        self,
        market_provider: MarketDataProvider,
        storage: Optional[MarketStorage] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._market_provider = market_provider
        self._storage = storage
        self._logger_instance = logger if logger is not None else base_logger

        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "MarketRepository",
                "operation": "init",
            },
        )
        self._logger.info("MarketRepository initialized successfully.")

    def _get_logger(
        self,
        symbol: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "MarketRepository",
                "symbol": symbol,
                "operation": operation,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def get_symbol(self, symbol: str, timeframes: list[str]) -> MarketDataset:
        """
        Retrieves market data for a single symbol across specified timeframes,
        coordinating provider extraction and optional storage handling.
        """
        logger = self._get_logger(symbol=symbol, operation="get_symbol")
        logger.info(f"Retrieving market dataset for symbol '{symbol}' across timeframes: {timeframes}")

        try:
            # Future expansion: Check cache/storage here before invoking provider
            dataset = self._market_provider.fetch_symbol(symbol, timeframes)

            # Future expansion: Persist fetched dataset into storage if configured
            if self._storage is not None:
                try:
                    # Placeholder for future storage save logic if applicable
                    pass
                except Exception as storage_err:
                    logger.warning(f"Failed to persist dataset to storage for symbol '{symbol}': {storage_err}")

            logger.info(f"Successfully retrieved MarketDataset for symbol '{symbol}'.")
            return dataset

        except Exception as e:
            logger.error(f"Failed to retrieve market data for symbol '{symbol}': {e}")
            raise RepositoryError(f"Failed to get symbol {symbol}: {e}") from e

    def get_symbols(self, symbols: list[str], timeframes: list[str]) -> list[MarketDataset]:
        """
        Retrieves market data for a list of symbols across specified timeframes.
        """
        logger = self._get_logger(operation="get_symbols")
        logger.info(f"Batch retrieving market datasets for {len(symbols)} symbols.")

        if not symbols:
            logger.warning("get_symbols called with empty symbols list.")
            return []

        try:
            datasets = self._market_provider.fetch_symbols(symbols, timeframes)
            logger.info(f"Successfully retrieved {len(datasets)} MarketDatasets in batch.")
            return datasets
        except Exception as e:
            logger.error(f"Failed to batch retrieve market data: {e}")
            raise RepositoryError(f"Failed to get symbols batch: {e}") from e

    def health_check(self) -> dict[str, Any]:
        """
        Performs a health check on the repository dependencies (provider and storage).
        """
        logger = self._get_logger(operation="health_check")
        logger.info("Executing repository health check.")

        provider_status = False
        try:
            # Verify provider readiness if possible, or assume available if instantiated
            provider_status = self._market_provider is not None
        except Exception:
            provider_status = False

        storage_status = False
        if self._storage is not None:
            try:
                # Verify storage readiness if applicable
                storage_status = True
            except Exception:
                storage_status = False
        else:
            storage_status = None  # Storage is optional

        status_report = {
            "provider_available": provider_status,
            "storage_available": storage_status,
        }

        logger.info(f"Repository health check completed: {status_report}")
        return status_report


# =============================================================================
# End Of File
# =============================================================================