"""D5 stale pending-order revalidation integrated with D3 and D4 runtime contracts."""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from models.execution import ExecutionPlan, ExecutionSide
from models.order_position_lifecycle import FillMetadata, OrderLifecycle, PositionBook
from models.signal_snapshot import MaterialChangePolicy, SignalSnapshot, SignalValidity, material_change_reasons


class PendingStatus(str, Enum):
    PENDING = "PENDING"
    CANCELLED = "CANCELLED"
    FILLED = "FILLED"


class RuntimeAction(str, Enum):
    KEEP = "KEEP"
    CREATED = "CREATED"
    CANCELLED = "CANCELLED"
    REPLACED = "REPLACED"
    FILLED = "FILLED"
    NO_TRADE = "NO_TRADE"
    REJECTED_DUPLICATE = "REJECTED_DUPLICATE"


class CancelReason(str, Enum):
    STALE_SIGNAL = "STALE_SIGNAL"
    EXPIRED_SIGNAL = "EXPIRED_SIGNAL"
    WAIT = "WAIT"
    OPPOSITE_DIRECTION = "OPPOSITE_DIRECTION"
    RISK_BREACH = "RISK_BREACH"
    POSITION_ALREADY_OPEN = "POSITION_ALREADY_OPEN"
    DUPLICATE_INTENT = "DUPLICATE_INTENT"
    REPRICING_LIMIT = "REPRICING_LIMIT"
    CUMULATIVE_DRIFT_LIMIT = "CUMULATIVE_DRIFT_LIMIT"
    MARKET_DISTANCE_LIMIT = "MARKET_DISTANCE_LIMIT"
    INVALID_PLAN = "INVALID_PLAN"


@dataclass(frozen=True, slots=True)
class RepricingPolicy:
    max_repricing_count: int = 2
    max_cumulative_entry_drift_pct: float = 20.0
    minimum_material_entry_change_pct: float = 2.0
    signal_validity_window: timedelta = timedelta(minutes=15)
    max_market_distance_pct: float = 5.0

    def __post_init__(self) -> None:
        if self.max_repricing_count < 0:
            raise ValueError("max_repricing_count must be >= 0")
        for name in ("max_cumulative_entry_drift_pct", "minimum_material_entry_change_pct", "max_market_distance_pct"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and >= 0")
        if self.signal_validity_window <= timedelta(0):
            raise ValueError("signal_validity_window must be > 0")

    def d3_policy(self) -> MaterialChangePolicy:
        return MaterialChangePolicy(entry_price_change_pct=self.minimum_material_entry_change_pct / 100.0)


@dataclass(frozen=True, slots=True)
class PendingOrderState:
    order_id: str
    intent_id: str
    symbol: str
    side: ExecutionSide
    entry_price: float
    quantity: float
    signal_id: str
    signal_version: int
    signal: SignalSnapshot
    status: PendingStatus
    created_at: datetime
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[CancelReason] = None
    filled_at: Optional[datetime] = None
    repricing_count: int = 0
    cumulative_entry_drift_pct: float = 0.0

    @property
    def active(self) -> bool:
        return self.status is PendingStatus.PENDING


@dataclass(frozen=True, slots=True)
class LifecycleResult:
    action: RuntimeAction
    order: Optional[PendingOrderState]
    previous_order_id: Optional[str] = None
    replacement_order_id: Optional[str] = None
    reason: Optional[CancelReason] = None


class PaperPendingOrderRuntime:
    """Stateful D5 runtime attached to the Paper Bot lifecycle."""

    def __init__(self, order_lifecycle: OrderLifecycle, position_book: PositionBook, policy: Optional[RepricingPolicy] = None) -> None:
        if order_lifecycle is None or position_book is None:
            raise ValueError("D4 OrderLifecycle and PositionBook are required")
        self._order_lifecycle = order_lifecycle
        self._position_book = position_book
        self._policy = policy or RepricingPolicy()
        self._orders: dict[str, PendingOrderState] = {}
        self._active_by_intent: dict[str, str] = {}
        self._history: dict[str, PendingOrderState] = {}

    def pending_orders(self) -> tuple[PendingOrderState, ...]:
        return tuple(self._orders.values())

    def order(self, order_id: str) -> PendingOrderState:
        if order_id in self._history:
            return self._history[order_id]
        return self._orders[order_id]

    def d4_order(self, order_id: str):
        return self._order_lifecycle.get(order_id)

    def position_exists(self, symbol: str) -> bool:
        return self._position_book.active_for_symbol(symbol) is not None

    def submit(self, signal: SignalSnapshot, plan: ExecutionPlan, *, intent_id: Optional[str] = None, at: Optional[datetime] = None) -> LifecycleResult:
        when = self._utc(at or datetime.now(timezone.utc))
        if signal.validity_at(when) is SignalValidity.EXPIRED:
            return LifecycleResult(RuntimeAction.NO_TRADE, None, reason=CancelReason.EXPIRED_SIGNAL)
        if signal.decision.upper() == "WAIT" or plan.side is ExecutionSide.HOLD:
            return LifecycleResult(RuntimeAction.NO_TRADE, None, reason=CancelReason.WAIT)
        if plan.side not in (ExecutionSide.BUY, ExecutionSide.SELL) or plan.price <= 0 or plan.quantity <= 0:
            return LifecycleResult(RuntimeAction.NO_TRADE, None, reason=CancelReason.INVALID_PLAN)
        if signal.identity.symbol != plan.symbol:
            return LifecycleResult(RuntimeAction.NO_TRADE, None, reason=CancelReason.INVALID_PLAN)
        key = intent_id or signal.identity.identity_key
        existing = self.active_intent(key)
        if existing is not None:
            return LifecycleResult(RuntimeAction.REJECTED_DUPLICATE, existing, reason=CancelReason.DUPLICATE_INTENT)
        if self.position_exists(signal.identity.symbol):
            return LifecycleResult(RuntimeAction.NO_TRADE, None, reason=CancelReason.POSITION_ALREADY_OPEN)
        order = self._make_order(signal, plan, key, when)
        self._order_lifecycle.create(order_id=order.order_id, symbol=order.symbol, side=order.side, quantity=order.quantity, price=order.entry_price, created_at=when)
        self._activate(order)
        return LifecycleResult(RuntimeAction.CREATED, order)

    def revalidate(self, current_signal: SignalSnapshot, current_plan: ExecutionPlan, *, market_price: float, at: Optional[datetime] = None, previous_signal: Optional[SignalSnapshot] = None, risk_breached: bool = False, intent_id: Optional[str] = None) -> LifecycleResult:
        when = self._utc(at or datetime.now(timezone.utc))
        key = intent_id or current_signal.identity.identity_key
        old = self.active_intent(key)
        if old is None:
            return self.submit(current_signal, current_plan, intent_id=key, at=when)
        if current_signal.decision.upper() == "WAIT" or current_plan.side is ExecutionSide.HOLD:
            return self._cancel(old, CancelReason.WAIT, when)
        if old.symbol != current_signal.identity.symbol or old.side is not current_plan.side:
            return self._cancel(old, CancelReason.OPPOSITE_DIRECTION, when)
        if current_signal.validity_at(when) is SignalValidity.EXPIRED:
            return self._cancel(old, CancelReason.EXPIRED_SIGNAL, when)
        if risk_breached:
            return self._cancel(old, CancelReason.RISK_BREACH, when)
        if self.position_exists(old.symbol):
            return self._cancel(old, CancelReason.POSITION_ALREADY_OPEN, when)
        distance = abs(float(current_plan.price) - float(market_price)) / float(market_price) * 100.0
        if not math.isfinite(distance) or distance > self._policy.max_market_distance_pct:
            self._cancel(old, CancelReason.MARKET_DISTANCE_LIMIT, when)
            return LifecycleResult(RuntimeAction.NO_TRADE, None, previous_order_id=old.order_id, reason=CancelReason.MARKET_DISTANCE_LIMIT)
        previous_signal = previous_signal or old.signal
        reasons = material_change_reasons(previous_signal, current_signal, self._policy.d3_policy())
        entry_change = abs(float(current_plan.price) - old.entry_price) / old.entry_price * 100.0
        material = bool(reasons) or entry_change >= self._policy.minimum_material_entry_change_pct
        if not material:
            return LifecycleResult(RuntimeAction.KEEP, old)
        next_drift = old.cumulative_entry_drift_pct + entry_change
        if old.repricing_count >= self._policy.max_repricing_count:
            self._cancel(old, CancelReason.REPRICING_LIMIT, when)
            return LifecycleResult(RuntimeAction.NO_TRADE, None, previous_order_id=old.order_id, reason=CancelReason.REPRICING_LIMIT)
        if next_drift > self._policy.max_cumulative_entry_drift_pct:
            self._cancel(old, CancelReason.CUMULATIVE_DRIFT_LIMIT, when)
            return LifecycleResult(RuntimeAction.NO_TRADE, None, previous_order_id=old.order_id, reason=CancelReason.CUMULATIVE_DRIFT_LIMIT)
        cancelled = self._cancel(old, CancelReason.STALE_SIGNAL, when)
        replacement = self._make_order(current_signal, current_plan, key, when, repricing_count=old.repricing_count + 1, cumulative_entry_drift_pct=next_drift)
        self._order_lifecycle.create(order_id=replacement.order_id, symbol=replacement.symbol, side=replacement.side, quantity=replacement.quantity, price=replacement.entry_price, created_at=when)
        self._activate(replacement)
        return LifecycleResult(RuntimeAction.REPLACED, replacement, previous_order_id=cancelled.previous_order_id, replacement_order_id=replacement.order_id, reason=CancelReason.STALE_SIGNAL)

    def on_market_price(self, symbol: str, market_price: float, *, at: Optional[datetime] = None) -> tuple[LifecycleResult, ...]:
        when = self._utc(at or datetime.now(timezone.utc))
        if not math.isfinite(float(market_price)) or float(market_price) <= 0:
            raise ValueError("market_price must be finite and > 0")
        results: list[LifecycleResult] = []
        for order in tuple(self.pending_orders()):
            if order.symbol != symbol:
                continue
            if order.signal.is_expired(when):
                results.append(self._cancel(order, CancelReason.EXPIRED_SIGNAL, when))
                continue
            touched = market_price <= order.entry_price if order.side is ExecutionSide.BUY else market_price >= order.entry_price
            if touched:
                results.append(LifecycleResult(RuntimeAction.FILLED, self._fill(order, market_price, when), previous_order_id=order.order_id))
        return tuple(results)

    def active_intent(self, intent_id: str) -> Optional[PendingOrderState]:
        order_id = self._active_by_intent.get(intent_id)
        return self._orders.get(order_id) if order_id is not None else None

    def reset(self) -> None:
        self._orders.clear()
        self._active_by_intent.clear()
        self._history.clear()

    def _activate(self, order: PendingOrderState) -> None:
        if self.active_intent(order.intent_id) is not None:
            raise ValueError(CancelReason.DUPLICATE_INTENT.value)
        self._orders[order.order_id] = order
        self._history[order.order_id] = order
        self._active_by_intent[order.intent_id] = order.order_id

    def _make_order(self, signal: SignalSnapshot, plan: ExecutionPlan, intent_id: str, at: datetime, *, repricing_count: int = 0, cumulative_entry_drift_pct: float = 0.0) -> PendingOrderState:
        return PendingOrderState(order_id=f"PAPER-PENDING-{uuid.uuid4().hex[:12]}", intent_id=intent_id, symbol=signal.identity.symbol, side=plan.side, entry_price=float(plan.price), quantity=float(plan.quantity), signal_id=signal.signal_id, signal_version=signal.version, signal=signal, status=PendingStatus.PENDING, created_at=at, repricing_count=repricing_count, cumulative_entry_drift_pct=cumulative_entry_drift_pct)

    def _cancel(self, order: PendingOrderState, reason: CancelReason, at: datetime) -> LifecycleResult:
        if not order.active:
            return LifecycleResult(RuntimeAction.CANCELLED, order, previous_order_id=order.order_id, reason=reason)
        self._order_lifecycle.cancel(order.order_id, reason=reason.value, occurred_at=at)
        cancelled = PendingOrderState(order_id=order.order_id, intent_id=order.intent_id, symbol=order.symbol, side=order.side, entry_price=order.entry_price, quantity=order.quantity, signal_id=order.signal_id, signal_version=order.signal_version, signal=order.signal, status=PendingStatus.CANCELLED, created_at=order.created_at, cancelled_at=at, cancel_reason=reason, repricing_count=order.repricing_count, cumulative_entry_drift_pct=order.cumulative_entry_drift_pct)
        self._orders.pop(order.order_id, None)
        self._history[order.order_id] = cancelled
        if self._active_by_intent.get(order.intent_id) == order.order_id:
            self._active_by_intent.pop(order.intent_id, None)
        return LifecycleResult(RuntimeAction.CANCELLED, cancelled, previous_order_id=order.order_id, reason=reason)

    def _fill(self, order: PendingOrderState, market_price: float, at: datetime) -> PendingOrderState:
        filled_record = self._order_lifecycle.fill(order.order_id, FillMetadata(f"FILL-{uuid.uuid4().hex[:12]}", order.quantity, float(market_price), at))
        if filled_record.fill is None:
            raise RuntimeError("D4 fill record missing fill metadata")
        self._position_book.create_from_fill(fill=filled_record.fill, symbol=order.symbol, side=order.side, source_order_id=order.order_id)
        filled = PendingOrderState(order_id=order.order_id, intent_id=order.intent_id, symbol=order.symbol, side=order.side, entry_price=order.entry_price, quantity=order.quantity, signal_id=order.signal_id, signal_version=order.signal_version, signal=order.signal, status=PendingStatus.FILLED, created_at=order.created_at, filled_at=at, repricing_count=order.repricing_count, cumulative_entry_drift_pct=order.cumulative_entry_drift_pct)
        self._orders.pop(order.order_id, None)
        self._history[order.order_id] = filled
        self._active_by_intent.pop(order.intent_id, None)
        return filled

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)


__all__ = ["CancelReason", "LifecycleResult", "PaperPendingOrderRuntime", "PendingOrderState", "PendingStatus", "RepricingPolicy", "RuntimeAction"]
