from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

# Canonical repository test arrangement: tests execute with binansScanner as
# the working directory, while integration.paper_runtime_supervisor imports
# repository-level tools. Add only the repository root for this test module;
# do not alter CI/PYTHONPATH or production runtime behavior.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from integration.paper_runtime_supervisor import PaperRuntimeSupervisor
from models.market_event import MarketEvent, MarketEventType
from models.order_position_lifecycle import ExitReason, OrderState, PositionState
from models.paper_capital import LedgerEventType
from models.signal_snapshot import SignalIdentity, SignalSnapshot

UTC = timezone.utc


def snapshot(*, generated_at: datetime, price: float = 100.0) -> SignalSnapshot:
    return SignalSnapshot(
        identity=SignalIdentity("BTCUSDT", "PAPER", "ENTRY"),
        version=1,
        direction="BUY",
        decision="FAVORABLE",
        confidence=90.0,
        entry_plan={"entry_price": price, "quantity": 1.0},
        generated_at=generated_at,
        valid_until=generated_at + timedelta(minutes=15),
        quality=90.0,
    )


def market(price: float, timestamp: datetime, source_id: str) -> MarketEvent:
    return MarketEvent(
        symbol="BTCUSDT",
        event_timestamp=timestamp,
        event_type=MarketEventType.TRADE,
        payload={"price": price},
        source_event_id=source_id,
    )


class TestExitRecoveryDeterminism(unittest.TestCase):
    def _open_long(self):
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        supervisor = PaperRuntimeSupervisor()
        entry = supervisor.submit_signal(snapshot(generated_at=t0), now=t0)
        self.assertEqual(supervisor.process_market_event(market(100.0, t0 + timedelta(seconds=1), "entry-fill")), (entry.order_id,))
        position = supervisor.active_positions[0]
        return supervisor, t0, entry, position

    def test_exit_creation_and_fill_are_recovered_with_same_order_id(self) -> None:
        supervisor, t0, _, position = self._open_long()
        exit_id = supervisor.exit_position(symbol="BTCUSDT", price=110.0, now=t0 + timedelta(seconds=2), reason=ExitReason.TAKE_PROFIT)
        recovered = supervisor.recover()
        self.assertEqual(exit_id, f"EXIT-{position.position_id}")
        self.assertEqual(recovered.runtime.orders.get(exit_id).state, OrderState.FILLED)
        self.assertEqual(recovered.runtime.orders.get(exit_id).fill.fill_id, f"FILL-{exit_id}")

    def test_exit_closes_same_position_after_recovery(self) -> None:
        supervisor, t0, _, position = self._open_long()
        supervisor.exit_position(symbol="BTCUSDT", price=110.0, now=t0 + timedelta(seconds=2), reason=ExitReason.TAKE_PROFIT)
        recovered = supervisor.recover()
        self.assertEqual(recovered.runtime.positions.get(position.position_id).state, PositionState.CLOSED)
        self.assertEqual(recovered.active_positions, ())

    def test_exit_recovery_preserves_account_and_realized_pnl(self) -> None:
        supervisor, t0, _, _ = self._open_long()
        supervisor.exit_position(symbol="BTCUSDT", price=110.0, now=t0 + timedelta(seconds=2), reason=ExitReason.TAKE_PROFIT)
        original_account = supervisor.replay_account()
        recovered_account = supervisor.recover().replay_account()
        self.assertEqual(recovered_account, original_account)
        self.assertEqual(recovered_account.realized_pnl, original_account.realized_pnl)

    def test_exit_recovery_replay_state_is_identical(self) -> None:
        supervisor, t0, _, _ = self._open_long()
        supervisor.exit_position(symbol="BTCUSDT", price=110.0, now=t0 + timedelta(seconds=2), reason=ExitReason.TAKE_PROFIT)
        recovered = supervisor.recover()
        self.assertEqual(recovered.replay_state(), supervisor.replay_state())

    def test_recover_twice_does_not_duplicate_exit_order_or_ledger(self) -> None:
        supervisor, t0, _, position = self._open_long()
        exit_id = supervisor.exit_position(symbol="BTCUSDT", price=110.0, now=t0 + timedelta(seconds=2), reason=ExitReason.TAKE_PROFIT)
        recovered_once = supervisor.recover()
        recovered_twice = recovered_once.recover()
        self.assertEqual(recovered_once.replay_state(), recovered_twice.replay_state())
        exit_orders_once = [event for event in recovered_once.runtime.orders.events if event.aggregate_id == exit_id]
        exit_orders_twice = [event for event in recovered_twice.runtime.orders.events if event.aggregate_id == exit_id]
        self.assertEqual(len(exit_orders_once), 2)
        self.assertEqual(len(exit_orders_twice), 2)
        self.assertEqual(recovered_once.runtime.ledger.events, recovered_twice.runtime.ledger.events)
        self.assertEqual(position.position_id, exit_id.removeprefix("EXIT-"))
        self.assertEqual(sum(event.event_type is LedgerEventType.FILL and event.side is not None and event.symbol == "BTCUSDT" for event in recovered_once.runtime.ledger.events), 2)

    def test_exit_journal_contains_canonical_identity_and_fill_data(self) -> None:
        supervisor, t0, _, position = self._open_long()
        exit_id = supervisor.exit_position(symbol="BTCUSDT", price=110.0, now=t0 + timedelta(seconds=2), reason=ExitReason.TAKE_PROFIT)
        exit_operations = [operation for operation in supervisor._operations if operation[0] == "exit"]
        self.assertEqual(len(exit_operations), 1)
        data = exit_operations[0][1]
        self.assertEqual(data["order_id"], exit_id)
        self.assertEqual(data["fill_id"], f"FILL-{exit_id}")
        self.assertEqual(data["position_id"], position.position_id)
        self.assertEqual(data["position_action"], "EXIT")
        self.assertEqual(data["quantity"], 1.0)
        self.assertEqual(data["price"], 110.0)
        self.assertEqual(data["reason"], ExitReason.TAKE_PROFIT)
        self.assertEqual(len(data["order_events"]), 2)
        self.assertEqual(len(data["position_events"]), 1)
        self.assertGreaterEqual(len(data["ledger_events"]), 1)


if __name__ == "__main__":
    unittest.main()
