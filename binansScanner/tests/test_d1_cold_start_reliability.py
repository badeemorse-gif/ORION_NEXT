from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from models.opportunity import MarketMetrics
from services.opportunity_discovery import MarketUniverseDiscovery, OpportunityConfig, OpportunityDiscovery
from providers.binance_opportunity_source import BinanceSpotOpportunitySource


SYMBOLS = ("AAAUSDT", "BBBUSDT", "CCCUSDT", "DDDUSDT")


def _metric(symbol: str, quality: float) -> MarketMetrics:
    return MarketMetrics(
        symbol=symbol,
        quote_volume_24h=200_000_000.0,
        volatility=0.03,
        spread_bps=1.0,
        tradable=True,
        last_price=100.0,
        volume_quality=quality,
        trend_quality=quality,
        momentum_quality=quality,
        structure_quality=quality,
        trend_persistence=quality,
        trend_direction=quality,
        momentum_direction=quality,
    )


class _Universe:
    def __init__(self, symbols: tuple[str, ...]):
        self._symbols = symbols

    def exchange_info(self):
        return {
            "symbols": [
                {
                    "symbol": symbol,
                    "baseAsset": symbol[:-4],
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                }
                for symbol in self._symbols
            ]
        }


class _StartupSource:
    def __init__(self, metrics: dict[str, MarketMetrics]):
        self._startup_deadline = time.monotonic() + 90.0
        self.metrics = metrics

    def exchange_info(self):
        return _Universe(tuple(self.metrics)).exchange_info()

    def metrics_bulk(self, symbols):
        return {symbol: self.metrics[symbol] for symbol in symbols if symbol in self.metrics}


class _ChangingBinanceSource(BinanceSpotOpportunitySource):
    def __init__(self, quality: float):
        super().__init__(ttl_seconds=300.0, timeout_seconds=1.0)
        self.quality = quality
        self.calls = 0

    def _get_json(self, path, params=None):
        if path == "ticker/24hr":
            return [
                {
                    "symbol": symbol,
                    "lastPrice": "100",
                    "quoteVolume": "200000000",
                    "priceChangePercent": "1",
                    "weightedAvgPrice": "100",
                }
                for symbol in SYMBOLS
            ]
        if path == "ticker/bookTicker":
            return [{"symbol": symbol, "bidPrice": "99.99", "askPrice": "100.01"} for symbol in SYMBOLS]
        if path == "klines":
            self.calls += 1
            return [[index, "1", "2", "0", str(100 + index * self.quality), "10"] for index in range(32)]
        raise AssertionError(path)


class _InstrumentedHistorySource(BinanceSpotOpportunitySource):
    def __init__(self, delay: float = 0.02):
        super().__init__(ttl_seconds=0.0, timeout_seconds=1.0)
        self.delay = delay
        self.calls = 0
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()
        self.started_at = 0.0
        self.finished_at = 0.0

    def _get_json(self, path, params=None):
        if path == "ticker/24hr":
            return [
                {
                    "symbol": symbol,
                    "lastPrice": "100",
                    "quoteVolume": "200000000",
                    "priceChangePercent": "1",
                    "weightedAvgPrice": "100",
                }
                for symbol in SYMBOLS
            ]
        if path == "ticker/bookTicker":
            return [{"symbol": symbol, "bidPrice": "99.99", "askPrice": "100.01"} for symbol in SYMBOLS]
        raise AssertionError(path)

    def _fetch_history(self, symbol):
        with self.lock:
            self.calls += 1
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            if self.calls == 1:
                self.started_at = time.monotonic()
        try:
            time.sleep(self.delay)
            return tuple([[index, "1", "2", "0", str(100 + index), "10"] for index in range(32)])
        finally:
            with self.lock:
                self.active -= 1
                if self.active == 0:
                    self.finished_at = time.monotonic()


class D1ColdStartReliabilityTests(unittest.TestCase):
    def test_incomplete_fresh_bootstrap_fails_closed_before_runtime(self):
        metrics = {SYMBOLS[0]: _metric(SYMBOLS[0], 0.9)}
        source = _StartupSource(metrics)
        discovery = OpportunityDiscovery(
            MarketUniverseDiscovery(_Universe(SYMBOLS)),
            source,
            OpportunityConfig(refresh_interval_seconds=30.0),
        )
        with self.assertRaisesRegex(RuntimeError, "fresh discovery bootstrap incomplete"):
            discovery.discover(top_n=1)

    def test_timeout_error_from_fresh_bootstrap_is_not_downgraded(self):
        class TimeoutSource(_StartupSource):
            def metrics_bulk(self, symbols):
                raise TimeoutError("paper startup discovery deadline exceeded")

        source = TimeoutSource({symbol: _metric(symbol, 0.9) for symbol in SYMBOLS})
        discovery = OpportunityDiscovery(MarketUniverseDiscovery(_Universe(SYMBOLS)), source)
        with self.assertRaises(TimeoutError):
            discovery.discover(top_n=2)

    def test_no_cross_run_historical_cache(self):
        first_run = _ChangingBinanceSource(quality=1.0)
        second_run = _ChangingBinanceSource(quality=0.1)
        first = first_run.metrics_bulk(SYMBOLS)
        second = second_run.metrics_bulk(SYMBOLS)
        self.assertEqual(first_run.calls, len(SYMBOLS))
        self.assertEqual(second_run.calls, len(SYMBOLS))
        self.assertNotEqual(first["AAAUSDT"].volatility, second["AAAUSDT"].volatility)
        self.assertIsNot(first_run._cache, second_run._cache)

    def test_fresh_source_has_no_historical_data_from_previous_instance(self):
        prior = _ChangingBinanceSource(quality=1.0)
        prior.metrics_bulk(("AAAUSDT",))
        fresh = _ChangingBinanceSource(quality=0.5)
        fresh.metrics_bulk(("AAAUSDT",))
        self.assertEqual(fresh.calls, 1)

    def test_bounded_concurrency_and_mocked_cold_start_latency_are_observable(self):
        source = _InstrumentedHistorySource(delay=0.02)
        started = time.monotonic()
        source.metrics_bulk(SYMBOLS)
        elapsed = time.monotonic() - started
        self.assertEqual(source.calls, len(SYMBOLS))
        self.assertGreaterEqual(source.max_active, 2)
        self.assertLessEqual(source.max_active, source.DISCOVERY_CONCURRENCY)
        self.assertGreater(source.finished_at - source.started_at, 0.0)
        self.assertLess(elapsed, len(SYMBOLS) * source.delay * 0.9)

    def test_canonical_symbol_order_is_stable_after_parallel_acquisition(self):
        source = _InstrumentedHistorySource(delay=0.01)
        result = source.metrics_bulk(tuple(reversed(SYMBOLS)))
        self.assertEqual(tuple(result), tuple(sorted(SYMBOLS)))

    def test_d1_ranking_is_unchanged_by_startup_guard(self):
        metrics = {symbol: _metric(symbol, 0.9 - index * 0.1) for index, symbol in enumerate(SYMBOLS)}
        normal = OpportunityDiscovery(MarketUniverseDiscovery(_Universe(SYMBOLS)), _StartupSource(metrics))
        startup = OpportunityDiscovery(MarketUniverseDiscovery(_Universe(SYMBOLS)), _StartupSource(metrics))
        expected = tuple(item.symbol for item in normal.discover(top_n=4).candidates)
        actual = tuple(item.symbol for item in startup.discover(top_n=4).candidates)
        self.assertEqual(actual, expected)

    def test_startup_failure_is_recorded_and_runtime_is_never_created(self):
        import tools.orion_paper_8h_runner as runner_module

        class FakeSource:
            def __init__(self, *args, **kwargs):
                self._startup_deadline = kwargs["deadline"]

            def exchange_info(self):
                return {"symbols": []}

        class FakePipeline:
            def __init__(self, *args, **kwargs):
                pass

            def discover(self):
                raise RuntimeError("fresh discovery bootstrap incomplete: 0/1 symbols")

        with tempfile.TemporaryDirectory() as tmp:
            config = runner_module.Paper8HConfig(output_dir=Path(tmp), dynamic_universe=True)
            with patch.object(runner_module, "BinanceSpotOpportunitySource", FakeSource), patch.object(runner_module, "ScalpingOpportunityPipeline", FakePipeline):
                with self.assertRaisesRegex(RuntimeError, "fresh discovery bootstrap incomplete"):
                    runner_module.Paper8HRunner.create(config)

            events = Path(tmp) / "events.jsonl"
            records = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
            failures = [item for item in records if item.get("event_type") == "startup_failure"]
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0]["startup_phase"], "failed")
            self.assertEqual(failures[0]["failure_kind"], "discovery_exception")


if __name__ == "__main__":
    unittest.main()
