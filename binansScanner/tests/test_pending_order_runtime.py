from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from application.application_runtime import ApplicationRuntime
from core.dependency_container import DependencyContainer
from models.execution import ExecutionPlan, ExecutionSide
from models.order_position_lifecycle import OrderState, PositionState
from models.signal_snapshot import MaterialChangePolicy, MaterialChangeReason, SignalIdentity, SignalSnapshot, SignalValidity, material_change_reasons
from services.pending_order_runtime import CancelReason, PaperPendingOrderRuntime, RepricingPolicy, RuntimeAction


ROOT = Path(__file__).resolve().parents[1]
BASE = datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc)


def snapshot(version: int, *, entry: float = 100.0, decision: str = "FAVORABLE", direction: str = "BUY", valid_for_minutes: int = 15, confidence: float = 80.0) -> SignalSnapshot:
    identity = SignalIdentity("BTCUSDT", "TEST", "ENTRY")
    generated = BASE + timedelta(minutes=version)
    return SignalSnapshot(
        identity=identity,
        version=version,
        direction=direction,
        decision=decision,
        confidence=confidence,
        entry_plan={"entry_price": entry},
        generated_at=generated,
        valid_until=generated + timedelta(minutes=valid_for_minutes),
    )


def plan(side: ExecutionSide, price: float, decision: str | None = None) -> ExecutionPlan:
    return ExecutionPlan("BTCUSDT", side, price, 1.0 if side in (ExecutionSide.BUY, ExecutionSide.SELL) else 0.0, 80.0, decision=decision or ("FAVORABLE" if side is ExecutionSide.BUY else "UNFAVORABLE" if side is ExecutionSide.SELL else "WAIT"))


class TestD3Compatibility(unittest.TestCase):
    def test_snapshot_validity_and_material_change_are_consumed_directly(self):
        old = snapshot(1, entry=100.0)
        new = snapshot(2, entry=118.0, confidence=92.0)
        policy = MaterialChangePolicy(entry_price_change_pct=0.02)
        reasons = material_change_reasons(old, new, policy)
        self.assertIn(MaterialChangeReason.ENTRY_PRICE_CHANGED, reasons)
        self.assertEqual(old.validity_at(BASE + timedelta(minutes=1)), SignalValidity.ACTIVE)
        self.assertEqual(new.version, 2)


class TestD4Compatibility(unittest.TestCase):
    def test_order_lifecycle_and_position_book_are_real_runtime_dependencies(self):
        container = DependencyContainer()
        runtime = container.build_pending_order_runtime()
        order_lifecycle = runtime._order_lifecycle
        position_book = runtime._position_book
        self.assertEqual(type(order_lifecycle).__name__, "OrderLifecycle")
        self.assertEqual(type(position_book).__name__, "PositionBook")

        created = runtime.submit(snapshot(1, entry=100.0), plan(ExecutionSide.BUY, 100.0), intent_id="BTC-ENTRY", at=BASE)
        self.assertEqual(created.action, RuntimeAction.CREATED)
        self.assertEqual(runtime.d4_order(created.order.order_id).state, OrderState.PENDING)

        replaced = runtime.revalidate(snapshot(2, entry=118.0, confidence=92.0), plan(ExecutionSide.BUY, 118.0), market_price=120.0, previous_signal=snapshot(1, entry=100.0), intent_id="BTC-ENTRY", at=BASE + timedelta(minutes=2))
        self.assertEqual(replaced.action, RuntimeAction.REPLACED)
        self.assertEqual(runtime.d4_order(created.order.order_id).state, OrderState.CANCELLED)
        self.assertEqual(runtime.d4_order(replaced.order.order_id).state, OrderState.PENDING)

        filled = runtime.on_market_price("BTCUSDT", 118.0, at=BASE + timedelta(minutes=3))
        self.assertEqual(filled[0].action, RuntimeAction.FILLED)
        self.assertEqual(runtime.d4_order(replaced.order.order_id).state, OrderState.FILLED)
        position = position_book.active_for_symbol("BTCUSDT")
        self.assertIsNotNone(position)
        self.assertEqual(position.state, PositionState.OPEN)


class TestPendingOrderRuntime(unittest.TestCase):
    def setUp(self):
        self.container = DependencyContainer()
        self.runtime = self.container.build_pending_order_runtime()
        self.old_signal = snapshot(1, entry=100.0)
        self.intent = "BTC-ENTRY"
        self.runtime.submit(self.old_signal, plan(ExecutionSide.BUY, 100.0), intent_id=self.intent, at=BASE)

    def test_same_valid_signal_keep(self):
        result = self.runtime.revalidate(snapshot(1, entry=100.5), plan(ExecutionSide.BUY, 100.5), market_price=101.0, previous_signal=self.old_signal, intent_id=self.intent, at=BASE + timedelta(minutes=1))
        self.assertEqual(result.action, RuntimeAction.KEEP)
        self.assertEqual(result.order.entry_price, 100.0)

    def test_material_entry_change_cancel_replace(self):
        result = self.runtime.revalidate(snapshot(2, entry=118.0, confidence=92.0), plan(ExecutionSide.BUY, 118.0), market_price=120.0, previous_signal=self.old_signal, intent_id=self.intent, at=BASE + timedelta(minutes=2))
        self.assertEqual(result.action, RuntimeAction.REPLACED)
        self.assertEqual(len(self.runtime.pending_orders()), 1)
        self.assertEqual(self.runtime.pending_orders()[0].entry_price, 118.0)
        self.assertNotEqual(result.previous_order_id, result.replacement_order_id)

    def test_wait_cancels(self):
        result = self.runtime.revalidate(snapshot(2, entry=100.0, decision="WAIT", direction="FLAT"), plan(ExecutionSide.HOLD, 0.0), market_price=100.0, previous_signal=self.old_signal, intent_id=self.intent, at=BASE + timedelta(minutes=1))
        self.assertEqual((result.action, result.reason), (RuntimeAction.CANCELLED, CancelReason.WAIT))
        self.assertEqual(self.runtime.pending_orders(), ())

    def test_opposite_direction_cancels(self):
        result = self.runtime.revalidate(snapshot(2, entry=118.0, decision="UNFAVORABLE", direction="SELL"), plan(ExecutionSide.SELL, 118.0), market_price=120.0, previous_signal=self.old_signal, intent_id=self.intent, at=BASE + timedelta(minutes=1))
        self.assertEqual((result.action, result.reason), (RuntimeAction.CANCELLED, CancelReason.OPPOSITE_DIRECTION))

    def test_expired_signal_cancels(self):
        result = self.runtime.revalidate(snapshot(2, entry=100.0, valid_for_minutes=1), plan(ExecutionSide.BUY, 100.0), market_price=100.0, previous_signal=self.old_signal, intent_id=self.intent, at=BASE + timedelta(minutes=10))
        self.assertEqual((result.action, result.reason), (RuntimeAction.CANCELLED, CancelReason.EXPIRED_SIGNAL))

    def test_risk_breach_cancels(self):
        result = self.runtime.revalidate(snapshot(2, entry=118.0, confidence=90.0), plan(ExecutionSide.BUY, 118.0), market_price=120.0, risk_breached=True, previous_signal=self.old_signal, intent_id=self.intent, at=BASE + timedelta(minutes=1))
        self.assertEqual((result.action, result.reason), (RuntimeAction.CANCELLED, CancelReason.RISK_BREACH))

    def test_duplicate_intent_rejected(self):
        result = self.runtime.submit(snapshot(2, entry=118.0), plan(ExecutionSide.BUY, 118.0), intent_id=self.intent, at=BASE + timedelta(minutes=1))
        self.assertEqual((result.action, result.reason), (RuntimeAction.REJECTED_DUPLICATE, CancelReason.DUPLICATE_INTENT))
        self.assertEqual(len(self.runtime.pending_orders()), 1)

    def test_repricing_limit_stops_price_chasing(self):
        limited = PaperPendingOrderRuntime(self.runtime._order_lifecycle, self.runtime._position_book, RepricingPolicy(max_repricing_count=0))
        # Separate runtime state with the same D4 dependencies is intentionally not reused.
        from models.order_position_lifecycle import OrderLifecycle, PositionBook
        limited = PaperPendingOrderRuntime(OrderLifecycle(), PositionBook(), RepricingPolicy(max_repricing_count=0))
        limited.submit(self.old_signal, plan(ExecutionSide.BUY, 100.0), intent_id=self.intent, at=BASE)
        result = limited.revalidate(snapshot(2, entry=118.0), plan(ExecutionSide.BUY, 118.0), market_price=120.0, previous_signal=self.old_signal, intent_id=self.intent, at=BASE + timedelta(minutes=1))
        self.assertEqual((result.action, result.reason), (RuntimeAction.NO_TRADE, CancelReason.REPRICING_LIMIT))
        self.assertEqual(limited.pending_orders(), ())

    def test_cumulative_drift_limit_stops_price_chasing(self):
        limited = PaperPendingOrderRuntime(self.runtime._order_lifecycle, self.runtime._position_book, RepricingPolicy(max_cumulative_entry_drift_pct=5.0))
        limited.reset()
        limited.submit(self.old_signal, plan(ExecutionSide.BUY, 100.0), intent_id=self.intent, at=BASE)
        result = limited.revalidate(snapshot(2, entry=108.0), plan(ExecutionSide.BUY, 108.0), market_price=110.0, previous_signal=self.old_signal, intent_id=self.intent, at=BASE + timedelta(minutes=1))
        self.assertEqual((result.action, result.reason), (RuntimeAction.NO_TRADE, CancelReason.CUMULATIVE_DRIFT_LIMIT))


class TestPendingOrderE2E(unittest.TestCase):
    def test_required_runtime_scenario_old_entry_is_cancelled_and_never_fills(self):
        container = DependencyContainer()
        app = ApplicationRuntime(container)
        runtime = app.pending_order_runtime()
        old = snapshot(1, entry=100.0)
        runtime.submit(old, plan(ExecutionSide.BUY, 100.0), intent_id="BTC-ENTRY", at=BASE)
        self.assertEqual(runtime.pending_orders()[0].entry_price, 100.0)

        self.assertEqual(runtime.on_market_price("BTCUSDT", 120.0, at=BASE + timedelta(minutes=1)), ())
        new = snapshot(2, entry=118.0, confidence=92.0)
        replacement = runtime.revalidate(new, plan(ExecutionSide.BUY, 118.0), market_price=120.0, previous_signal=old, intent_id="BTC-ENTRY", at=BASE + timedelta(minutes=2))
        self.assertEqual(replacement.action, RuntimeAction.REPLACED)
        old_id = replacement.previous_order_id
        new_id = replacement.replacement_order_id
        self.assertEqual(runtime.d4_order(old_id).state, OrderState.CANCELLED)
        self.assertEqual(runtime.d4_order(new_id).state, OrderState.PENDING)
        self.assertEqual([order.entry_price for order in runtime.pending_orders()], [118.0])

        self.assertEqual(runtime.on_market_price("BTCUSDT", 100.0, at=BASE + timedelta(minutes=3)), ())
        self.assertEqual(runtime.d4_order(old_id).state, OrderState.CANCELLED)
        self.assertEqual(runtime.pending_orders()[0].entry_price, 118.0)

        filled = runtime.on_market_price("BTCUSDT", 118.0, at=BASE + timedelta(minutes=4))
        self.assertEqual(filled[0].action, RuntimeAction.FILLED)
        self.assertEqual(runtime.d4_order(new_id).state, OrderState.FILLED)
        self.assertTrue(runtime.position_exists("BTCUSDT"))

    def test_wait_and_sell_cancel_existing_buy(self):
        container = DependencyContainer()
        runtime = container.build_pending_order_runtime()
        old = snapshot(1, entry=100.0)
        runtime.submit(old, plan(ExecutionSide.BUY, 100.0), intent_id="BTC-ENTRY", at=BASE)
        wait = runtime.revalidate(snapshot(2, decision="WAIT", direction="FLAT"), plan(ExecutionSide.HOLD, 0.0), market_price=100.0, previous_signal=old, intent_id="BTC-ENTRY", at=BASE + timedelta(minutes=1))
        self.assertEqual(wait.reason, CancelReason.WAIT)
        runtime.submit(old, plan(ExecutionSide.BUY, 100.0), intent_id="BTC-ENTRY-2", at=BASE)
        sell = runtime.revalidate(snapshot(2, entry=99.0, decision="UNFAVORABLE", direction="SELL"), plan(ExecutionSide.SELL, 99.0), market_price=100.0, previous_signal=old, intent_id="BTC-ENTRY-2", at=BASE + timedelta(minutes=1))
        self.assertEqual(sell.reason, CancelReason.OPPOSITE_DIRECTION)

    def test_position_exists_blocks_uncontrolled_new_entry(self):
        container = DependencyContainer()
        runtime = container.build_pending_order_runtime()
        old = snapshot(1, entry=100.0)
        created = runtime.submit(old, plan(ExecutionSide.BUY, 100.0), intent_id="BTC-ENTRY", at=BASE)
        runtime.on_market_price("BTCUSDT", 100.0, at=BASE + timedelta(minutes=1))
        result = runtime.submit(snapshot(2, entry=101.0), plan(ExecutionSide.BUY, 101.0), intent_id="BTC-ENTRY-NEW", at=BASE + timedelta(minutes=2))
        self.assertEqual((result.action, result.reason), (RuntimeAction.NO_TRADE, CancelReason.POSITION_ALREADY_OPEN))
        self.assertEqual(runtime.d4_order(created.order.order_id).state, OrderState.FILLED)

    def test_signal_expiry_prevents_later_fill(self):
        container = DependencyContainer()
        runtime = container.build_pending_order_runtime()
        expiring = snapshot(1, entry=100.0, valid_for_minutes=1)
        created = runtime.submit(expiring, plan(ExecutionSide.BUY, 100.0), intent_id="EXP", at=BASE)
        expired = runtime.on_market_price("BTCUSDT", 100.0, at=BASE + timedelta(minutes=2))
        self.assertEqual(expired[0].reason, CancelReason.EXPIRED_SIGNAL)
        self.assertEqual(runtime.d4_order(created.order.order_id).state, OrderState.CANCELLED)
        self.assertEqual(runtime.pending_orders(), ())

    def test_live_path_is_absent_from_d5_runtime_module(self):
        source = (ROOT / "services" / "pending_order_runtime.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name.lower() for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module.lower())
        joined = " ".join(imported)
        for forbidden in ("binance", "providers", "exchange", "liveexecutionadapter"):
            self.assertNotIn(forbidden, joined)


if __name__ == "__main__":
    unittest.main()
