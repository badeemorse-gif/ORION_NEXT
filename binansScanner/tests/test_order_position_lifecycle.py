from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from models.execution import ExecutionRequest, ExecutionResult, ExecutionSide, ExecutionStatus
from models.lifecycle import (
    DuplicatePositionError,
    ExecutionLifecycleBridge,
    ExitReason,
    FillMetadata,
    InvalidTransitionError,
    LifecycleEventStore,
    LifecycleEvent,
    OrderLifecycle,
    OrderState,
    PositionBook,
    PositionState,
    ReplayError,
)


class TestOrderLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.lifecycle = OrderLifecycle()

    def _fill(self, *, fill_id: str = "F-1", quantity: float = 2.0, price: float = 101.0) -> FillMetadata:
        return FillMetadata(fill_id, quantity, price, self.t0 + timedelta(seconds=1))

    def test_pending_to_filled_persists_exactly_one_fill(self) -> None:
        order = self.lifecycle.create(
            order_id="O-1",
            symbol="BTCUSDT",
            side=ExecutionSide.BUY,
            quantity=2.0,
            price=100.0,
            created_at=self.t0,
        )
        self.assertEqual(order.state, OrderState.PENDING)

        filled = self.lifecycle.fill("O-1", self._fill())
        self.assertEqual(filled.state, OrderState.FILLED)
        self.assertEqual(filled.fill.fill_id, "F-1")
        self.assertEqual(filled.fill.quantity, 2.0)
        self.assertEqual(filled.fill.price, 101.0)
        self.assertEqual(len(self.lifecycle.history("O-1")), 2)
        self.assertEqual(self.lifecycle.history("O-1")[1].event_type, "ORDER_FILLED")

        with self.assertRaises(InvalidTransitionError):
            self.lifecycle.fill("O-1", self._fill(fill_id="F-2"))

    def test_invalid_terminal_transitions_are_rejected(self) -> None:
        self.lifecycle.create(
            order_id="O-1",
            symbol="BTCUSDT",
            side=ExecutionSide.BUY,
            quantity=1.0,
            price=100.0,
            created_at=self.t0,
        )
        self.lifecycle.cancel("O-1", reason="manual")
        with self.assertRaises(InvalidTransitionError):
            self.lifecycle.expire("O-1")

    def test_fill_quantity_must_match_pending_order(self) -> None:
        self.lifecycle.create(
            order_id="O-1",
            symbol="BTCUSDT",
            side=ExecutionSide.BUY,
            quantity=2.0,
            price=100.0,
            created_at=self.t0,
        )
        with self.assertRaisesRegex(Exception, "exactly match"):
            self.lifecycle.fill("O-1", self._fill(quantity=1.0))

    def test_order_history_replays_deterministically(self) -> None:
        self.lifecycle.create(
            order_id="O-1",
            symbol="BTCUSDT",
            side=ExecutionSide.SELL,
            quantity=3.0,
            price=200.0,
            created_at=self.t0,
        )
        self.lifecycle.fill("O-1", self._fill(quantity=3.0, price=199.0))

        replayed = OrderLifecycle(LifecycleEventStore())
        replayed.replay(self.lifecycle.history("O-1"))
        self.assertEqual(replayed.get("O-1"), self.lifecycle.get("O-1"))

    def test_event_store_rejects_non_contiguous_sequences(self) -> None:
        event = LifecycleEvent(
            event_id="E-1",
            aggregate_id="O-1",
            aggregate_type="ORDER",
            sequence=2,
            event_type="ORDER_CREATED",
            occurred_at=self.t0,
            payload={},
        )
        with self.assertRaises(ReplayError):
            LifecycleEventStore([event])


class TestPositionBook(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.fill = FillMetadata("F-1", 5.0, 100.0, self.t0, source="PAPER")
        self.book = PositionBook()

    def test_position_created_from_fill_and_duplicate_protection(self) -> None:
        position = self.book.create_from_fill(
            fill=self.fill,
            symbol="BTCUSDT",
            side=ExecutionSide.BUY,
            source_order_id="O-1",
            position_id="P-1",
        )
        self.assertEqual(position.state, PositionState.OPEN)
        self.assertEqual(position.quantity, 5.0)

        with self.assertRaises(DuplicatePositionError):
            self.book.create_from_fill(
                fill=self.fill,
                symbol="BTCUSDT",
                side=ExecutionSide.SELL,
                source_order_id="O-2",
                position_id="P-2",
            )

    def test_hold_and_reduce_transitions(self) -> None:
        self.book.create_from_fill(
            fill=self.fill,
            symbol="BTCUSDT",
            side=ExecutionSide.BUY,
            source_order_id="O-1",
            position_id="P-1",
        )
        held = self.book.hold("P-1", occurred_at=self.t0 + timedelta(seconds=1))
        self.assertEqual(held.state, PositionState.HOLD)
        reduced = self.book.reduce("P-1", 2.0, occurred_at=self.t0 + timedelta(seconds=2))
        self.assertEqual(reduced.state, PositionState.REDUCE)
        self.assertEqual(reduced.quantity, 3.0)

        with self.assertRaises(ValueError):
            self.book.reduce("P-1", 3.0)

    def test_exit_supports_all_required_reasons_and_closes(self) -> None:
        reasons = (
            ExitReason.STOP_LOSS,
            ExitReason.TAKE_PROFIT,
            ExitReason.SIGNAL_REVERSAL,
            ExitReason.RISK_EXIT,
            ExitReason.TIME_EXIT,
        )
        for index, reason in enumerate(reasons, start=1):
            book = PositionBook()
            book.create_from_fill(
                fill=self.fill,
                symbol=f"BTC{index}USDT",
                side=ExecutionSide.BUY,
                source_order_id=f"O-{index}",
                position_id=f"P-{index}",
            )
            closed = book.exit(f"P-{index}", reason=reason, occurred_at=self.t0 + timedelta(seconds=1))
            self.assertEqual(closed.state, PositionState.CLOSED)
            self.assertEqual(closed.exit_reason, reason)
            self.assertIsNotNone(closed.closed_at)
            self.assertIsNone(book.active_for_symbol(closed.symbol))

    def test_reverse_closes_old_position_then_allows_new_position(self) -> None:
        position = self.book.create_from_fill(
            fill=self.fill,
            symbol="BTCUSDT",
            side=ExecutionSide.BUY,
            source_order_id="O-1",
            position_id="P-1",
        )
        reversed_position = self.book.reverse("P-1")
        self.assertEqual(reversed_position.state, PositionState.CLOSED)
        self.assertEqual(reversed_position.exit_reason, ExitReason.SIGNAL_REVERSAL)

        new_position = self.book.create_from_fill(
            fill=self.fill,
            symbol="BTCUSDT",
            side=ExecutionSide.SELL,
            source_order_id="O-2",
            position_id="P-2",
        )
        self.assertEqual(new_position.state, PositionState.OPEN)
        self.assertEqual(self.book.active_for_symbol("BTCUSDT").position_id, "P-2")

    def test_closed_position_cannot_be_mutated(self) -> None:
        self.book.create_from_fill(
            fill=self.fill,
            symbol="BTCUSDT",
            side=ExecutionSide.BUY,
            source_order_id="O-1",
            position_id="P-1",
        )
        self.book.exit("P-1", reason=ExitReason.RISK_EXIT)
        with self.assertRaises(InvalidTransitionError):
            self.book.hold("P-1")
        with self.assertRaises(InvalidTransitionError):
            self.book.reverse("P-1")

    def test_position_history_replays_deterministically(self) -> None:
        self.book.create_from_fill(
            fill=self.fill,
            symbol="BTCUSDT",
            side=ExecutionSide.BUY,
            source_order_id="O-1",
            position_id="P-1",
        )
        self.book.hold("P-1", occurred_at=self.t0 + timedelta(seconds=1))
        self.book.reduce("P-1", 1.0, occurred_at=self.t0 + timedelta(seconds=2))
        self.book.exit("P-1", reason=ExitReason.TIME_EXIT, occurred_at=self.t0 + timedelta(seconds=3))

        replayed = PositionBook()
        replayed.replay(self.book.history("P-1"))
        self.assertEqual(replayed.get("P-1"), self.book.get("P-1"))


class TestExecutionLifecycleBridge(unittest.TestCase):
    def test_successful_execution_creates_pending_then_filled_order(self) -> None:
        created = datetime(2026, 1, 1, tzinfo=timezone.utc)
        request = ExecutionRequest(
            symbol="BTCUSDT",
            side=ExecutionSide.BUY,
            price=100.0,
            quantity=1.5,
            confidence=95.0,
            created_at=created,
        )
        result = ExecutionResult(
            request=request,
            status=ExecutionStatus.EXECUTED,
            executed_at=created + timedelta(seconds=1),
            order_id="PAPER-ORD-1",
        )
        lifecycle = OrderLifecycle()
        record = ExecutionLifecycleBridge.record_paper_execution(
            result,
            lifecycle=lifecycle,
            fill_id="F-1",
        )
        self.assertEqual(record.state, OrderState.FILLED)
        self.assertEqual([event.event_type for event in lifecycle.history("PAPER-ORD-1")], ["ORDER_CREATED", "ORDER_FILLED"])

    def test_non_executed_result_cannot_be_recorded_as_fill(self) -> None:
        result = ExecutionResult(status=ExecutionStatus.FAILED, message="nope")
        with self.assertRaises(Exception):
            ExecutionLifecycleBridge.record_paper_execution(
                result,
                lifecycle=OrderLifecycle(),
                fill_id="F-1",
            )


if __name__ == "__main__":
    unittest.main()
