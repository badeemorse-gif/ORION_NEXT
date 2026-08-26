"""Bulk Binance Spot market source for dynamic opportunity discovery."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from models.opportunity import MarketMetrics


@dataclass(slots=True)
class _CacheEntry:
    expires_at: float
    value: Any


@dataclass(frozen=True, slots=True)
class DailyCandleHandoff:
    """Discovery-scoped daily candles available for equivalent deep evaluation."""

    limit: int
    candles: Mapping[str, tuple[Sequence[Any], ...]]


class BinanceSpotOpportunitySource:
    """Discover spot symbols and derive distinct market-quality features."""

    BASE_URL = "https://api.binance.com/api/v3"
    HISTORY_INTERVAL = "1d"
    HISTORY_LIMIT = 32
    METRICS_HISTORY_WINDOW = 31
    MIN_HISTORY_CANDLES = 22
    DISCOVERY_CONCURRENCY = 4
    EARLY_MIN_QUOTE_VOLUME_24H = 1_000_000.0
    EARLY_MAX_SPREAD_BPS = 50.0

    def __init__(self, ttl_seconds: float = 30.0, timeout_seconds: float = 10.0, clock=time.monotonic) -> None:
        if ttl_seconds < 0 or timeout_seconds <= 0:
            raise ValueError("invalid cache/timeout configuration")
        self.ttl_seconds = ttl_seconds
        self.timeout_seconds = timeout_seconds
        self._clock = clock
        self._cache: dict[str, _CacheEntry] = {}
        self._cache_lock = threading.Lock()
        self._last_daily_candle_handoff: DailyCandleHandoff | None = None

    def _get_json(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        query = f"?{urlencode(params or {})}" if params else ""
        request = Request(f"{self.BASE_URL}/{path}{query}", headers={"Accept": "application/json"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.load(response)

    def _cached(self, key: str, loader):
        now = self._clock()
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry is not None and entry.expires_at > now:
                return entry.value
        value = loader()
        with self._cache_lock:
            current = self._cache.get(key)
            if current is not None and current.expires_at > now:
                return current.value
            self._cache[key] = _CacheEntry(now + self.ttl_seconds, value)
        return value

    def exchange_info(self) -> Mapping[str, Any]:
        return self._cached("exchange_info", lambda: self._get_json("exchangeInfo"))

    def take_daily_candle_handoff(self) -> DailyCandleHandoff | None:
        """Consume the latest discovery-scoped daily candle dataset exactly once."""
        handoff = self._last_daily_candle_handoff
        self._last_daily_candle_handoff = None
        return handoff

    @staticmethod
    def _ema(values: Sequence[float], period: int) -> float:
        if len(values) < period:
            raise ValueError("insufficient history for EMA")
        alpha = 2.0 / (period + 1.0)
        ema = statistics.fmean(values[:period])
        for value in values[period:]:
            ema = alpha * value + (1.0 - alpha) * ema
        return ema

    @classmethod
    def _history_features(cls, rows: Sequence[Any]) -> tuple[float, float, float, float, float, float]:
        closes = [float(row[4]) for row in rows if isinstance(row, Sequence) and len(row) > 4]
        if len(closes) < cls.MIN_HISTORY_CANDLES:
            raise ValueError("insufficient price history")
        returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i] > 0 and closes[i - 1] > 0]
        if len(returns) < cls.MIN_HISTORY_CANDLES - 1:
            raise ValueError("insufficient return history")

        volatility = statistics.stdev(returns)
        ema_fast = cls._ema(closes[-21:], 7)
        ema_slow = cls._ema(closes[-21:], 21)
        trend_direction = max(-1.0, min(1.0, (ema_fast / ema_slow - 1.0) / 0.05)) if ema_slow > 0 else 0.0
        recent_returns = returns[-7:]
        positive_fraction = sum(value > 0 for value in recent_returns) / len(recent_returns)
        negative_fraction = sum(value < 0 for value in recent_returns) / len(recent_returns)
        trend_persistence = max(positive_fraction, negative_fraction)
        trend_quality = min(1.0, abs(trend_direction)) * trend_persistence

        roc_3 = closes[-1] / closes[-4] - 1.0
        roc_7 = closes[-1] / closes[-8] - 1.0
        momentum_raw = roc_3 - (roc_7 / 7.0 * 3.0)
        momentum_direction = max(-1.0, min(1.0, momentum_raw / 0.03))
        momentum_quality = min(1.0, abs(momentum_direction))
        return volatility, trend_quality, trend_direction, trend_persistence, momentum_quality, momentum_direction

    def _fetch_history(self, symbol: str) -> tuple[Sequence[Any], ...]:
        def loader():
            deadline = getattr(self, "_startup_deadline", None)
            if deadline is None:
                return self._get_json(
                    "klines",
                    {"symbol": symbol, "interval": self.HISTORY_INTERVAL, "limit": self.HISTORY_LIMIT},
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("paper startup discovery deadline exceeded")
            query = urlencode({"symbol": symbol, "interval": self.HISTORY_INTERVAL, "limit": self.HISTORY_LIMIT})
            request = Request(f"{self.BASE_URL}/klines?{query}", headers={"Accept": "application/json"})
            with urlopen(request, timeout=min(self.timeout_seconds, remaining)) as response:
                return json.load(response)

        history = self._cached(f"klines_{symbol}", loader)
        if not isinstance(history, list):
            raise ValueError("invalid price history payload")
        return tuple(history)

    @classmethod
    def _needs_history(cls, ticker: Mapping[str, Any] | None, book: Mapping[str, Any] | None) -> bool:
        if ticker is None:
            return True
        try:
            quote_volume = float(ticker["quoteVolume"])
        except (KeyError, TypeError, ValueError):
            return True
        if not math.isfinite(quote_volume) or quote_volume < cls.EARLY_MIN_QUOTE_VOLUME_24H:
            return False
        if book is None:
            return True
        try:
            bid = float(book["bidPrice"])
            ask = float(book["askPrice"])
        except (KeyError, TypeError, ValueError):
            return True
        if bid <= 0 or ask < bid:
            return True
        spread_bps = ((ask - bid) / ((ask + bid) / 2.0)) * 10_000.0
        return not math.isfinite(spread_bps) or spread_bps <= cls.EARLY_MAX_SPREAD_BPS

    @classmethod
    def _metadata_only_metric(cls, symbol: str, ticker: Mapping[str, Any] | None, book: Mapping[str, Any] | None) -> MarketMetrics | None:
        if ticker is None:
            return None
        try:
            quote_volume = float(ticker["quoteVolume"])
        except (KeyError, TypeError, ValueError):
            return None
        change_pct = None
        weighted_avg = None
        last_price = None
        try:
            change_pct = float(ticker["priceChangePercent"])
        except (KeyError, TypeError, ValueError):
            pass
        try:
            weighted_avg = float(ticker["weightedAvgPrice"])
        except (KeyError, TypeError, ValueError):
            pass
        try:
            last_price = float(ticker["lastPrice"])
        except (KeyError, TypeError, ValueError):
            pass
        spread_bps = None
        if book is not None:
            try:
                bid = float(book["bidPrice"])
                ask = float(book["askPrice"])
                if bid > 0 and ask >= bid:
                    spread_bps = ((ask - bid) / ((ask + bid) / 2.0)) * 10_000.0
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                pass
        safe_volume = quote_volume if math.isfinite(quote_volume) else 0.0
        volume_quality = min(math.log1p(max(safe_volume, 0.0)) / math.log1p(100_000_000.0), 1.0)
        return MarketMetrics(
            symbol=symbol,
            quote_volume_24h=quote_volume,
            volatility=0.0,
            spread_bps=spread_bps,
            tradable=True,
            last_price=last_price,
            volume_quality=volume_quality,
            trend_quality=None,
            momentum_quality=None,
            structure_quality=None,
            price_change_pct_24h=change_pct,
            weighted_avg_price_24h=weighted_avg,
            trend_direction=None,
            trend_persistence=None,
            momentum_direction=None,
        )

    def metrics_bulk(self, symbols: Sequence[str]) -> Mapping[str, MarketMetrics]:
        wanted = tuple(sorted({s.upper() for s in symbols}))
        self._last_daily_candle_handoff = None
        if not wanted:
            return {}

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="orion-discovery-metadata") as executor:
            ticker_future = executor.submit(self._cached, "ticker_24h", lambda: self._get_json("ticker/24hr"))
            book_future = executor.submit(self._cached, "book_ticker", lambda: self._get_json("ticker/bookTicker"))
            tickers = ticker_future.result()
            books = book_future.result()
        ticker_by_symbol = {str(row.get("symbol", "")).upper(): row for row in tickers if isinstance(row, Mapping)}
        book_by_symbol = {str(row.get("symbol", "")).upper(): row for row in books if isinstance(row, Mapping)}
        history_symbols = tuple(
            symbol for symbol in wanted
            if self._needs_history(ticker_by_symbol.get(symbol), book_by_symbol.get(symbol))
        )

        histories: dict[str, tuple[Sequence[Any], ...]] = {}
        with ThreadPoolExecutor(max_workers=self.DISCOVERY_CONCURRENCY, thread_name_prefix="orion-discovery-history") as executor:
            future_to_symbol = {
                executor.submit(self._fetch_history, symbol): symbol
                for symbol in history_symbols
            }
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    histories[symbol] = future.result()
                except TimeoutError:
                    for pending in future_to_symbol:
                        pending.cancel()
                    raise
                except Exception:
                    continue

        result: dict[str, MarketMetrics] = {}
        reusable_daily: dict[str, tuple[Sequence[Any], ...]] = {}
        for symbol in wanted:
            ticker = ticker_by_symbol.get(symbol)
            if not self._needs_history(ticker, book_by_symbol.get(symbol)):
                metadata_metric = self._metadata_only_metric(symbol, ticker, book_by_symbol.get(symbol))
                if metadata_metric is None:
                    continue
                result[symbol] = metadata_metric
                continue
            history = histories.get(symbol)
            if ticker is None or history is None:
                continue
            try:
                last_price = float(ticker["lastPrice"])
                quote_volume = float(ticker["quoteVolume"])
                change_pct = float(ticker["priceChangePercent"])
                weighted_avg = float(ticker["weightedAvgPrice"])
                book = book_by_symbol.get(symbol)
                spread_bps = None
                if book is not None:
                    bid = float(book["bidPrice"])
                    ask = float(book["askPrice"])
                    if bid > 0 and ask >= bid:
                        spread_bps = ((ask - bid) / ((ask + bid) / 2.0)) * 10_000.0

                metric_history = history[-self.METRICS_HISTORY_WINDOW:]
                volatility, trend_quality, trend_direction, trend_persistence, momentum_quality, momentum_direction = self._history_features(metric_history)
                structure_deviation = abs(last_price / weighted_avg - 1.0) if weighted_avg > 0 else math.inf
                structure_quality = max(0.0, 1.0 - min(structure_deviation / 0.05, 1.0)) if math.isfinite(structure_deviation) else 0.0
                volume_quality = min(math.log1p(max(quote_volume, 0.0)) / math.log1p(100_000_000.0), 1.0)

                result[symbol] = MarketMetrics(
                    symbol=symbol,
                    quote_volume_24h=quote_volume,
                    volatility=volatility,
                    spread_bps=spread_bps,
                    tradable=True,
                    last_price=last_price,
                    volume_quality=volume_quality,
                    trend_quality=trend_quality,
                    momentum_quality=momentum_quality,
                    structure_quality=structure_quality,
                    price_change_pct_24h=change_pct,
                    weighted_avg_price_24h=weighted_avg,
                    trend_direction=trend_direction,
                    trend_persistence=trend_persistence,
                    momentum_direction=momentum_direction,
                )
                if len(history) == self.HISTORY_LIMIT:
                    reusable_daily[symbol] = history
            except (KeyError, TypeError, ValueError, statistics.StatisticsError, ZeroDivisionError):
                continue

        self._last_daily_candle_handoff = DailyCandleHandoff(
            limit=self.HISTORY_LIMIT,
            candles=dict(reusable_daily),
        )
        return result
