from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from models.opportunity import MarketMetrics
from providers.binance_opportunity_source import BinanceSpotOpportunitySource

DJTB = "DJTBUSDT"
EXPECTED_SYMBOLS = tuple(f"S{i:03d}USDT" for i in range(475)) + (DJTB,)


def _history_payload(rows: int = 32):
    return [[index, "100", "101", "99", str(100 + (index % 5)), "10"] for index in range(rows)]


def _exchange_info_rows():
    rows = []
    for symbol in EXPECTED_SYMBOLS:
        base = symbol[:-4]
        rows.append(
            {
                "symbol": symbol,
                "status": "TRADING",
                "baseAsset": base,
                "quoteAsset": "USDT",
                "isSpotTradingAllowed": True,
                "filters": [],
            }
        )
    return {"symbols": rows}


def _ticker(symbol: str, volume: float = 1_000_000.0):
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

    def __iter__(self):
        return iter(())


class _PaperNetwork:
    """Deterministic public-network mock for the actual Paper8HRunner composition."""

    def __init__(self, *, persistent_missing: bool):
        self.persistent_missing = persistent_missing
        self.calls: list[dict[str, object]] = []
        self.history_calls: list[str] = []
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
                if self.persistent_missing:
                    return _Response([])
                return _Response(_ticker(DJTB))
            self.phase_trace.append("bulk_ticker")
            return _Response([_ticker(symbol, 500_000.0) for symbol in EXPECTED_SYMBOLS[:-1]])

        if "ticker/bookTicker" in url:
            if "symbol=" in url:
                self.phase_trace.append("targeted_book")
                if self.persistent_missing:
                    return _Response([])
                return _Response(_book(DJTB))
            self.phase_trace.append("bulk_book")
            return _Response([_book(symbol) for symbol in EXPECTED_SYMBOLS[:-1]])

        if "/klines?" in url:
            params = dict(part.split("=", 1) for part in url.split("?", 1)[1].split("&"))
            symbol = params["symbol"]
            interval = params["interval"]
            self.phase_trace.append(f"history:{symbol}:{interval}")
            self.history_calls.append(symbol)
            if self.persistent_missing:
                raise AssertionError(f"first_divergence=unexpected history request for unresolved {DJTB}")
            return _Response(_history_payload())

        raise AssertionError(f"first_divergence=unexpected endpoint {url}")

    def targeted_symbols(self, endpoint: str):
        return [
            call["url"]
            for call in self.calls
            if endpoint in str(call["url"]) and "symbol=" in str(call["url"])
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

    def test_real_paper8h_create_recovers_475_of_476_djtb_with_targeted_metadata(self):
        import tools.orion_paper_8h_runner as runner_module

        network = _PaperNetwork(persistent_missing=False)
        lifecycle = Mock()
        stream = Mock()
        stream.set_symbols.return_value = False

        with tempfile.TemporaryDirectory() as tmp:
            config = self._config(runner_module, Path(tmp) / "run")
            with patch("providers.binance_opportunity_source.urlopen", side_effect=network), patch(
                "tools.orion_paper_8h_runner.DynamicMarketStream", return_value=stream
            ), patch("tools.orion_paper_8h_runner.PaperRealtimeLifecycle", return_value=lifecycle) as lifecycle_factory:
                runner = runner_module.Paper8HRunner.create(config)

            self.assertIsNotNone(runner, "first_divergence=create() did not return a runner")
            self.assertEqual(len(runner.pipeline.discovery.last_bootstrap.expected_symbols), 476)
            self.assertEqual(len(runner.pipeline.discovery.last_bootstrap.received_symbols), 476)
            self.assertEqual(runner.pipeline.discovery.last_bootstrap.missing_symbols, ())

            targeted_ticker = network.targeted_symbols("ticker/24hr")
            targeted_book = network.targeted_symbols("ticker/bookTicker")
            self.assertEqual(targeted_ticker, [next(url for url in targeted_ticker if DJTB in url)])
            self.assertEqual(targeted_book, [next(url for url in targeted_book if DJTB in url)])
            self.assertEqual(network.history_calls.count(DJTB), 1, "first_divergence=DJTB history was not acquired exactly once")
            self.assertIn("targeted_ticker", network.phase_trace)
            self.assertIn("targeted_book", network.phase_trace)
            self.assertIn(f"history:{DJTB}:1d", network.phase_trace)

            reconciliation_events = [
                event for event in runner.pipeline.discovery.last_reconciliation_events if event["symbol"] == DJTB
            ]
            self.assertEqual(len(reconciliation_events), 1, "first_divergence=unexpected reconciliation count")
            event = reconciliation_events[0]
            self.assertEqual(event["bulk_ticker_state"], "absent")
            self.assertEqual(event["bulk_book_state"], "absent")
            self.assertEqual(event["targeted_ticker_state"], "present")
            self.assertEqual(event["targeted_book_state"], "present")
            self.assertTrue(event["needs_history"])
            self.assertEqual(event["history_outcome"], "success")
            self.assertEqual(event["final_disposition"], "eligible")
            lifecycle_factory.assert_called_once()

            # The runtime object was created only after the real Paper8HRunner.create composition
            # completed discovery. We intentionally do not call runner.run().
            self.assertIs(runner.supervisor.runtime, lifecycle)

    def test_real_paper8h_create_blocks_runtime_after_reconciliation_exhaustion(self):
        import tools.orion_paper_8h_runner as runner_module

        network = _PaperNetwork(persistent_missing=True)
        lifecycle_factory = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config(runner_module, Path(tmp) / "run")
            with patch("providers.binance_opportunity_source.urlopen", side_effect=network), patch.object(
                runner_module, "PaperRealtimeLifecycle", lifecycle_factory
            ):
                with self.assertRaisesRegex(RuntimeError, "missing=DJTBUSDT"):
                    runner_module.Paper8HRunner.create(config)

            self.assertEqual(network.targeted_symbols("ticker/24hr").__len__(), 2)
            self.assertEqual(network.targeted_symbols("ticker/bookTicker").__len__(), 2)
            self.assertEqual(network.history_calls, [], "first_divergence=history ran while DJTBUSDT remained unresolved")
            lifecycle_factory.assert_not_called()

    def test_exact_stage_trace_for_recovery_has_no_mapping_or_history_gap(self):
        import tools.orion_paper_8h_runner as runner_module

        network = _PaperNetwork(persistent_missing=False)
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config(runner_module, Path(tmp) / "run")
            with patch("providers.binance_opportunity_source.urlopen", side_effect=network), patch(
                "tools.orion_paper_8h_runner.PaperRealtimeLifecycle", return_value=Mock()
            ):
                runner = runner_module.Paper8HRunner.create(config)

            bootstrap = runner.pipeline.discovery.last_bootstrap
            self.assertEqual((len(bootstrap.expected_symbols), len(bootstrap.received_symbols)), (476, 476))
            self.assertEqual(bootstrap.missing_symbols, ())
            self.assertEqual(bootstrap.source_status, "complete")
            self.assertIn("targeted_ticker", network.phase_trace, "first_divergence=targeted ticker never invoked")
            self.assertIn("targeted_book", network.phase_trace, "first_divergence=targeted book never invoked")
            self.assertIn(f"history:{DJTB}:1d", network.phase_trace, "first_divergence=DJTB history never invoked")


if __name__ == "__main__":
    unittest.main()
