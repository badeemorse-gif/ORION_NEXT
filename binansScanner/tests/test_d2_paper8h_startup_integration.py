from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

DJTB = "DJTBUSDT"
EXPECTED_SYMBOLS = tuple(f"S{i:03d}USDT" for i in range(475)) + (DJTB,)
ELIGIBLE_BULK_SYMBOLS = EXPECTED_SYMBOLS[:50]
LOW_VOLUME_BULK_SYMBOLS = EXPECTED_SYMBOLS[50:-1]


def _history_payload(rows: int = 32):
    return [[index, "100", "101", "99", str(100 + (index % 5)), "10"] for index in range(rows)]


def _exchange_info_rows():
    return {
        "symbols": [
            {
                "symbol": symbol,
                "status": "TRADING",
                "baseAsset": symbol[:-4],
                "quoteAsset": "USDT",
                "isSpotTradingAllowed": True,
                "filters": [],
            }
            for symbol in EXPECTED_SYMBOLS
        ]
    }


def _ticker(symbol: str, volume: float = 200_000_000.0):
    return {
        "symbol": symbol,
        "lastPrice": "100",
        "quoteVolume": str(volume),
        "priceChangePercent": "1",
        "weightedAvgPrice": "100",
    }


def _book(symbol: str):
    return {"symbol": symbol, "bidPrice": "99.99", "askPrice": "100.01"}


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


class _PaperNetwork:
    """Deterministic public-network mock for the actual Paper8HRunner composition."""

    def __init__(self, *, persistent_missing: bool):
        self.persistent_missing = persistent_missing
        self.calls: list[dict[str, object]] = []
        self.history_calls: list[tuple[str, str]] = []
        self.phase_trace: list[str] = []

    def __call__(self, request, timeout):
        url = request.full_url
        self.calls.append({"url": url, "timeout": timeout})

        if "exchangeInfo" in url:
            self.phase_trace.append("exchangeInfo")
            return _Response(_exchange_info_rows())

        if "ticker/24hr" in url:
            if "symbol=" in url:
                self.phase_trace.append("targeted_ticker")
                symbol = url.split("symbol=", 1)[1].split("&", 1)[0]
                if symbol != DJTB:
                    raise AssertionError(f"first_divergence=unexpected targeted ticker {symbol}")
                if self.persistent_missing:
                    return _Response([])
                return _Response(_ticker(DJTB))
            self.phase_trace.append("bulk_ticker")
            rows = [_ticker(symbol) for symbol in ELIGIBLE_BULK_SYMBOLS]
            rows.extend(_ticker(symbol, 500_000.0) for symbol in LOW_VOLUME_BULK_SYMBOLS)
            return _Response(rows)

        if "ticker/bookTicker" in url:
            if "symbol=" in url:
                self.phase_trace.append("targeted_book")
                symbol = url.split("symbol=", 1)[1].split("&", 1)[0]
                if symbol != DJTB:
                    raise AssertionError(f"first_divergence=unexpected targeted book {symbol}")
                if self.persistent_missing:
                    return _Response([])
                return _Response(_book(DJTB))
            self.phase_trace.append("bulk_book")
            return _Response([_book(symbol) for symbol in EXPECTED_SYMBOLS[:-1]])

        if "/klines?" in url:
            query = dict(part.split("=", 1) for part in url.split("?", 1)[1].split("&"))
            symbol = query["symbol"]
            interval = query["interval"]
            self.phase_trace.append(f"history:{symbol}:{interval}")
            self.history_calls.append((symbol, interval))
            if self.persistent_missing and symbol == DJTB:
                raise AssertionError(f"first_divergence=unexpected history request for unresolved {DJTB}")
            return _Response(_history_payload())

        raise AssertionError(f"first_divergence=unexpected endpoint {url}")

    def targeted_symbols(self, endpoint: str):
        return [
            call["url"]
            for call in self.calls
            if endpoint in str(call["url"]) and f"?symbol={DJTB}" in str(call["url"])
        ]


class Paper8HStartupIntegrationTests(unittest.TestCase):
    @staticmethod
    def _config(runner_module, output_dir: Path):
        return runner_module.Paper8HConfig(
            duration_hours=0.01,
            starting_capital=50.0,
            dynamic_universe=True,
            top_n=1,
            output_dir=output_dir,
        )

    @staticmethod
    def _discovery_from_runner(runner):
        return runner.opportunity.discovery

    def test_real_paper8h_create_recovers_475_of_476_djtb_with_targeted_metadata(self):
        import tools.orion_paper_8h_runner as runner_module

        network = _PaperNetwork(persistent_missing=False)
        lifecycle = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config(runner_module, Path(tmp) / "run")
            with patch("providers.binance_opportunity_source.urlopen", side_effect=network), patch(
                "tools.orion_paper_8h_runner.urllib.request.urlopen", side_effect=network
            ), patch.object(runner_module, "DynamicMarketStream", return_value=Mock()), patch.object(
                runner_module, "PaperRealtimeLifecycle", return_value=lifecycle
            ) as lifecycle_factory:
                runner = runner_module.Paper8HRunner.create(config)

            self.assertIsNotNone(runner, "first_divergence=create() did not return a runner")
            discovery = self._discovery_from_runner(runner)
            bootstrap = discovery.last_bootstrap
            self.assertEqual((len(bootstrap.expected_symbols), len(bootstrap.received_symbols)), (476, 476))
            self.assertEqual(bootstrap.missing_symbols, ())

            targeted_ticker = network.targeted_symbols("ticker/24hr")
            targeted_book = network.targeted_symbols("ticker/bookTicker")
            self.assertEqual(len(targeted_ticker), 1, f"first_divergence=targeted ticker count={len(targeted_ticker)}")
            self.assertEqual(len(targeted_book), 1, f"first_divergence=targeted book count={len(targeted_book)}")
            self.assertIn("symbol=DJTBUSDT", targeted_ticker[0])
            self.assertIn("symbol=DJTBUSDT", targeted_book[0])
            self.assertEqual(network.history_calls.count((DJTB, "1d")), 1, "first_divergence=DJTB 1d history not acquired exactly once")
            self.assertIn("history:DJTBUSDT:1d", network.phase_trace)

            events = [event for event in discovery.last_reconciliation_events if event["symbol"] == DJTB]
            self.assertEqual(len(events), 1, "first_divergence=unexpected reconciliation event count")
            event = events[0]
            self.assertEqual((event["bulk_ticker_state"], event["bulk_book_state"]), ("absent", "absent"))
            self.assertEqual((event["targeted_ticker_state"], event["targeted_book_state"]), ("present", "present"))
            self.assertTrue(event["needs_history"])
            self.assertEqual(event["history_outcome"], "success")
            self.assertEqual(event["final_disposition"], "eligible")
            lifecycle_factory.assert_called_once()
            self.assertIs(runner.supervisor.runtime, lifecycle)

    def test_real_paper8h_create_blocks_runtime_after_reconciliation_exhaustion(self):
        import tools.orion_paper_8h_runner as runner_module

        network = _PaperNetwork(persistent_missing=True)
        lifecycle_factory = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config(runner_module, Path(tmp) / "run")
            with patch("providers.binance_opportunity_source.urlopen", side_effect=network), patch(
                "tools.orion_paper_8h_runner.urllib.request.urlopen", side_effect=network
            ), patch.object(runner_module, "DynamicMarketStream", return_value=Mock()), patch.object(
                runner_module, "PaperRealtimeLifecycle", lifecycle_factory
            ):
                with self.assertRaisesRegex(RuntimeError, "missing=DJTBUSDT"):
                    runner_module.Paper8HRunner.create(config)

            self.assertEqual(len(network.targeted_symbols("ticker/24hr")), 2)
            self.assertEqual(len(network.targeted_symbols("ticker/bookTicker")), 2)
            self.assertEqual(network.history_calls.count((DJTB, "1d")), 0)
            lifecycle_factory.assert_not_called()

    def test_exact_stage_trace_for_recovery_has_no_mapping_or_history_gap(self):
        import tools.orion_paper_8h_runner as runner_module

        network = _PaperNetwork(persistent_missing=False)
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config(runner_module, Path(tmp) / "run")
            with patch("providers.binance_opportunity_source.urlopen", side_effect=network), patch(
                "tools.orion_paper_8h_runner.urllib.request.urlopen", side_effect=network
            ), patch.object(runner_module, "DynamicMarketStream", return_value=Mock()), patch.object(
                runner_module, "PaperRealtimeLifecycle", return_value=Mock()
            ):
                runner = runner_module.Paper8HRunner.create(config)

            discovery = self._discovery_from_runner(runner)
            bootstrap = discovery.last_bootstrap
            self.assertEqual((len(bootstrap.expected_symbols), len(bootstrap.received_symbols)), (476, 476))
            self.assertEqual(bootstrap.missing_symbols, ())
            self.assertEqual(bootstrap.source_status, "complete")
            self.assertIn("targeted_ticker", network.phase_trace, "first_divergence=targeted ticker never invoked")
            self.assertIn("targeted_book", network.phase_trace, "first_divergence=targeted book never invoked")
            self.assertIn(f"history:{DJTB}:1d", network.phase_trace, "first_divergence=DJTB history never invoked")


if __name__ == "__main__":
    unittest.main()
