"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : providers.binance_provider
Version      : 2.0.0
Status       : ORION Production Coordinator V2
===============================================================================

Binance market data provider coordinator strictly focused on orchestrating
BinanceClient and BinanceMapper without direct low-level REST calls or raw transformations.
===============================================================================
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from enums import Timeframe
from models.market import MarketDataset
from providers.binance_client import BinanceClient, BinanceClientError
from providers.binance_mapper import BinanceMapper, BinanceMapperError

base_logger = logging.getLogger(__name__)


# =============================================================================
# Version Constants & Mappings
# =============================================================================

PROVIDER_VERSION: str = "2.0.0"
API_VERSION: str = "v3"

TIMEFRAME_MAPPING: dict[Timeframe, str] = {
    Timeframe.M1: "1m",
    Timeframe.M5: "5m",
    Timeframe.M15: "15m",
    Timeframe.H1: "1h",
    Timeframe.H4: "4h",
    Timeframe.D1: "1d",
}


# =============================================================================
# Custom Exceptions
# =============================================================================

class ProviderError(Exception):
    """Base exception for all provider-related errors."""
    pass


class InvalidSymbol(ProviderError):
    """Raised when a symbol is invalid or does not exist."""
    pass


class DownloadError(ProviderError):
    """Raised when data downloading fails."""
    pass


class RateLimitError(ProviderError):
    """Raised when rate limit is breached or exceeds limits."""
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
# Binance Provider Coordinator
# =============================================================================

class BinanceProvider:
    """
    Coordinator responsible for managing market data retrieval workflow by delegating
    network calls to BinanceClient and data mapping/cleaning to BinanceMapper, returning
    raw DataFrames or MarketDataset containers.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        timeout: int = 30,
        testnet: bool = False,
        client: Optional[BinanceClient] = None,
        mapper: Optional[BinanceMapper] = None,
    ) -> None:
        self.api_key: str = api_key
        self.api_secret: str = api_secret
        self.timeout: int = timeout
        self.testnet: bool = testnet

        self._client = client if client is not None else BinanceClient(
            api_key=self.api_key,
            api_secret=self.api_secret,
            timeout=self.timeout,
            testnet=self.testnet,
        )
        self._mapper = mapper if mapper is not None else BinanceMapper()

        self.logger = LoggerAdapter(
            base_logger,
            {"symbol": None, "timeframe": None, "operation": "init"},
        )

        self._cached_symbols: set[str] = set()
        self._exchange_info_cache: Optional[dict[str, Any]] = None
        self._exchange_info_timestamp: float = 0.0
        self._cache_ttl: float = 1800.0  # 30 minutes

    def _get_logger(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[Timeframe | str] = None,
        operation: Optional[str] = None,
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
            {"symbol": symbol, "timeframe": tf_str, "operation": operation},
        )

    def _refresh_exchange_cache(self) -> None:
        """
        Refresh exchange info cache if expired (TTL 30 minutes).
        """
        now = time.time()
        if (
            self._exchange_info_cache is None
            or (now - self._exchange_info_timestamp) > self._cache_ttl
        ):
            self.logger.info("Refreshing exchange info cache.")
            try:
                info = self._client.get_exchange_info()
            except Exception as e:
                raise ProviderError(f"Failed to fetch exchange info: {e}") from e

            self._exchange_info_cache = info
            self._cached_symbols = {
                s["symbol"]
                for s in info.get("symbols", [])
                if s.get("status") == "TRADING"
            }
            self._exchange_info_timestamp = now

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def ping(self) -> bool:
        """
        Ping Binance API to check connectivity.
        """
        try:
            self._client.ping()
            return True
        except Exception as e:
            raise ProviderError(f"Ping failed: {e}") from e

    def server_time(self) -> datetime:
        """
        Get Binance server time as a UTC datetime object.
        """
        try:
            response = self._client.get_server_time()
            server_timestamp = response.get("serverTime", 0) / 1000.0
            return datetime.fromtimestamp(server_timestamp, tz=timezone.utc)
        except Exception as e:
            raise ProviderError(f"Failed to get server time: {e}") from e

    def exchange_info(self) -> dict[str, Any]:
        """
        Fetch exchange information from cached state.
        """
        self._refresh_exchange_cache()
        assert self._exchange_info_cache is not None
        return self._exchange_info_cache

    def symbol_exists(self, symbol: str) -> bool:
        """
        Check if a given symbol exists and is actively trading on Binance.
        """
        try:
            self._validate_symbol(symbol)
            return True
        except (InvalidSymbol, ProviderError):
            return False

    def list_symbols(self) -> list[str]:
        """
        List all active trading symbols on Binance sorted alphabetically.
        """
        self._refresh_exchange_cache()
        return sorted(list(self._cached_symbols))

    def download_timeframe(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """
        Download historical klines for a single symbol and timeframe,
        delegating fetching to BinanceClient and mapping/cleaning to BinanceMapper.
        """
        self._validate_symbol(symbol)
        tf_str = TIMEFRAME_MAPPING.get(timeframe, timeframe.value if hasattr(timeframe, "value") else str(timeframe))
        
        logger = self._get_logger(symbol=symbol, timeframe=timeframe, operation="download_timeframe")
        start_time = time.time()
        logger.info(f"Downloading timeframe {tf_str}.")

        try:
            raw_klines = self._client.get_klines(symbol=symbol, interval=tf_str, limit=limit)
            df = self._mapper.convert_klines_to_dataframe(raw_klines)
        except Exception as e:
            if isinstance(e, ProviderError):
                raise
            raise DownloadError(f"Failed to download timeframe {tf_str} for {symbol}: {e}") from e

        elapsed_ms = (time.time() - start_time) * 1000.0
        logger.info(f"Downloaded timeframe {tf_str}.", extra={"elapsed_ms": elapsed_ms, "rows": len(df)})

        return df

    def download_dataset(
        self,
        symbol: str,
        timeframes: list[Timeframe],
    ) -> MarketDataset:
        """
        Download dataset across multiple timeframes concurrently and return a fully populated MarketDataset.
        """
        self._validate_symbol(symbol)
        logger = self._get_logger(symbol=symbol, operation="download_dataset")
        start_time = time.time()
        logger.info(f"Downloading dataset across timeframes: {timeframes}")

        tf_data_dict: dict[Timeframe, pd.DataFrame] = {}

        with ThreadPoolExecutor(max_workers=min(len(timeframes), 5)) as executor:
            future_to_tf = {
                executor.submit(self.download_timeframe, symbol, tf): tf
                for tf in timeframes
            }
            try:
                for future in as_completed(future_to_tf):
                    tf = future_to_tf[future]
                    df = future.result()
                    tf_data_dict[tf] = df
            except Exception as e:
                logger.error(f"Error during concurrent dataset download: {e}")
                for future in future_to_tf:
                    future.cancel()
                raise DownloadError(f"Concurrent download failed for symbol {symbol}: {e}") from e

        dataset = self._mapper.create_market_dataset(symbol, tf_data_dict)
        elapsed_ms = (time.time() - start_time) * 1000.0
        logger.info("Dataset successfully downloaded and created.", extra={"elapsed_ms": elapsed_ms})
        return dataset

    def latest_price(self, symbol: str) -> float:
        """
        Get the latest ticker price for a symbol.
        """
        self._validate_symbol(symbol)
        try:
            ticker = self._client.get_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        except Exception as e:
            raise ProviderError(f"Failed to get latest price for {symbol}: {e}") from e

    def klines(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 500,
    ) -> list[list[Any]]:
        """
        Fetch raw klines data for a symbol and timeframe.
        """
        self._validate_symbol(symbol)
        tf_str = TIMEFRAME_MAPPING.get(timeframe, timeframe.value if hasattr(timeframe, "value") else str(timeframe))
        try:
            return self._client.get_klines(symbol=symbol, interval=tf_str, limit=limit)
        except Exception as e:
            raise ProviderError(f"Failed to fetch klines for {symbol}: {e}") from e

    # -------------------------------------------------------------------------
    # Internal Private Methods
    # -------------------------------------------------------------------------

    def _validate_symbol(self, symbol: str) -> None:
        """
        Validate if the symbol exists in the cached exchange info.
        """
        self._refresh_exchange_cache()
        if symbol not in self._cached_symbols:
            raise InvalidSymbol(f"Symbol {symbol} does not exist or is not trading on Binance.")