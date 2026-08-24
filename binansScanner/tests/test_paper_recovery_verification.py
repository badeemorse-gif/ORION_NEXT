from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from integration.paper_recovery_verification import verify_recovery
from integration.paper_runtime_supervisor import PaperRuntimeSupervisor
from tools.orion_paper_8h_runner import JsonlRunLog, Paper8HConfig, Paper8HRunner
from models.capital_management import CapitalMode
from models.market_event import MarketEvent, MarketEventType
from models.paper_capital import PaperLedger
from models.signal_snapshot import SignalIdentity, SignalSnapshot

UTC = timezone.utc


def market(index: int) -> MarketEvent:
    return MarketEvent(
        symbol="BTCUSDT",
        event_timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=UTC) + timedelta(seconds=index),
        event_type=MarketEventType.TRADE,
        payload={"price": 100.0},
        source_event_id=f"event-{index}",
    )


def snapshot(now: datetime) -> SignalSnapshot:
    return SignalSnapshot(
        identity=SignalIdentity("BTCUSDT", "PAPER", "ENTRY"),
        version=1,
        direction="BUY",
        decision="FAVORABLE",
        confidence=80.0,
        entry_plan={"entry_price": 100.0, "quantity": 1.0},
        generated_at=now,
        valid_until=now + timedelta(minutes=15),
        quality=90.0,
    )


class TestPaperRecoveryVerification(unittest.TestCase):
    def test_valid_no_trade_high_event_count_is_deterministic(self) -> None:
        with TemporaryDirectory() as tmp:
            supervisor = PaperRuntimeSupervisor(control_path=Path(tmp) / "control.json")
            for index in range(1000):
                supervisor.process_market_event(market(index))
            config = Paper8HConfig(starting_capital=50.0, output_dir=Path(tmp) / "run", duration_hours=1.0)
            runner = Paper8HRunner(config, object(), supervisor, object(), JsonlRunLog(Path(tmp) / "events.jsonl"), peak_equity=50.0)
            result = runner._finalize(SimpleNamespace(stats=SimpleNamespace(reconnects=0, duplicates=0)))
            self.assertTrue(result["runtime_replay_equal"])
            self.assertTrue(result["runtime_repeat_recovery_equal"])
            self.assertTrue(result["capital_replay_equal"])
            self.assertTrue(result["paper_only_verification"])
            self.assertEqual(result["recovery_failure_reasons"], ())

    def test_recovery_verifier_identifies_runtime_mismatch_independently(self) -> None:
        result = verify_recovery(
            canonical_runtime=("RUNNING", ("ORDER-A",)),
            recovered_runtime=("RUNNING", ("ORDER-B",)),
            repeated_runtime=("RUNNING", ("ORDER-B",)),
            canonical_capital={"reserved_capital": 0.0},
            recovered_capital={"reserved_capital": 0.0},
            repeated_capital={"reserved_capital": 0.0},
            paper_only=True,
        )
        self.assertFalse(result.runtime_replay_equal)
        self.assertTrue(result.runtime_repeat_recovery_equal)
        self.assertTrue(result.capital_replay_equal)
        self.assertIn("runtime_replay[1] differs", result.failure_reasons[0])

    def test_recovery_verifier_identifies_repeat_mismatch_independently(self) -> None:
        result = verify_recovery(
            canonical_runtime=("RUNNING", ("ORDER-A",)),
            recovered_runtime=("RUNNING", ("ORDER-A",)),
            repeated_runtime=("RUNNING", ("ORDER-B",)),
            canonical_capital={"reserved_capital": 0.0},
            recovered_capital={"reserved_capital": 0.0},
            repeated_capital={"reserved_capital": 0.0},
            paper_only=True,
        )
        self.assertTrue(result.runtime_replay_equal)
        self.assertFalse(result.runtime_repeat_recovery_equal)
        self.assertTrue(result.capital_replay_equal)
        self.assertIn("runtime_repeat_recovery[1] differs", result.failure_reasons[0])

    def test_recovery_verifier_identifies_capital_mismatch_independently(self) -> None:
        result = verify_recovery(
            canonical_runtime=("RUNNING", ()),
            recovered_runtime=("RUNNING", ()),
            repeated_runtime=("RUNNING", ()),
            canonical_capital={"reserved_capital": 1.0},
            recovered_capital={"reserved_capital": 2.0},
            repeated_capital={"reserved_capital": 2.0},
            paper_only=True,
        )
        self.assertTrue(result.runtime_replay_equal)
        self.assertTrue(result.runtime_repeat_recovery_equal)
        self.assertFalse(result.capital_replay_equal)
        self.assertIn("capital_replay.reserved_capital differs", result.failure_reasons[0])

    def test_paper_only_failure_is_independent_invariant(self) -> None:
        result = verify_recovery(
            canonical_runtime=(), recovered_runtime=(), repeated_runtime=(),
            canonical_capital={}, recovered_capital={}, repeated_capital={},
            paper_only=False,
        )
        self.assertFalse(result.paper_only)
        self.assertFalse(result.passed)
        self.assertEqual(result.failure_reasons, ("paper_only=false",))


if __name__ == "__main__":
    unittest.main()
