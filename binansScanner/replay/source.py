from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from enums import Timeframe
from providers.binance_opportunity_source import BinanceSpotOpportunitySource

from replay.clock import ReplayClock
from replay.dataset import HistoricalDataset


class HistoricalMarketDataSource(BinanceSpotOpportunitySource):
    """Offline MarketMetrics/candle source backed only by preloaded data."""

    _INTERVALS = {
        Timeframe.D1: "1d",
        Timeframe.H4: "4h",
        Timeframe.H1: "1h",
        Timeframe.M15: "15m",
    }

    def __init__(self, dataset: HistoricalDataset, clock: ReplayClock) -> None:
        super().__init__(ttl_seconds=0.0, timeout_seconds=10.0, clock=clock.monotonic)
        self.dataset = dataset
        self.clock = clock

    @property
    def live_accessed(self) -> bool:
        return False

    def _snapshot(self) -> Mapping[str, Any]:
        return self.dataset.metadata_at(self.clock.simulation_timestamp)

    def exchange_info(self) -> Mapping[str, Any]:
        return self._snapshot().get("exchange_info", {"symbols": []})

    def _get_json(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        params = params or {}
        snapshot = self._snapshot()
        if path == "exchangeInfo":
            return snapshot.get("exchange_info", {"symbols": []})
        if path == "ticker/24hr":
            symbol = params.get("symbol")
            rows = snapshot.get("ticker_24h", [])
            if symbol is None:
                return rows
            wanted = str(symbol).upper()
            return [row for row in rows if str(row.get("symbol", "")).upper() == wanted]
        if path == "ticker/bookTicker":
            symbol = params.get("symbol")
            rows = snapshot.get("book_ticker", [])
            if symbol is None:
                return rows
            wanted = str(symbol).upper()
            return [row for row in rows if str(row.get("symbol", "")).upper() == wanted]
        if path == "klines":
            symbol = str(params.get("symbol", "")).upper()
            interval = str(params.get("interval", "1d"))
            limit = int(params.get("limit", 32))
            rows = self.dataset.candles_at(symbol, interval, self.clock.simulation_timestamp)
            return list(rows[-limit:])
        raise RuntimeError(f"historical replay reached unsupported market-data path: {path}")

    def klines(self, symbol: str, timeframe: Timeframe, limit: int):
        interval = self._INTERVALS[timeframe]
        return self._get_json(
            "klines",
            {"symbol": symbol.upper(), "interval": interval, "limit": int(limit)},
        )

    def _cached(self, key: str, loader):
        # Discovery snapshots must be resolved against the current simulation time.
        return loader()

    def mark(self, timestamp: datetime) -> None:
        self.clock.advance_to(timestamp)


__all__ = ["HistoricalMarketDataSource"]
