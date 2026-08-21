"""Bulk Binance Spot market source for dynamic opportunity discovery."""
from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from models.opportunity import MarketMetrics


@dataclass(slots=True)
class _CacheEntry:
    expires_at: float
    value: Any


class BinanceSpotOpportunitySource:
    """Uses bulk exchangeInfo, 24h ticker, and bookTicker endpoints only."""
    BASE_URL = "https://api.binance.com/api/v3"

    def __init__(self, ttl_seconds: float = 30.0, timeout_seconds: float = 10.0, clock=time.monotonic) -> None:
        if ttl_seconds < 0 or timeout_seconds <= 0:
            raise ValueError("invalid cache/timeout configuration")
        self.ttl_seconds = ttl_seconds
        self.timeout_seconds = timeout_seconds
        self._clock = clock
        self._cache: dict[str, _CacheEntry] = {}

    def _get_json(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        query = f"?{urlencode(params or {})}" if params else ""
        request = Request(f"{self.BASE_URL}/{path}{query}", headers={"Accept": "application/json"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.load(response)

    def _cached(self, key: str, loader):
        now = self._clock()
        entry = self._cache.get(key)
        if entry is not None and entry.expires_at > now:
            return entry.value
        value = loader()
        self._cache[key] = _CacheEntry(now + self.ttl_seconds, value)
        return value

    def exchange_info(self) -> Mapping[str, Any]:
        return self._cached("exchange_info", lambda: self._get_json("exchangeInfo"))

    def metrics_bulk(self, symbols: Sequence[str]) -> Mapping[str, MarketMetrics]:
        wanted = {s.upper() for s in symbols}
        if not wanted:
            return {}
        tickers = self._cached("ticker_24h", lambda: self._get_json("ticker/24hr"))
        books = self._cached("book_ticker", lambda: self._get_json("ticker/bookTicker"))
        ticker_by_symbol = {str(row.get("symbol", "")).upper(): row for row in tickers if isinstance(row, Mapping)}
        book_by_symbol = {str(row.get("symbol", "")).upper(): row for row in books if isinstance(row, Mapping)}
        result: dict[str, MarketMetrics] = {}
        for symbol in sorted(wanted):
            ticker = ticker_by_symbol.get(symbol)
            if ticker is None:
                continue
            try:
                last_price = float(ticker["lastPrice"])
                quote_volume = float(ticker["quoteVolume"])
                change_pct = float(ticker["priceChangePercent"])
                book = book_by_symbol.get(symbol)
                spread_bps = None
                if book is not None:
                    bid = float(book["bidPrice"])
                    ask = float(book["askPrice"])
                    if bid > 0 and ask >= bid:
                        spread_bps = ((ask - bid) / ((ask + bid) / 2.0)) * 10_000.0
                result[symbol] = MarketMetrics(
                    symbol=symbol,
                    quote_volume_24h=quote_volume,
                    volatility=abs(change_pct) / 100.0,
                    spread_bps=spread_bps,
                    tradable=True,
                    last_price=last_price,
                )
            except (KeyError, TypeError, ValueError):
                continue
        return result
