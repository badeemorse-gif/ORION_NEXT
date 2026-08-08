"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : providers.binance_client
Version      : 2.0.0
Status       : ORION Production Client Component
===============================================================================

Binance REST API communication client handling authentication, timeout,
retry policies, and rate limiting via python-binance.
===============================================================================
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import ConnectionError, ReadTimeout, Timeout

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class BinanceClientError(Exception):
    """Base exception for all Binance client related errors."""
    pass


class ClientConnectionError(BinanceClientError):
    """Raised when connection or timeout occurs."""
    pass


class ClientRateLimitError(BinanceClientError):
    """Raised when rate limit is exceeded."""
    pass


# =============================================================================
# Token Bucket Rate Limiter
# =============================================================================

class TokenBucketRateLimiter:
    """
    Token Bucket algorithm implementation for dynamic rate limiting and weight tracking
    with precise post-sleep token recalculation.
    """

    def __init__(self, capacity: float = 1200.0, refill_rate: float = 20.0) -> None:
        self.capacity: float = capacity
        self.tokens: float = capacity
        self.refill_rate: float = refill_rate  # tokens per second
        self.last_refill: float = time.time()

    def acquire(self, weight: int = 1) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        self.last_refill = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

        if self.tokens < weight:
            required = weight - self.tokens
            sleep_time = required / self.refill_rate
            time.sleep(sleep_time)
            now = time.time()
            elapsed = now - self.last_refill
            self.last_refill = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

        self.tokens -= weight


# =============================================================================
# Binance Client Component
# =============================================================================

class BinanceClient:
    """
    Responsible for raw REST requests, connection management, authentication,
    timeout handling, and retry policies for Binance API.
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
        return self._retry_request(
            lambda: self._client.get_symbol_ticker(symbol=symbol),
            weight=1,
        )

    def _retry_request(self, func: Any, weight: int = 1) -> Any:
        retries = 3
        backoff_delays = [1, 2, 4]

        for attempt in range(retries):
            try:
                self._limiter.acquire(weight=weight)
                return func()
            except (BinanceAPIException, BinanceRequestException) as e:
                status_code = getattr(e, "status_code", None)
                code = getattr(e, "code", None)
                if status_code in {429, 418} or code in {-1003, -1021}:
                    self.logger.warning(f"Rate limited or server throttle encountered (status={status_code}): {e}. Retrying...")
                    if attempt == retries - 1:
                        raise ClientRateLimitError(f"Rate limit exceeded after {retries} retries: {e}") from e
                    time.sleep(backoff_delays[attempt])
                else:
                    raise BinanceClientError(f"Binance non-retryable API exception: {e}") from e
            except (Timeout, ReadTimeout, ConnectionError) as e:
                self.logger.warning(f"Network timeout or connection error on attempt {attempt + 1}: {e}")
                if attempt == retries - 1:
                    raise ClientConnectionError(f"Network request failed after {retries} retries: {e}") from e
                time.sleep(backoff_delays[attempt])
            except Exception as e:
                raise BinanceClientError(f"Unexpected request error: {e}") from e