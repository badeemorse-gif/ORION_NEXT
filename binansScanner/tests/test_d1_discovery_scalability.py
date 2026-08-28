from __future__ import annotations

import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from models.opportunity import MarketMetrics, OpportunityCandidate
from services.scalping_pipeline import ScalpingOpportunityPipeline
from providers.binance_opportunity_source import BinanceSpotOpportunitySource, DailyCandleHandoff


TARGET_SYMBOLS = ("AAAUSDT", "BBBUSDT", "CCCUSDT", "DDDUSDT")


def _history(rows: int = 32):
    base_ts = 1_700_000_000_000
    return [[base_ts + index * 86_400_000, "100", "101", "99", str(100 + index), "10"] for index in range(rows)]


def _ticker(symbol: str):
    return {
        "symbol": symbol,
        "lastPrice": "100",
        "quoteVolume": "200000000",
        "priceChangePercent": "1",
        "weightedAvgPrice": "100",
    }


def _book(symbol: str):
    return {"symbol": symbol, "bidPrice": "99.99", "askPrice": "100.01"}


def _candidate(symbol: str, score: float) -> OpportunityCandidate:
    return OpportunityCandidate(
        symbol=symbol,
        opportunity_score=score,
        rank=1,
        metrics=MarketMetrics(symbol, 200_000_000.0, 0.03, None, True, 100.0),
        eligibility_reasons=(),
    )


class _InstrumentedSource(BinanceSpotOpportunitySource):
    def __init__(self, *, delay: float = 0.03):
        super().__init__(ttl_seconds=30.0, timeout_seconds=10.0)
        self.delay = delay
        self.active = 0
        self.max_active = 0
        self.calls: list[str] = []
        self.lock = threading.Lock()

    def _get_json(self, path, params=None):
        if path == "ticker/24hr":
            return [_ticker(symbol) for symbol in TARGET_SYMBOLS]
        if path == "ticker/bookTicker":
            return [_book(symbol) for symbol in TARGET_SYMBOLS]
        raise AssertionError(path)

    def _fetch_history(self, symbol: str):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.calls.append(symbol)
        try:
            time.sleep(self.delay)
            return tuple(_history())
        finally:
            with self.lock:
                self.active -= 1


class _FakeCandleSource:
    def __init__(self, delay: float = 0.02):
        self.delay = delay
        self.active = 0
        self.max_active = 0
        self.calls: list[tuple[str, str, int]] = []
        self.lock = threading.Lock()

    def candles(self, symbol: str, timeframe: str, limit: int):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.calls.append((symbol, timeframe, limit))
        try:
            time.sleep(self.delay * ((ord(symbol[0]) - ord("A")) % 3 + 1))
            return tuple(_history(limit))
        finally:
            with self.lock:
                self.active -= 1


class _FakeDecisionEngine:
    def __init__(self):
        self.config = SimpleNamespace(min_candles=32, active_top_n=1, broad_pool_top_n=100)

    def decide(self, candidate, candle_map, **kwargs):
        return candidate


class _FakePoolManager:
    config = SimpleNamespace(active_top_n=1, broad_pool_top_n=100)


class D1DiscoveryScalabilityTests(unittest.TestCase):
    def test_metrics_history_is_bounded_and_parallel(self):
        source = _InstrumentedSource()
        output = source.metrics_bulk(TARGET_SYMBOLS)
        self.assertEqual(tuple(output), TARGET_SYMBOLS)
        self.assertGreaterEqual(source.max_active, 2)
        self.assertLessEqual(source.max_active, source.DISCOVERY_CONCURRENCY)
        self.assertEqual(sorted(source.calls), sorted(TARGET_SYMBOLS))

    def test_legacy_deadline_marker_does_not_block_history_request(self):
        source = BinanceSpotOpportunitySource()
        source._startup_deadline = time.monotonic() - 1.0
        history = _history()
        with patch.object(source, "_get_json", return_value=history) as get_json:
            result = source._fetch_history("AAAUSDT")
        self.assertEqual(result, tuple(history))
        get_json.assert_called_once_with(
            "klines",
            {"symbol": "AAAUSDT", "interval": "1d", "limit": source.HISTORY_LIMIT},
        )

    def test_inflight_timeout_propagates(self):
        source = _InstrumentedSource()
        original = source._fetch_history

        def timeout_one(symbol: str):
            if symbol == "BBBUSDT":
                raise TimeoutError("paper startup discovery deadline exceeded")
            return original(symbol)

        source._fetch_history = timeout_one
        with self.assertRaises(TimeoutError):
            source.metrics_bulk(TARGET_SYMBOLS)

    def test_candidate_evaluation_is_concurrent_and_bounded(self):
        source = _FakeCandleSource(delay=0.01)
        pipeline = ScalpingOpportunityPipeline.__new__(ScalpingOpportunityPipeline)
        pipeline._candle_source = source
        pipeline._decision_engine = _FakeDecisionEngine()
        pipeline._candidate_pool = _FakePoolManager()
        self.assertEqual(source.max_active, 0)

    def test_daily_handoff_avoids_duplicate_1d_request(self):
        source = BinanceSpotOpportunitySource()
        source._last_daily_candle_handoff = DailyCandleHandoff(limit=source.HISTORY_LIMIT, candles={"AAAUSDT": tuple(_history())})
        self.assertEqual(source.take_daily_candle_handoff().candles["AAAUSDT"], tuple(_history()))
        self.assertIsNone(source.take_daily_candle_handoff())

    def test_legacy_deadline_marker_does_not_override_transport_timeout(self):
        source = BinanceSpotOpportunitySource()
        source._startup_deadline = time.monotonic() - 1.0
        with patch.object(source, "_get_json", return_value={"ok": True}) as get_json:
            self.assertEqual(source._get_json("exchangeInfo"), {"ok": True})
        get_json.assert_called_once_with("exchangeInfo")


if __name__ == "__main__":
    unittest.main()
