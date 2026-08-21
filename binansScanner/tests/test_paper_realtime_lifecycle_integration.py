from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from integration.paper_realtime_lifecycle import PaperRealtimeLifecycle
from models.market_event import MarketEvent, MarketEventType
from models.order_position_lifecycle import ExitReason, OrderState
from models.signal_snapshot import SignalIdentity, SignalSnapshot

UTC = timezone.utc


def snapshot(*, version: int, price: float, decision: str = "FAVORABLE", direction: str = "BUY", valid_for_minutes: int = 15, generated_at: datetime | None = None) -> SignalSnapshot:
    generated_at = generated_at or datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    return SignalSnapshot(
        identity=SignalIdentity("BTCUSDT", "PAPER", "ENTRY"),
        version=version,
        direction=direction,
        decision=decision,
        confidence=80.0,
        entry_plan={"entry_price": price, "quantity": 1.0},
        generated_at=generated_at,
        valid_until=generated_at + timedelta(minutes=valid_for_minutes),
        quality=90.0,
    )


def event(price: float, timestamp: datetime, event_id: str) -> MarketEvent:
    return MarketEvent(
        symbol="BTCUSDT",
        event_timestamp=timestamp,
        event_type=MarketEventType.TRADE,
        payload={"price": price},
        source_event_id=event_id,
    )


class TestPaperRealtimeLifecycleIntegration(unittest.TestCase):
    def test_buy_100_reprice_118_old_order_never_fills(self) -> None:
        runtime = PaperRealtimeLifecycle()
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        first = runtime.submit_signal(snapshot(version=1, price=100.0, generated_at=t0), now=t0)
        t1 = t0 + timedelta(minutes=1)
        action = runtime.revalidate(intent_id=first.intent_id, snapshot=snapshot(version=2, price=118.0, generated_at=t1), market_price=120.0, now=t1)
        self.assertEqual(action.value, "REPLACE")
        self.assertEqual(runtime.orders.get(first.order_id).state, OrderState.REPLACED)
        replacement = runtime.pending.active_for_intent(first.intent_id)
        self.assertIsNotNone(replacement)
        self.assertEqual(replacement.entry_price, 118.0)
        self.assertEqual(runtime.on_market_event(event(100.0, t1 + timedelta(minutes=1), "p100")), ())
        self.assertEqual(runtime.on_market_event(event(118.0, t1 + timedelta(minutes=2), "p118")), (replacement.order_id,))
        self.assertEqual(runtime.positions.active_for_symbol("BTCUSDT").quantity, 1.0)
        self.assertEqual(len(runtime.ledger.events), 5)

    def test_replacement_has_single_active_intent_and_old_is_terminal(self) -> None:
        runtime = PaperRealtimeLifecycle()
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        first = runtime.submit_signal(snapshot(version=1, price=100.0, generated_at=t0), now=t0)
        t1 = t0 + timedelta(minutes=1)
        runtime.revalidate(intent_id=first.intent_id, snapshot=snapshot(version=2, price=118.0, generated_at=t1), market_price=120.0, now=t1)
        replacement = runtime.pending.active_for_intent(first.intent_id)
        self.assertIsNotNone(replacement)
        active = runtime.pending.pending()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].order_id, replacement.order_id)
        self.assertEqual(runtime.orders.get(first.order_id).state, OrderState.REPLACED)
        self.assertEqual(runtime.orders.history(first.order_id)[-1].event_type, "ORDER_REPLACED")

    def test_cancelled_order_cannot_fill_position_or_ledger(self) -> None:
        runtime = PaperRealtimeLifecycle()
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        first = runtime.submit_signal(snapshot(version=1, price=100.0, generated_at=t0), now=t0)
        action = runtime.revalidate(intent_id=first.intent_id, snapshot=snapshot(version=2, price=100.0, decision="WAIT", generated_at=t0 + timedelta(minutes=1)), market_price=105.0, now=t0 + timedelta(minutes=1))
        self.assertEqual(action.value, "CANCEL")
        before = len(runtime.ledger.events)
        self.assertEqual(runtime.on_market_event(event(100.0, t0 + timedelta(minutes=2), "late-cancelled")), ())
        self.assertEqual(runtime.orders.get(first.order_id).state, OrderState.CANCELLED)
        self.assertEqual(len(runtime.ledger.events), before)
        self.assertIsNone(runtime.positions.active_for_symbol("BTCUSDT"))

    def test_wait_cancels_pending(self) -> None:
        runtime = PaperRealtimeLifecycle()
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        first = runtime.submit_signal(snapshot(version=1, price=100.0, generated_at=t0), now=t0)
        action = runtime.revalidate(intent_id=first.intent_id, snapshot=snapshot(version=2, price=100.0, decision="WAIT", generated_at=t0 + timedelta(minutes=1)), market_price=105.0, now=t0 + timedelta(minutes=1))
        self.assertEqual(action.value, "CANCEL")
        self.assertEqual(runtime.orders.get(first.order_id).state, OrderState.CANCELLED)
        self.assertEqual(runtime.pending.pending(), ())

    def test_sell_signal_cancels_pending_buy(self) -> None:
        runtime = PaperRealtimeLifecycle()
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        first = runtime.submit_signal(snapshot(version=1, price=100.0, generated_at=t0), now=t0)
        action = runtime.revalidate(intent_id=first.intent_id, snapshot=snapshot(version=2, price=99.0, direction="SELL", generated_at=t0 + timedelta(minutes=1)), market_price=101.0, now=t0 + timedelta(minutes=1))
        self.assertEqual(action.value, "CANCEL")
        self.assertEqual(runtime.orders.get(first.order_id).state, OrderState.CANCELLED)

    def test_expired_signal_cancels_and_late_touch_does_not_fill(self) -> None:
        runtime = PaperRealtimeLifecycle()
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        first = runtime.submit_signal(snapshot(version=1, price=100.0, valid_for_minutes=1, generated_at=t0), now=t0)
        expired = snapshot(version=2, price=100.0, generated_at=t0 + timedelta(minutes=2))
        action = runtime.revalidate(intent_id=first.intent_id, snapshot=expired, market_price=105.0, now=t0 + timedelta(minutes=2))
        self.assertEqual(action.value, "CANCEL")
        self.assertEqual(runtime.on_market_event(event(100.0, t0 + timedelta(minutes=3), "late")), ())

    def test_open_position_blocks_uncontrolled_duplicate_intent(self) -> None:
        runtime = PaperRealtimeLifecycle()
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        first = runtime.submit_signal(snapshot(version=1, price=100.0, generated_at=t0), now=t0)
        self.assertEqual(runtime.on_market_event(event(100.0, t0 + timedelta(seconds=1), "fill")), (first.order_id,))
        with self.assertRaises(ValueError):
            runtime.submit_signal(snapshot(version=2, price=101.0, generated_at=t0 + timedelta(minutes=1)), now=t0 + timedelta(minutes=1), intent_id=first.intent_id)

    def test_repricing_limit_returns_no_trade(self) -> None:
        runtime = PaperRealtimeLifecycle()
        runtime.revalidation_policy = runtime.revalidation_policy.__class__(max_repricing_count=0)
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        first = runtime.submit_signal(snapshot(version=1, price=100.0, generated_at=t0), now=t0)
        action = runtime.revalidate(intent_id=first.intent_id, snapshot=snapshot(version=2, price=118.0, generated_at=t0 + timedelta(minutes=1)), market_price=120.0, now=t0 + timedelta(minutes=1))
        self.assertIn(action.value, {"CANCEL", "NO_TRADE"})

    def test_duplicate_market_event_is_suppressed(self) -> None:
        runtime = PaperRealtimeLifecycle()
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        first = runtime.submit_signal(snapshot(version=1, price=100.0, generated_at=t0), now=t0)
        duplicate = event(100.0, t0 + timedelta(seconds=1), "same-source-event")
        self.assertEqual(runtime.on_market_event(duplicate), (first.order_id,))
        event_count = len(runtime.ledger.events)
        self.assertEqual(runtime.on_market_event(duplicate), ())
        self.assertEqual(len(runtime.ledger.events), event_count)

    def test_exit_updates_capital_and_replay_is_stable(self) -> None:
        runtime = PaperRealtimeLifecycle()
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        runtime.submit_signal(snapshot(version=1, price=100.0, generated_at=t0), now=t0)
        runtime.on_market_event(event(100.0, t0 + timedelta(seconds=1), "fill"))
        runtime.exit_position(symbol="BTCUSDT", price=110.0, now=t0 + timedelta(minutes=2), reason=ExitReason.TAKE_PROFIT)
        state_a = runtime.replay_account()
        state_b = runtime.replay_account()
        self.assertEqual(state_a, state_b)
        self.assertEqual(state_a.position("BTCUSDT").quantity, 0.0)
        self.assertAlmostEqual(state_a.wallet.cash, 210.0)
        self.assertTrue(runtime.no_live_execution())


if __name__ == "__main__":
    unittest.main()
