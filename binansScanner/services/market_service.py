"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : services.market_service
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

Market Application Service responsible for coordinating market data retrieval
requests between the execution pipeline and the MarketRepository, providing
a clean application service boundary without analytical logic.
===============================================================================
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from models.market import MarketDataset
from repositories.market_repository import MarketRepository

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class MarketServiceError(Exception):
    """Base exception class for all market service related errors."""
    pass


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting service operation context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Market Application Service
# =============================================================================

class MarketService:
    """
    Stateless market application service encapsulating data coordination logic,
    acting as the intermediary between execution pipelines and the market repository.
    """

    def __init__(
        self,
        repository: MarketRepository,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._repository = repository
        self._logger_instance = logger if logger is not None else base_logger

        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "MarketService",
                "operation": "init",
            },
        )
        self._logger.info("MarketService initialized successfully.")

    def _get_logger(
        self,
        symbol: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "MarketService",
                "symbol": symbol,
                "operation": operation,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def get_market_dataset(self, symbol: str, timeframes: list[str]) -> MarketDataset:
        """
        Retrieves a single MarketDataset for a specified symbol across given timeframes
        via the underlying market repository.
        """
        logger = self._get_logger(symbol=symbol, operation="get_market_dataset")
        logger.info(f"Requesting market dataset for symbol '{symbol}' across timeframes: {timeframes}")

        try:
            dataset = self._repository.get_symbol(symbol, timeframes)
            logger.info(f"Successfully retrieved market dataset for symbol '{symbol}'.")
            return dataset
        except Exception as e:
            logger.error(f"Failed to get market dataset for symbol '{symbol}': {e}")
            raise MarketServiceError(f"Failed to get market dataset for symbol {symbol}: {e}") from e

    def get_market_datasets(self, symbols: list[str], timeframes: list[str]) -> list[MarketDataset]:
        """
        Retrieves a list of MarketDatasets for multiple symbols across specified timeframes
        via the underlying market repository.
        """
        logger = self._get_logger(operation="get_market_datasets")
        logger.info(f"Requesting batch market datasets for {len(symbols)} symbols.")

        if not symbols:
            logger.warning("get_market_datasets called with empty symbols list.")
            return []

        try:
            datasets = self._repository.get_symbols(symbols, timeframes)
            logger.info(f"Successfully retrieved {len(datasets)} market datasets in batch.")
            return datasets
        except Exception as e:
            logger.error(f"Failed to batch retrieve market datasets: {e}")
            raise MarketServiceError(f"Failed to batch get market datasets: {e}") from e

    def service_health(self) -> dict[str, Any]:
        """
        Performs a health check on the market service by delegating to the repository health check.
        """
        logger = self._get_logger(operation="service_health")
        logger.info("Executing market service health check.")

        try:
            health_status = self._repository.health_check()
            service_status = {
                "service_available": True,
                "repository_health": health_status,
            }
            logger.info(f"Market service health check completed: {service_status}")
            return service_status
        except Exception as e:
            logger.error(f"Market service health check failed: {e}")
            return {
                "service_available": False,
                "error": str(e),
            }


# =============================================================================
# End Of File
# =============================================================================