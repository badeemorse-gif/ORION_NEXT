from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from integration.paper_realtime_lifecycle import PaperRealtimeLifecycle
from integration.paper_runtime_supervisor import PaperRuntimeSupervisor
from models.market_event import MarketEvent, MarketEventType
from models.opportunity import MarketMetrics, OpportunityCandidate, OpportunityCandidateSet
from models.paper_capital import PaperLedger
from tools.orion_paper_8h_runner import (
    DynamicMarketStream,
    JsonlRunLog,
    Paper8HConfig,
    Paper8HRunner,
    parse_args,
)

UTC = timezone.utc


def trade_event(symbol: str, price: float, event_id: str, timestamp: datetime) -> MarketEvent:
    return MarketEvent(symbol=symbol, event_timestamp=timestamp, event_type=MarketEventType.TRADE, payload={"price": price}, source_event_id=event_id)


def candle_event(symbol: str, price: float, event_id: str, timestamp: datetime) -> MarketEvent:
    return MarketEvent(symbol=symbol, event_timestamp=timestamp, event_type=MarketEventType.CANDLE_CLOSE, payload={"close": price, "price": price, "timeframe": "1m", "is_closed": True}, source_event_id=event_id)


class FakeDecisionContext:
    def build(self, symbol: str):
        return {"health_score": 100.0, "trade_mode": "FULL_ANALYSIS"}


class FakeOpportunity:
    def __init__(self, symbols=("BTCUSDT",)):
        self.symbols_sequence = [tuple(symbols)]
        self.calls = 0

    def discover(self, top_n=None):
        symbols = self.symbols_sequence[min(self.calls, len(self.symbols_sequence) - 1)]
        self.calls += 1
        candidates = tuple(
            OpportunityCandidate(symbol=s, opportunity_score=90.0 - i, rank=i + 1, metrics=MarketMetrics(s, 200_000_000.0, 0.03, None, True, 100.0), eligibility_reasons=())
            for i, s in enumerate(symbols)
        )
        return OpportunityCandidateSet(candidates=candidates, top_n=top_n or len(candidates))


class TestPaper8HConfig(unittest.TestCase):
    def test_default_is_dynamic_and_uses_top_n(self):
        config = Paper8HConfig()
        self.assertTrue(config.dynamic_universe)
        self.assertEqual(config.symbols, ())
        self.assertEqual(config.top_n, 10)
        self.assertEqual(config.duration_hours, 8.0)
        self.assertEqual(config.starting_capital, 200.0)

    def test_fixed_override_is_explicit(self):
        config = Paper8HConfig(dynamic_universe=False, symbols=("BTCUSDT",), top_n=1)
        self.assertFalse(config.dynamic_universe)
        with self.assertRaises(ValueError):
            Paper8HConfig(dynamic_universe=True, symbols=("BTCUSDT",))
        with self.assertRaises(ValueError):
            Paper8HConfig(dynamic_universe=False, symbols=())

    def test_cli_defaults_to_dynamic_and_accepts_top_n(self):
        args = parse_args(["--top-n", "3"])
        self.assertEqual(args.universe, "dynamic")
        self.assertEqual(args.top_n, 3)
        self.assertEqual(args.symbols, "")


class TestDynamicMarketStream(unittest.TestCase):
    def test_subscription_changes_only_when_top_n_changes(self):
        stream = DynamicMarketStream(("BTCUSDT", "ETHUSDT"))
        self.assertFalse(stream.set_symbols(("ETHUSDT", "BTCUSDT")))
        self.assertTrue(stream.set_symbols(("SOLUSDT", "BTCUSDT")))
        self.assertEqual(stream.symbols, ("BTCUSDT", "SOLUSDT"))


class TestPaper8HRunnerE2E(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        config = Paper8HConfig(output_dir=Path(self.tempdir.name))
        runtime = PaperRealtimeLifecycle(ledger=PaperLedger(starting_equity=200.0))
        supervisor = PaperRuntimeSupervisor(runtime=runtime)
        self.opportunity = FakeOpportunity()
        self.runner = Paper8HRunner(
            config=config,
            stream=DynamicMarketStream(("BTCUSDT",)),
            supervisor=supervisor,
            opportunity=self.opportunity,
            log=JsonlRunLog(Path(self.tempdir.name) / "events.jsonl"),
            decision_context=FakeDecisionContext(),
            previous_top_symbols=("BTCUSDT",),
        )
        self.runner.log.open()

    async def asyncTearDown(self):
        self.runner.log.close()
        self.tempdir.cleanup()

    async def test_dynamic_candidate_replacement_refreshes_stream_without_touching_position(self):
        self.opportunity.symbols_sequence = [("BTCUSDT",), ("ETHUSDT",)]
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        self.runner.last_prices.update({"BTCUSDT": 100.0, "ETHUSDT": 100.0})
        await self.runner._on_market_event(candle_event("BTCUSDT", 100.0, "c1", t0))
        self.assertEqual(self.runner.stream.symbols, ("BTCUSDT",))
        await self.runner._on_market_event(candle_event("BTCUSDT", 100.0, "c2", t0.replace(minute=1)))
        self.assertEqual(self.runner.stream.symbols, ("ETHUSDT",))

    async def test_actual_runner_path_can_create_pending_buy(self):
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        self.runner.last_prices["BTCUSDT"] = 100.0
        await self.runner._on_market_event(candle_event("BTCUSDT", 100.0, "candle-1", t0))
        active = self.runner.supervisor.runtime.pending.pending()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].side.value, "BUY")

    async def test_market_event_to_fill_to_position_to_ledger_to_recovery(self):
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        await self.runner._on_market_event(candle_event("BTCUSDT", 100.0, "candle-1", t0))
        await self.runner._on_market_event(trade_event("BTCUSDT", 99.0, "trade-1", t0.replace(second=10)))
        self.assertEqual(len(self.runner.supervisor.active_positions), 1)
        state = self.runner.supervisor.runtime.ledger.replay()
        self.assertGreater(state.position("BTCUSDT").quantity, 0.0)
        original = self.runner.supervisor.replay_state()
        recovered = self.runner.supervisor.recover()
        self.assertEqual(original, recovered.replay_state())
        self.assertEqual(recovered.replay_state(), recovered.recover().replay_state())

    async def test_duplicate_market_event_is_suppressed(self):
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        event = trade_event("BTCUSDT", 100.0, "duplicate", t0)
        await self.runner._on_market_event(event)
        before = len(self.runner.supervisor.runtime.ledger.events)
        await self.runner._on_market_event(event)
        self.assertEqual(len(self.runner.supervisor.runtime.ledger.events), before)
        self.assertEqual(self.runner.supervisor.health.duplicate_events, 1)


class TestPaper8HLog(unittest.TestCase):
    def test_jsonl_log_persists_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            log = JsonlRunLog(path)
            log.open(); log.write("run_start", starting_equity=200.0); log.close()
            content = path.read_text(encoding="utf-8")
            self.assertIn("run_start", content)
            self.assertIn("200.0", content)


if __name__ == "__main__":
    unittest.main()
