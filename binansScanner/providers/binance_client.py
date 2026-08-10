"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module      : providers.binance_client
===============================================================================

Binance REST client boundary.

The client owns transport concerns only. Construction must remain side-effect
free: connectivity is established when an actual API operation is requested,
not while the dependency graph is being assembled.
===============================================================================
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional, TypeVar

from binance.client import Client

from providers.binance_exceptions import BinanceClientError

base_logger = logging.getLogger(__name__)

T = TypeVar("T")


class TokenBucketRateLimiter:
    """Simple local rate limiter for Binance requests."""

    def __init__(self, capacity: int = 1200, refill_rate: float = 20.0) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()

    def consume(self, weight: int = 1) -> None:
        while True:
            now = time.time()
            elapsed = now - self.last_refill
            self.last_refill = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            if self.tokens >= weight:
                break
            required = weight - self.tokens
            sleep_time = required / self.refill_rate
            time.sleep(sleep_time)
        self.tokens -= weight


# =============================================================================
# Binance Client Component
# =============================================================================

class BinanceClient:
    """
    Responsible for raw REST requests, connection management, authentication,
    timeout handling, and retry policies for Binance API.

    Construction is intentionally network-free. python-binance performs a
    connectivity ping by default during ``Client`` construction; disabling
    that implicit ping keeps dependency-container construction deterministic
    and prevents API availability from becoming a composition-root concern.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        timeout: int = 30,
        testnet: bool = False,
    ) -> None:
        self.api_key: str = api_key
        self.api_secret: str = api_secret
        self.timeout: int = timeout
        self.testnet: bool = testnet

        try:
            self._client: Client = Client(
                api_key=self.api_key,
                api_secret=self.api_secret,
                requests_params={"timeout": self.timeout},
                ping=False,
            )
            if self.testnet:
                self._client.API_URL = "https://testnet.binance.vision/api"
        except Exception as e:
            raise BinanceClientError(f"Failed to initialize Binance Client: {e}") from e

        self.logger = base_logger
        self._limiter = TokenBucketRateLimiter()

    def ping(self) -> None:
        self._retry_request(lambda: self._client.ping(), weight=1)

    def get_server_time(self) -> dict[str, Any]:
        return self._retry_request(lambda: self._client.get_server_time(), weight=1)

    def get_exchange_info(self) -> dict[str, Any]:
        return self._retry_request(lambda: self._client.get_exchange_info(), weight=10)

    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> list[list[Any]]:
        return self._retry_request(
            lambda: self._client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
            ),
            weight=1,
        )

    def get_symbol_ticker(self, symbol: str) -> dict[str, Any]:
        return self._retry_request(lambda: self._client.get_symbol_ticker(symbol=symbol), weight=1)

    def _retry_request(self, operation: Callable[[], T], weight: int = 1, retries: int = 3) -> T:
        last_error: Optional[Exception] = None
        for attempt in range(retries):
            try:
                self._limiter.consume(weight)
                return operation()
            except Exception as exc:
                last_error = exc
                if attempt < retries - 1:
                    time.sleep(0.5 * (attempt + 1))
        raise BinanceClientError(f"Binance request failed after {retries} attempts: {last_error}") from last_error


__all__ = ["BinanceClient", "BinanceClientError", "TokenBucketRateLimiter"]
