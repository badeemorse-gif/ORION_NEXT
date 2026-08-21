from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from integration.paper_runtime_supervisor import PaperRuntimeSupervisor
from models.market_event import MarketEvent, MarketEventType
from models.order_position_lifecycle import ExitReason, OrderState, PositionState
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
        runtime = PaperRuntimeSupervisor()
        entry = runtime.submit_signal(snapshot(generated_at=t0), now=t0)
        self.assertEqual(runtime.process_market_event(market(100.0, t0 + timedelta(seconds=1), "entry-fill")), (entry.order_id,))
        position = runtime.active_positions[0]
        return runtime, t0, entry, position

    def test_exit_creation_and_fill_are_recovered_with_same_order_id(self) -> None:
        runtime, t0, _, position = self._open_long()
        exit_id = runtime.exit_position(symbol="BTCUSDT", price=110.0, now=t0 + timedelta(seconds=2), reason=ExitReason.TAKE_PROFIT)
        recovered = runtime.recover()
        self.assertEqual(exit_id, f"EXIT-{position.position_id}")
        self.assertEqual(recovered.runtime.orders.get(exit_id).state, OrderState.FILLED)
        self.assertEqual(recovered.runtime.orders.get(exit_id).fill.fill_id, f"FILL-{exit_id}")

    def test_exit_closes_same_position_after_recovery(self) -> None:
        runtime, t0, _, position = self._open_long()
        runtime.exit_position(symbol="BTCUSDT", price=110.0, now=t0 + timedelta(seconds=2), reason=ExitReason.TAKE_PROFIT)
        recovered = runtime.recover()
        self.assertEqual(recovered.runtime.positions.get(position.position_id).state, PositionState.CLOSED)
        self.assertIsNone(recovered.active_positions)

    def test_exit_recovery_preserves_account_and_realized_pnl(self) -> None:
        runtime, t0, _, _ = self._open_long()
        runtime.exit_position(symbol="BTCUSDT", price=110.0, now=t0 + timedelta(seconds=2), reason=ExitReason.TAKE_PROFIT)
        original_account = runtime.replay_account()
        recovered_account = runtime.recover().replay_account()
        self.assertEqual(recovered_account, original_account)
        self.assertEqual(recovered_account.realized_pnl, original_account.realized_pnl)

    def test_exit_recovery_replay_state_is_identical(self) -> None:
        runtime, t0, _, _ = self._open_long()
        runtime.exit_position(symbol="BTCUSDT", price=110.0, now=t0 + timedelta(seconds=2), reason=ExitReason.TAKE_PROFIT)
        recovered = runtime.recover()
        self.assertEqual(recovered.replay_state(), runtime.replay_state())

    def test_recover_twice_does_not_duplicate_exit_order_or_ledger(self) -> None:
        runtime, t0, _, position = self._open_long()
        exit_id = runtime.exit_position(symbol="BTCUSDT", price=110.0, now=t0 + timedelta(seconds=2), reason=ExitReason.TAKE_PROFIT)
        recovered_once = runtime.recover()
        recovered_twice = recovered_once.recover()
        self.assertEqual(recovered_once.replay_state(), recovered_twice.replay_state())
        exit_orders_once = [event for event in recovered_once.runtime.orders.events if event.aggregate_id == exit_id]
        exit_orders_twice = [event for event in recovered_twice.runtime.orders.events if event.aggregate_id == exit_id]
        self.assertEqual(len(exit_orders_once), 2)
        self.assertEqual(len(exit_orders_twice), 2)
        exit_ledger_once = [event for event in recovered_once.runtime.ledger.events if event.payload.get("order_id") == exit_id]
        exit_ledger_twice = [event for event in recovered_twice.runtime.ledger.events if event.payload.get("order_id") == exit_id]
        self.assertEqual(len(exit_ledger_once), len(exit_ledger_twice))
        self.assertEqual(position.position_id, exit_id.removeprefix("EXIT-") )

    def test_exit_journal_contains_canonical_identity_and_fill_data(self) -> None:
        runtime, t0, _, position = self._open_long()
        exit_id = runtime.exit_position(symbol="BTCUSDT", price=110.0, now=t0 + timedelta(seconds=2), reason=ExitReason.TAKE_PROFIT)
        exit_operations = [operation for operation in runtime._operations if operation[0] == "exit"]
        self.assertEqual(len(exit_operations), 1)
        data = exit_operations[0][1]
        self.assertEqual(data["order_id"], exit_id)
        self.assertEqual(data["fill_id"], f"FILL-{exit_id}")
        self.assertEqual(data["position_id"], position.position_id)
        self.assertEqual(data["position_action"], "EXIT")
        self.assertEqual(data["quantity"], 1.0)
        self.assertEqual(data["price"], 110.0)
        self.assertEqual(data["reason"], ExitReason.TAKE_PROFIT)


if __name__ == "__main__":
    unittest.main()
