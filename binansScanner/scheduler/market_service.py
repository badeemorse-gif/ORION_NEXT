"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : services.market_service
Version      : 1.1.0
Status       : ORION Production Service Layer
===============================================================================

Market Service acting purely as a Service Layer delegating market data requests
to MarketRepository with strict adherence to SRP and pure Dependency Injection.
===============================================================================
"""

from __future__ import annotations

import logging
from typing import Any

from models.market import MarketDataset
from repositories.market_repository import MarketRepository

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class MarketServiceError(Exception):
    """Base exception for all market service related errors."""
    pass


class InvalidSymbolError(MarketServiceError):
    """Raised when a symbol format is invalid."""
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
# Market Service Layer
# =============================================================================

class MarketService:
    """
    Service Layer responsible exclusively for coordinating market data operations
    between application callers and MarketRepository without business logic,
    calculations, or direct provider calls.
    """

    def __init__(self, repository: MarketRepository) -> None:
        if repository is None:
            raise MarketServiceError("MarketRepository must be provided via dependency injection.")
        self._repository = repository
        self.logger = LoggerAdapter(
            base_logger,
            {
                "symbol": None,
                "operation": "init",
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def get_market_dataset(self, symbol: str) -> MarketDataset:
        """
        Retrieve MarketDataset for a given symbol from the repository.
        """
        self.validate_symbol(symbol)
        clean_symbol = symbol.upper().strip()

        logger = LoggerAdapter(base_logger, {"symbol": clean_symbol, "operation": "get_market_dataset"})
        logger.info("Fetching market dataset from repository.")

        try:
            dataset = self._repository.get_dataset(clean_symbol)
            if dataset is None:
                raise MarketServiceError(f"No market dataset returned for symbol {clean_symbol}.")
            return dataset
        except Exception as e:
            if isinstance(e, MarketServiceError):
                raise
            raise MarketServiceError(f"Failed to get market dataset for {clean_symbol}: {e}") from e

    def refresh_market_dataset(self, symbol: str) -> MarketDataset:
        """
        Force the repository to refresh and update market data for a given symbol.
        """
        self.validate_symbol(symbol)
        clean_symbol = symbol.upper().strip()

        logger = LoggerAdapter(base_logger, {"symbol": clean_symbol, "operation": "refresh_market_dataset"})
        logger.info("Forcing market dataset refresh in repository.")

        try:
            dataset = self._repository.refresh_dataset(clean_symbol)
            if dataset is None:
                raise MarketServiceError(f"No refreshed market dataset returned for symbol {clean_symbol}.")
            return dataset
        except Exception as e:
            if isinstance(e, MarketServiceError):
                raise
            raise MarketServiceError(f"Failed to refresh market dataset for {clean_symbol}: {e}") from e

    def repository_health(self) -> dict[str, Any]:
        """
        Return health status information from the underlying repository.
        """
        logger = LoggerAdapter(base_logger, {"symbol": None, "operation": "repository_health"})
        logger.info("Checking repository health.")

        try:
            if hasattr(self._repository, "health"):
                return self._repository.health()
            return {"status": "HEALTHY", "repository": type(self._repository).__name__}
        except Exception as e:
            raise MarketServiceError(f"Failed to retrieve repository health: {e}") from e

    def validate_symbol(self, symbol: str) -> None:
        """
        Perform basic validation on the symbol string format before passing to repository.
        """
        if not symbol or not isinstance(symbol, str) or not symbol.strip():
            raise InvalidSymbolError(f"Invalid symbol provided: '{symbol}'. Symbol must be a non-empty string.")


# =============================================================================
# End Of File
# =============================================================================