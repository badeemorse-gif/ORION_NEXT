from __future__ import annotations

import math
import socket
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from models.opportunity import MarketMetrics
from providers.binance_opportunity_source import BinanceSpotOpportunitySource
from services.opportunity_discovery import MarketUniverseDiscovery, OpportunityConfig, OpportunityDiscovery


SYMBOLS = ("AAABUSDT", "DJTBUSDT")


def _history(rows: int = 32):
    return [[index, "1", "2", "0", str(100 + (index % 3) * 2), "10"] for index in range(rows)]


def _ticker(symbol: str, volume: float = 200_000_000.0):
    return {
        "symbol": symbol,
        "lastPrice": "100",
        "quoteVolume": str(volume),
        "priceChangePercent": "1",
        "weightedAvgPrice": "100",
    }


def _book(symbol: str, spread_bps: float = 1.0):
    half = spread_bps / 20_000.0
    return {
        "symbol": symbol,
        "bidPrice": str(100.0 * (1.0 - half)),
        "askPrice": str(100.0 * (1.0 + half)),
    }


class _ReconciliationSource(BinanceSpotOpportunitySource):
    def __init__(self, persistent_missing: bool = False, low_volume: bool = False, wide_spread: bool = False):
        super().__init__(ttl_seconds=30.0, timeout_seconds=1.0)
        self._startup_deadline = math.inf
        self.metadata_round = 0
        self.history_calls: list[str] = []
        self.persistent_missing = persistent_missing
        self.low_volume = low_volume
        self.wide_spread = wide_spread

    def _get_json(self, path, params=None):
        if path == "ticker/24hr":
            self.metadata_round += 1
            if self.metadata_round == 1:
                return [_ticker("AAABUSDT")]
            if self.persistent_missing:
                return [_ticker("AAABUSDT")]
            volume = 500_000.0 if self.low_volume else 200_000_000.0
            return [_ticker("AAABUSDT"), _ticker("DJTBUSDT", volume)]
        if path == "ticker/bookTicker":
            if self.metadata_round == 1:
                return [_book("AAABUSDT")]
            if self.persistent_missing:
                return [_book("AAABUSDT")]
            spread = 100.0 if self.wide_spread else 1.0
            return [_book("AAABUSDT"), _book("DJTBUSDT", spread)]
        raise AssertionError(path)

    def _fetch_history(self, symbol: str):
        self.history_calls.append(symbol)
        return tuple(_history())


def _metrics(symbol: str) -> MarketMetrics:
    return MarketMetrics(
        symbol=symbol,
        quote_volume_24h=200_000_000.0,
        volatility=0.03,
        spread_bps=1.0,
        tradable=True,
        last_price=100.0,
        volume_quality=1.0,
        trend_quality=0.8,
        momentum_quality=0.7,
        structure_quality=0.9,
        price_change_pct_24h=1.0,
        weighted_avg_price_24h=100.0,
        trend_direction=0.5,
        trend_persistence=0.8,
        momentum_direction=0.4,
    )


class D1MetadataReconciliationTests(unittest.TestCase):
    def test_djtb_incident_475_of_476_is_reconciled_in_same_run(self):
        candidates = tuple(
            type("Candidate", (), {"symbol": f"S{i:03d}USDT", "base_asset": f"S{i:03d}", "quote_asset": "USDT"})()
            for i in range(475)
        ) + (type("Candidate", (), {"symbol": "DJTBUSDT", "base_asset": "DJTB", "quote_asset": "USDT"})(),)

        class Source:
            _startup_deadline = math.inf

            def metrics_bulk(self, symbols):
                return {symbol: _metrics(symbol) for symbol in symbols[:-1]}

            def reconcile_missing_symbols(self, symbols):
                self.reconciled = tuple(symbols)
                return {"DJTBUSDT": _metrics("DJTBUSDT")}

        source = Source()
        discovery = OpportunityDiscovery(
            MarketUniverseDiscovery(SimpleNamespace(exchange_info=lambda: {"symbols": []})),
            source,
            OpportunityConfig(default_top_n=1),
        )
        discovery._universe = SimpleNamespace(discover=lambda: candidates)
        result = discovery.discover(top_n=1)
        self.assertEqual(len(discovery.last_bootstrap.expected_symbols), 476)
        self.assertEqual(len(discovery.last_bootstrap.received_symbols), 476)
        self.assertEqual(discovery.last_bootstrap.missing_symbols, ())
        self.assertEqual(result.candidates[0].symbol, "DJTBUSDT")
        self.assertEqual(source.reconciled, ("DJTBUSDT",))

    def test_transient_metadata_absence_refreshes_without_cached_snapshot(self):
        source = _ReconciliationSource()
        initial = source.metrics_bulk(SYMBOLS)
        self.assertNotIn("DJTBUSDT", initial)
        source._last_daily_candle_handoff = None
        reconciled = source.reconcile_missing_symbols(("DJTBUSDT",))
        self.assertIn("DJTBUSDT", reconciled)
        self.assertGreaterEqual(source.metadata_round, 2)
        events = [event for event in source.reconciliation_events if event["symbol"] == "DJTBUSDT"]
        self.assertEqual(events[-1]["final_disposition"], "eligible")
        self.assertEqual(events[-1]["history_outcome"], "success")

    def test_reconciliation_transient_metadata_timeout_uses_existing_retry(self):
        source = BinanceSpotOpportunitySource(ttl_seconds=0.0, timeout_seconds=1.0)
        responses = {"ticker": 0}
        payload = _history()

        def fake_urlopen(request, timeout):
            url = request.full_url
            if "ticker/24hr" in url:
                responses["ticker"] += 1
                if responses["ticker"] == 1:
                    raise socket.timeout("read timed out")
                return _Response([_ticker("DJTBUSDT")])
            if "ticker/bookTicker" in url:
                return _Response([_book("DJTBUSDT")])
            if "/klines?" in url:
                return _Response(payload)
            raise AssertionError(url)

        with patch("providers.binance_opportunity_source.urlopen", side_effect=fake_urlopen), patch(
            "providers.binance_opportunity_source.time.sleep"
        ) as sleep:
            result = source.reconcile_missing_symbols(("DJTBUSDT",))
        self.assertIn("DJTBUSDT", result)
        self.assertEqual(responses["ticker"], 2)
        sleep.assert_called_once_with(0.5)

    def test_persistent_metadata_absence_is_bounded_and_unresolved(self):
        source = _ReconciliationSource(persistent_missing=True)
        initial = source.metrics_bulk(SYMBOLS)
        self.assertNotIn("DJTBUSDT", initial)
        reconciled = source.reconcile_missing_symbols(("DJTBUSDT",))
        self.assertNotIn("DJTBUSDT", reconciled)
        events = [event for event in source.reconciliation_events if event["symbol"] == "DJTBUSDT"]
        self.assertEqual(len(events), 3)
        self.assertEqual(events[-1]["final_disposition"], "unresolved")
        self.assertEqual(events[-1]["history_outcome"], "exhausted")
        self.assertLessEqual(source.RECONCILIATION_MAX_ATTEMPTS, 2)

    def test_reconciliation_low_volume_becomes_metadata_only_rejection(self):
        source = _ReconciliationSource(low_volume=True)
        source.metrics_bulk(SYMBOLS)
        reconciled = source.reconcile_missing_symbols(("DJTBUSDT",))
        self.assertIn("DJTBUSDT", reconciled)
        self.assertFalse(source._needs_history(
            {"quoteVolume": "500000", "lastPrice": "100", "priceChangePercent": "1", "weightedAvgPrice": "100"},
            _book("DJTBUSDT"),
        ))
        self.assertEqual(source.history_calls.count("DJTBUSDT"), 1)
        event = [event for event in source.reconciliation_events if event["symbol"] == "DJTBUSDT"][-1]
        self.assertEqual(event["final_disposition"], "definitely_ineligible")
        self.assertEqual(event["history_outcome"], "not_required")

    def test_reconciliation_wide_spread_becomes_metadata_only_rejection(self):
        source = _ReconciliationSource(wide_spread=True)
        source.metrics_bulk(SYMBOLS)
        reconciled = source.reconcile_missing_symbols(("DJTBUSDT",))
        self.assertIn("DJTBUSDT", reconciled)
        self.assertEqual(source.history_calls.count("DJTBUSDT"), 1)
        event = [event for event in source.reconciliation_events if event["symbol"] == "DJTBUSDT"][-1]
        self.assertEqual(event["final_disposition"], "definitely_ineligible")
        self.assertEqual(event["history_outcome"], "not_required")

    def test_startup_discovery_fails_closed_when_reconciliation_stays_unresolved(self):
        candidates = (
            type("Candidate", (), {"symbol": "AAABUSDT", "base_asset": "AAA", "quote_asset": "USDT"})(),
            type("Candidate", (), {"symbol": "DJTBUSDT", "base_asset": "DJTB", "quote_asset": "USDT"})(),
        )
        source = _ReconciliationSource(persistent_missing=True)
        discovery = OpportunityDiscovery(
            MarketUniverseDiscovery(SimpleNamespace(exchange_info=lambda: {"symbols": []})),
            source,
            OpportunityConfig(default_top_n=1),
        )
        discovery._universe = SimpleNamespace(discover=lambda: candidates)
        with self.assertRaises(RuntimeError):
            discovery.discover(top_n=1)
        self.assertEqual(discovery.last_bootstrap.missing_symbols, ("DJTBUSDT",))

    def test_non_startup_behavior_does_not_reconcile(self):
        class Source:
            _startup_deadline = None
            calls = 0

            def metrics_bulk(self, symbols):
                self.calls += 1
                return {"DJTBUSDT": _metrics("DJTBUSDT")}

            def reconcile_missing_symbols(self, symbols):
                raise AssertionError("non-startup discovery must not reconcile")

        source = Source()
        candidates = (type("Candidate", (), {"symbol": "DJTBUSDT", "base_asset": "DJTB", "quote_asset": "USDT"})(),)
        discovery = OpportunityDiscovery(
            MarketUniverseDiscovery(SimpleNamespace(exchange_info=lambda: {"symbols": []})),
            source,
            OpportunityConfig(default_top_n=1),
        )
        discovery._universe = SimpleNamespace(discover=lambda: candidates)
        self.assertEqual(discovery.discover(top_n=1).candidates[0].symbol, "DJTBUSDT")


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        import json
        return json.dumps(self.payload).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
