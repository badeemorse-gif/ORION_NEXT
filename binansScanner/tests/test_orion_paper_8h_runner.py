from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from integration.paper_realtime_lifecycle import PaperRealtimeLifecycle
from integration.paper_runtime_supervisor import PaperRuntimeSupervisor
from models.market_event import MarketEvent, MarketEventType
from models.opportunity import MarketMetrics, OpportunityCandidate, OpportunityCandidateSet
from models.paper_capital import PaperLedger
from tools.orion_paper_8h_runner import JsonlRunLog, Paper8HConfig, Paper8HRunner, canonical_decision

UTC = timezone.utc


def trade_event(price: float, event_id: str, timestamp: datetime) -> MarketEvent:
    return MarketEvent(
        symbol="BTCUSDT",
        event_timestamp=timestamp,
        event_type=MarketEventType.TRADE,
        payload={"price": price},
        source_event_id=event_id,
    )


def candle_event(price: float, event_id: str, timestamp: datetime) -> MarketEvent:
    return MarketEvent(
        symbol="BTCUSDT",
        event_timestamp=timestamp,
        event_type=MarketEventType.CANDLE_CLOSE,
        payload={"close": price, "price": price, "timeframe": "1m", "is_closed": True},
        source_event_id=event_id,
    )


class FakeOpportunity:
    def __init__(self, score: float = 90.0):
        self.score = score

    def discover(self, top_n=None):
        metrics = MarketMetrics("BTCUSDT", 200_000_000.0, 0.03, None, True)
        candidate = OpportunityCandidate(
            symbol="BTCUSDT",
            opportunity_score=self.score,
            rank=1,
            metrics=metrics,
            eligibility_reasons=(),
        )
        return OpportunityCandidateSet(candidates=(candidate,), top_n=top_n or 1)


class FakeDecisionContext:
    def __init__(self, context):
        self.context = context

    def build(self, symbol):
        return self.context


class TestPaper8HConfig(unittest.TestCase):
    def test_default_contract_is_eight_hours_and_two_hundred(self):
        config = Paper8HConfig()
        self.assertEqual(config.duration_hours, 8.0)
        self.assertEqual(config.starting_capital, 200.0)
        self.assertEqual(config.symbols, ("BTCUSDT",))
        self.assertEqual(config.max_notional_pct, 20.0)

    def test_invalid_duration_fails_closed(self):
        with self.assertRaises(ValueError):
            Paper8HConfig(duration_hours=0)

    def test_invalid_notional_limit_fails_closed(self):
        with self.assertRaises(ValueError):
            Paper8HConfig(max_notional_pct=100.1)


class TestCanonicalDecisionAdapter(unittest.TestCase):
    def _candidate(self, score: float) -> OpportunityCandidate:
        return OpportunityCandidate(
            symbol="BTCUSDT",
            opportunity_score=score,
            rank=1,
            metrics=MarketMetrics("BTCUSDT", 200_000_000.0, 0.03, None, True),
            eligibility_reasons=(),
        )

    def test_tradeable_canonical_context_and_d1_score_produce_buy(self):
        decision = canonical_decision(
            self._candidate(85.0),
            {"health_score": 90.0, "trade_mode": "FULL_ANALYSIS"},
        )
        self.assertEqual(decision["decision"], "BUY")
        self.assertEqual(decision["decision_score"], 85.0)

    def test_legitimate_blocking_context_remains_blocked(self):
        decision = canonical_decision(
            self._candidate(95.0),
            {"health_score": 40.0, "trade_mode": "FULL_ANALYSIS"},
        )
        self.assertEqual(decision["decision"], "REJECT")

    def test_actual_d1_score_changes_decision_with_same_context(self):
        context = {"health_score": 90.0, "trade_mode": "FULL_ANALYSIS"}
        below_entry = canonical_decision(self._candidate(84.0), context)
        at_entry = canonical_decision(self._candidate(85.0), context)
        self.assertNotEqual(below_entry["decision"], at_entry["decision"])
        self.assertEqual(at_entry["decision"], "BUY")

    def test_context_is_required(self):
        with self.assertRaises(ValueError):
            canonical_decision(self._candidate(90.0))


class TestPaper8HRunnerE2E(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        config = Paper8HConfig(output_dir=Path(self.tempdir.name))
        runtime = PaperRealtimeLifecycle(ledger=PaperLedger(starting_equity=200.0))
        supervisor = PaperRuntimeSupervisor(runtime=runtime)
        self.runner = Paper8HRunner(
            config=config,
            stream=object(),
            supervisor=supervisor,
            opportunity=FakeOpportunity(),
            log=JsonlRunLog(Path(self.tempdir.name) / "events.jsonl"),
            decision_context=FakeDecisionContext({"health_score": 90.0, "trade_mode": "FULL_ANALYSIS"}),
        )
        self.runner.log.open()

    async def asyncTearDown(self):
        self.runner.log.close()
        self.tempdir.cleanup()

    async def test_actual_decision_path_produces_buy_signal(self):
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        self.runner.last_prices["BTCUSDT"] = 100.0
        await self.runner._on_market_event(candle_event(100.0, "candle-1", t0))
        active = self.runner.supervisor.runtime.pending.pending()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].side.value, "BUY")
        self.assertEqual(active[0].entry_price, 100.0)

    async def test_market_event_to_fill_to_position_to_ledger_to_recovery(self):
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        await self.runner._on_market_event(candle_event(100.0, "candle-1", t0))
        await self.runner._on_market_event(trade_event(99.0, "trade-1", t0.replace(second=10)))
        self.assertEqual(len(self.runner.supervisor.active_positions), 1)
        state = self.runner.supervisor.runtime.ledger.replay()
        self.assertAlmostEqual(state.starting_equity, 200.0)
        self.assertGreater(state.position("BTCUSDT").quantity, 0.0)

        original = self.runner.supervisor.replay_state()
        recovered = self.runner.supervisor.recover()
        recovered_twice = recovered.recover()
        self.assertEqual(original, recovered.replay_state())
        self.assertEqual(recovered.replay_state(), recovered_twice.replay_state())

    async def test_buy_fill_sell_exit_realized_pnl_and_replay(self):
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        await self.runner._on_market_event(candle_event(100.0, "entry", t0))
        await self.runner._on_market_event(trade_event(99.0, "entry-fill", t0.replace(second=10)))
        self.assertEqual(len(self.runner.supervisor.active_positions), 1)
        before = self.runner.supervisor.runtime.ledger.replay().realized_pnl
        exit_order = self.runner.supervisor.exit_position(symbol="BTCUSDT", price=105.0, now=t0.replace(second=20))
        self.assertTrue(exit_order.startswith("EXIT-POS-"))
        after = self.runner.supervisor.runtime.ledger.replay()
        self.assertEqual(len(self.runner.supervisor.active_positions), 0)
        self.assertNotEqual(after.realized_pnl, before)
        original = self.runner.supervisor.replay_state()
        recovered = self.runner.supervisor.recover()
        self.assertEqual(original, recovered.replay_state())

    async def test_duplicate_market_event_is_suppressed_by_supervisor(self):
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        event = trade_event(100.0, "duplicate", t0)
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
            log.open()
            log.write("run_start", starting_equity=200.0)
            log.close()
            content = path.read_text(encoding="utf-8")
            self.assertIn("run_start", content)
            self.assertIn("200.0", content)


if __name__ == "__main__":
    unittest.main()
