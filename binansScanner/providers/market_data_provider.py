"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : providers.market_data_provider
Version      : 2.0.0
Status       : ORION Canonical Provider Boundary
===============================================================================

Canonical application-facing market data provider boundary.

This component converts the external provider implementation into the
canonical MarketDataset contract.

===============================================================================
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Protocol

from enums import Timeframe
from models.market import MarketDataset


base_logger = logging.getLogger(__name__)


# =============================================================================
# Protocol
# =============================================================================


class MarketSourceProtocol(Protocol):
    """
    Protocol implemented by concrete market providers.

    The concrete BinanceProvider already exposes download_timeframe().
    """

    def download_timeframe(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 1000,
    ) -> Any:
        ...


# =============================================================================
# Exceptions
# =============================================================================


class ProviderError(Exception):
    """Base exception for market provider failures."""


class InvalidSymbolError(ProviderError):
    """Raised when a symbol is invalid."""


class InvalidTimeframeError(ProviderError):
    """Raised when timeframe input is invalid."""


# =============================================================================
# Provider Boundary
# =============================================================================


class MarketDataProvider:
    """
    Canonical market-data application boundary.

    Responsibilities:
        - validate request inputs;
        - request market data from injected source;
        - construct MarketDataset through the canonical mapper path.

    It does not perform analysis.
    """

    def __init__(
        self,
        source: MarketSourceProtocol,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if source is None:
            raise ProviderError(
                "Market source dependency is required."
            )

        self._source = source
        self._logger = (
            logger
            if logger is not None
            else base_logger
        )

    def execute(
        self,
        symbol: str,
        timeframes: list[str | Timeframe],
    ) -> MarketDataset:
        """Execute the canonical market-data provider contract."""
        return self.fetch_symbol(
            symbol=symbol,
            timeframes=timeframes,
        )

    def fetch_symbol(
        self,
        symbol: str,
        timeframes: list[str | Timeframe],
        limit: int = 1000,
    ) -> MarketDataset:
        """
        Fetch one canonical MarketDataset.
        """

        self._validate_symbol(symbol)

        normalized_timeframes = [
            self._normalize_timeframe(timeframe)
            for timeframe in timeframes
        ]

        if not normalized_timeframes:
            raise InvalidTimeframeError(
                "At least one timeframe is required."
            )

        dataframe_map: dict[
            Timeframe,
            Any,
        ] = {}

        for timeframe in normalized_timeframes:
            try:
                dataframe = self._source.download_timeframe(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=limit,
                )
            except Exception as exc:
                raise ProviderError(
                    f"Failed to fetch {symbol} "
                    f"{timeframe.value}: {exc}"
                ) from exc

            dataframe_map[timeframe] = dataframe

        mapper = getattr(
            self._source,
            "_mapper",
            None,
        )

        if mapper is None:
            raise ProviderError(
                "Concrete market source must expose its canonical mapper."
            )

        return mapper.create_market_dataset(
            symbol=symbol,
            timeframe_data=dataframe_map,
            exchange="BINANCE",
            source="BINANCE_API",
        )

    def fetch_symbols(
        self,
        symbols: list[str],
        timeframes: list[str | Timeframe],
        limit: int = 1000,
    ) -> list[MarketDataset]:
        """
        Fetch independent datasets for multiple symbols.
        """

        if not symbols:
            return []

        datasets: list[MarketDataset] = []

        for symbol in symbols:
            try:
                datasets.append(
                    self.fetch_symbol(
                        symbol=symbol,
                        timeframes=timeframes,
                        limit=limit,
                    )
                )
            except Exception as exc:
                self._logger.error(
                    "Skipping symbol '%s': %s",
                    symbol,
                    exc,
                )

        return datasets

    # =========================================================================
    # Validation
    # =========================================================================

    def _validate_symbol(
        self,
        symbol: str,
    ) -> None:
        if (
            not isinstance(symbol, str)
            or not symbol.strip()
        ):
            raise InvalidSymbolError(
                f"Invalid symbol: {symbol!r}"
            )

    def _normalize_timeframe(
        self,
        timeframe: str | Timeframe,
    ) -> Timeframe:
        if isinstance(timeframe, Timeframe):
            return timeframe

        try:
            return Timeframe(timeframe)
        except ValueError as exc:
            raise InvalidTimeframeError(
                f"Unsupported timeframe: {timeframe!r}"
            ) from exc
