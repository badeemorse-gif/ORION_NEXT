from __future__ import annotations

import ast
import sys
import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "binansScanner"))

from models.execution import ExecutionPlan, ExecutionSide
from models.signal_journal import SignalObservation
from tools.pending_order_revalidation import (
    CancelReason,
    PendingOrderBook,
    RevalidationAction,
    RevalidationPolicy,
    build_pending_order,
    revalidate_pending_order,
)

BASE = datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc)


def obs(i: str, decision: str = "FAVORABLE", confidence: float = 80.0) -> SignalObservation:
    return SignalObservation(i, BASE, "BTCUSDT", "1h", 80.0, confidence=confidence, decision=decision, market_regime="BULLISH", reasons=("TEST",))


def buy(price: float) -> ExecutionPlan:
    return ExecutionPlan("BTCUSDT", ExecutionSide.BUY, price, 1.0, 80.0, decision="FAVORABLE")


def sell(price: float) -> ExecutionPlan:
    return ExecutionPlan("BTCUSDT", ExecutionSide.SELL, price, 1.0, 80.0, decision="UNFAVORABLE")


@dataclass
class PositionState:
    open_symbols: set[str]
    def has_open_position(self, symbol: str) -> bool:
        return symbol in self.open_symbols


class TestPendingOrderContract(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = RevalidationPolicy()
        self.book = PendingOrderBook()
        self.old = build_pending_order(obs("SIG-1"), buy(100.0), intent_id="BTC-ENTRY")
        self.book.add(self.old)

    def test_same_signal_same_entry_keep(self):
        r = revalidate_pending_order(self.old, obs("SIG-1"), buy(100.5), market_price=101.0, now=BASE + timedelta(minutes=1))
        self.assertEqual(r.action, RevalidationAction.KEEP)
        self.assertEqual(len(self.book.pending()), 1)

    def test_material_change_cancel_replace(self):
        r = revalidate_pending_order(self.old, obs("SIG-2", confidence=92.0), buy(118.0), market_price=120.0, now=BASE + timedelta(minutes=2))
        self.assertEqual((r.action, r.reason), (RevalidationAction.REPLACE, CancelReason.MATERIAL_SIGNAL_CHANGE))
        assert r.replacement is not None
        self.book.replace(self.old.order_id, r.replacement)
        self.assertEqual(len(self.book.pending()), 1)
        self.assertEqual(self.book.pending()[0].entry_price, 118.0)
        self.assertNotEqual(self.book.pending()[0].order_id, self.old.order_id)

    def test_wait_cancel(self):
        r = revalidate_pending_order(self.old, obs("SIG-2", "WAIT"), ExecutionPlan("BTCUSDT", ExecutionSide.HOLD, 0.0, 0.0, 0.0, decision="WAIT"), market_price=120.0, now=BASE + timedelta(minutes=1))
        self.assertEqual((r.action, r.reason), (RevalidationAction.CANCEL, CancelReason.WAIT))

    def test_opposite_cancel(self):
        r = revalidate_pending_order(self.old, obs("SIG-2", "UNFAVORABLE"), sell(118.0), market_price=120.0, now=BASE + timedelta(minutes=1))
        self.assertEqual((r.action, r.reason), (RevalidationAction.CANCEL, CancelReason.OPPOSITE_DIRECTION))

    def test_expiry_cancel(self):
        r = revalidate_pending_order(self.old, obs("SIG-2"), buy(118.0), market_price=118.0, now=BASE + timedelta(minutes=16))
        self.assertEqual((r.action, r.reason), (RevalidationAction.CANCEL, CancelReason.EXPIRED))

    def test_risk_cancel(self):
        r = revalidate_pending_order(self.old, obs("SIG-2"), buy(118.0), market_price=120.0, now=BASE + timedelta(minutes=1), risk_breached=True)
        self.assertEqual((r.action, r.reason), (RevalidationAction.CANCEL, CancelReason.RISK_BREACH))

    def test_market_distance_limit(self):
        r = revalidate_pending_order(self.old, obs("SIG-2", confidence=95.0), buy(130.0), market_price=120.0, now=BASE + timedelta(minutes=1))
        self.assertEqual((r.action, r.reason), (RevalidationAction.NO_TRADE, CancelReason.MARKET_DISTANCE_LIMIT))

    def test_repricing_count_limit(self):
        r = revalidate_pending_order(self.old, obs("SIG-2"), buy(118.0), market_price=120.0, now=BASE + timedelta(minutes=1), policy=RevalidationPolicy(max_repricing_count=0))
        self.assertEqual((r.action, r.reason), (RevalidationAction.NO_TRADE, CancelReason.REPRICING_LIMIT))

    def test_cumulative_drift_limit(self):
        r = revalidate_pending_order(self.old, obs("SIG-2"), buy(118.0), market_price=120.0, now=BASE + timedelta(minutes=1), policy=RevalidationPolicy(max_cumulative_entry_drift_pct=10.0))
        self.assertEqual((r.action, r.reason), (RevalidationAction.NO_TRADE, CancelReason.CUMULATIVE_DRIFT_LIMIT))

    def test_duplicate_intent_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_INTENT"):
            self.book.add(build_pending_order(obs("SIG-2"), buy(118.0), intent_id="BTC-ENTRY"))
        self.assertEqual(len(self.book.pending()), 1)

    def test_position_open_cancels(self):
        r = revalidate_pending_order(self.old, obs("SIG-2"), buy(118.0), market_price=120.0, now=BASE + timedelta(minutes=1), position_state=PositionState({"BTCUSDT"}))
        self.assertEqual((r.action, r.reason), (RevalidationAction.CANCEL, CancelReason.POSITION_ALREADY_OPEN))

    def test_touch_fills_once_and_expired_never_fills(self):
        filled = self.book.try_fill(self.old.order_id, 100.0, BASE + timedelta(minutes=2))
        self.assertTrue(self.book.was_filled(filled.order_id))
        with self.assertRaisesRegex(RuntimeError, "duplicate fill"):
            self.book.try_fill(self.old.order_id, 100.0, BASE + timedelta(minutes=2))
        expired = PendingOrderBook()
        order = build_pending_order(obs("SIG-EXP"), buy(100.0), intent_id="EXP")
        expired.add(order)
        with self.assertRaisesRegex(RuntimeError, "expired pending order"):
            expired.try_fill(order.order_id, 100.0, BASE + timedelta(minutes=16))


class TestPendingOrderE2E(unittest.TestCase):
    def test_required_buy_100_to_buy_118_scenario(self):
        book = PendingOrderBook()
        old = build_pending_order(obs("OLD"), buy(100.0), intent_id="BTC-ENTRY")
        book.add(old)
        r = revalidate_pending_order(old, obs("NEW", confidence=92.0), buy(118.0), market_price=120.0, now=BASE + timedelta(minutes=2))
        self.assertEqual(r.action, RevalidationAction.REPLACE)
        assert r.replacement is not None
        book.replace(old.order_id, r.replacement)
        self.assertEqual([o.entry_price for o in book.pending()], [118.0])

    def test_no_live_execution_imports(self):
        tree = ast.parse((ROOT / "tools" / "pending_order_revalidation.py").read_text(encoding="utf-8"))
        imports = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imports.extend(a.name for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                imports.append(n.module or "")
        joined = " ".join(imports).lower()
        for forbidden in ("binance", "providers", "adapter", "exchange"):
            self.assertNotIn(forbidden, joined)


if __name__ == "__main__":
    unittest.main()
