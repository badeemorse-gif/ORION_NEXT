"""Runtime pending-order revalidation for the paper lifecycle.

D5 owns this orchestration boundary. It consumes the immutable D3
SignalSnapshot contract and a narrow D4 order/position lifecycle port. It never
contacts an exchange and never replaces the D4 position state machine.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Protocol

from models.execution import ExecutionPlan, ExecutionSide
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


class D4OrderPositionLifecyclePort(Protocol):
    """Narrow D4 contract consumed by D5; D5 does not define position FSM transitions."""

    def position_exists(self, symbol: str) -> bool: ...

    def record_pending_cancel(self, order_id: str, *, reason: CancelReason, at: datetime) -> None: ...

    def record_pending_create(self, order_id: str, *, symbol: str, side: ExecutionSide, price: float, quantity: float, at: datetime) -> None: ...

    def record_fill(self, order_id: str, *, symbol: str, side: ExecutionSide, price: float, quantity: float, at: datetime) -> None: ...


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
        for field_name in (
            "max_cumulative_entry_drift_pct",
            "minimum_material_entry_change_pct",
            "max_market_distance_pct",
        ):
            value = float(getattr(self, field_name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{field_name} must be finite and >= 0")
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
    """Stateful runtime component attached to the Paper Bot application runtime."""

    def __init__(self, lifecycle_port: D4OrderPositionLifecyclePort, policy: Optional[RepricingPolicy] = None) -> None:
        if lifecycle_port is None:
            raise ValueError("D4 order/position lifecycle port is required")
        self._lifecycle_port = lifecycle_port
        self._policy = policy or RepricingPolicy()
        self._orders: dict[str, PendingOrderState] = {}
        self._active_by_intent: dict[str, str] = {}
        self._history: dict[str, PendingOrderState] = {}

    def pending_orders(self) -> tuple[PendingOrderState, ...]:
        return tuple(order for order in self._orders.values() if order.active)

    def order(self, order_id: str) -> PendingOrderState:
        return self._history.get(order_id) or self._orders[order_id]

    def submit(self, signal: SignalSnapshot, plan: ExecutionPlan, *, intent_id: Optional[str] = None, at: Optional[datetime] = None) -> LifecycleResult:
        when = self._utc(at or datetime.now(timezone.utc))
        if signal.validity_at(when) is SignalValidity.EXPIRED:
            return LifecycleResult(RuntimeAction.NO_TRADE, None, reason=CancelReason.EXPIRED_SIGNAL)
        if signal.decision.strip().upper() == "WAIT" or plan.side is ExecutionSide.HOLD:
            return LifecycleResult(RuntimeAction.NO_TRADE, None, reason=CancelReason.WAIT)
        if plan.side not in (ExecutionSide.BUY, ExecutionSide.SELL) or plan.quantity <= 0.0 or plan.price <= 0.0:
            return LifecycleResult(RuntimeAction.NO_TRADE, None, reason=CancelReason.INVALID_PLAN)
        if signal.identity.symbol != plan.symbol:
            return LifecycleResult(RuntimeAction.NO_TRADE, None, reason=CancelReason.INVALID_PLAN)
        key = intent_id or signal.identity.identity_key
        existing = self.active_intent(key)
        if existing is not None:
            return LifecycleResult(RuntimeAction.REJECTED_DUPLICATE, existing, reason=CancelReason.DUPLICATE_INTENT)
        if self._lifecycle_port.position_exists(signal.identity.symbol):
            return LifecycleResult(RuntimeAction.NO_TRADE, None, reason=CancelReason.POSITION_ALREADY_OPEN)
        order = self._make_order(signal, plan, key, when)
        self._orders[order.order_id] = order
        self._active_by_intent[key] = order.order_id
        self._history[order.order_id] = order
        self._lifecycle_port.record_pending_create(
            order.order_id,
            symbol=order.symbol,
            side=order.side,
            price=order.entry_price,
            quantity=order.quantity,
            at=when,
        )
        return LifecycleResult(RuntimeAction.CREATED, order)

    def revalidate(self, current_signal: SignalSnapshot, current_plan: ExecutionPlan, *, market_price: float, at: Optional[datetime] = None, previous_signal: Optional[SignalSnapshot] = None, risk_breached: bool = False, intent_id: Optional[str] = None) -> LifecycleResult:
        when = self._utc(at or datetime.now(timezone.utc))
        key = intent_id or current_signal.identity.identity_key
        old = self.active_intent(key)
        if old is None:
            return self.submit(current_signal, current_plan, intent_id=key, at=when)
        if old.symbol != current_signal.identity.symbol or old.side != current_plan.side:
            return self._cancel(old, CancelReason.OPPOSITE_DIRECTION, when)
        if current_signal.validity_at(when) is SignalValidity.EXPIRED:
            return self._cancel(old, CancelReason.EXPIRED_SIGNAL, when)
        if current_signal.decision.strip().upper() == "WAIT" or current_plan.side is ExecutionSide.HOLD:
            return self._cancel(old, CancelReason.WAIT, when)
        if risk_breached:
            return self._cancel(old, CancelReason.RISK_BREACH, when)
        if self._lifecycle_port.position_exists(old.symbol):
            return self._cancel(old, CancelReason.POSITION_ALREADY_OPEN, when)
        price_distance = abs(float(current_plan.price) - float(market_price)) / float(market_price) * 100.0
        if not math.isfinite(price_distance) or price_distance > self._policy.max_market_distance_pct:
            self._cancel(old, CancelReason.MARKET_DISTANCE_LIMIT, when)
            return LifecycleResult(RuntimeAction.NO_TRADE, None, previous_order_id=old.order_id, reason=CancelReason.MARKET_DISTANCE_LIMIT)

        if previous_signal is None:
            previous_signal = old.signal
        d3_reasons = material_change_reasons(previous_signal, current_signal, self._policy.d3_policy())
        entry_change = abs(float(current_plan.price) - old.entry_price) / old.entry_price * 100.0
        material = bool(d3_reasons) or entry_change >= self._policy.minimum_material_entry_change_pct
        if not material and current_signal.version == old.signal_version:
            return LifecycleResult(RuntimeAction.KEEP, old)
        if not material and entry_change < self._policy.minimum_material_entry_change_pct:
            return LifecycleResult(RuntimeAction.KEEP, old)
        next_drift = old.cumulative_entry_drift_pct + entry_change
        if old.repricing_count >= self._policy.max_repricing_count:
            self._cancel(old, CancelReason.REPRICING_LIMIT, when)
            return LifecycleResult(RuntimeAction.NO_TRADE, None, previous_order_id=old.order_id, reason=CancelReason.REPRICING_LIMIT)
        if next_drift > self._policy.max_cumulative_entry_drift_pct:
            self._cancel(old, CancelReason.CUMULATIVE_DRIFT_LIMIT, when)
            return LifecycleResult(RuntimeAction.NO_TRADE, None, previous_order_id=old.order_id, reason=CancelReason.CUMULATIVE_DRIFT_LIMIT)

        # Atomic logical replacement: the old intent is first removed from the active set,
        # then the replacement becomes the only active intent. A cancelled order is never fillable.
        cancelled = self._cancel(old, CancelReason.STALE_SIGNAL, when)
        replacement = self._make_order(
            current_signal,
            current_plan,
            key,
            when,
            repricing_count=old.repricing_count + 1,
            cumulative_entry_drift_pct=next_drift,
        )
        self._orders[replacement.order_id] = replacement
        self._active_by_intent[key] = replacement.order_id
        self._history[replacement.order_id] = replacement
        self._lifecycle_port.record_pending_create(
            replacement.order_id,
            symbol=replacement.symbol,
            side=replacement.side,
            price=replacement.entry_price,
            quantity=replacement.quantity,
            at=when,
        )
        return LifecycleResult(RuntimeAction.REPLACED, replacement, previous_order_id=cancelled.order_id, replacement_order_id=replacement.order_id, reason=CancelReason.STALE_SIGNAL)

    def on_market_price(self, symbol: str, market_price: float, *, at: Optional[datetime] = None) -> tuple[LifecycleResult, ...]:
        when = self._utc(at or datetime.now(timezone.utc))
        if not math.isfinite(float(market_price)) or float(market_price) <= 0.0:
            raise ValueError("market_price must be finite and > 0")
        results: list[LifecycleResult] = []
        for order in tuple(self.pending_orders()):
            if order.symbol != symbol:
                continue
            if order.signal.is_expired(when):
                results.append(self._cancel(order, CancelReason.EXPIRED_SIGNAL, when))
                continue
            touched = market_price <= order.entry_price if order.side is ExecutionSide.BUY else market_price >= order.entry_price
            if not touched:
                continue
            filled = self._fill(order, market_price, when)
            results.append(LifecycleResult(RuntimeAction.FILLED, filled, previous_order_id=order.order_id))
        return tuple(results)

    def active_intent(self, intent_id: str) -> Optional[PendingOrderState]:
        order_id = self._active_by_intent.get(intent_id)
        if order_id is None:
            return None
        order = self._orders.get(order_id)
        return order if order is not None and order.active else None

    def _make_order(self, signal: SignalSnapshot, plan: ExecutionPlan, intent_id: str, at: datetime, *, repricing_count: int = 0, cumulative_entry_drift_pct: float = 0.0) -> PendingOrderState:
        return PendingOrderState(
            order_id=f"PAPER-PENDING-{uuid.uuid4().hex[:12]}",
            intent_id=intent_id,
            symbol=signal.identity.symbol,
            side=plan.side,
            entry_price=float(plan.price),
            quantity=float(plan.quantity),
            signal_id=signal.signal_id,
            signal_version=signal.version,
            signal=signal,
            status=PendingStatus.PENDING,
            created_at=at,
            repricing_count=repricing_count,
            cumulative_entry_drift_pct=cumulative_entry_drift_pct,
        )

    def _cancel(self, order: PendingOrderState, reason: CancelReason, at: datetime) -> LifecycleResult:
        if not order.active:
            return LifecycleResult(RuntimeAction.CANCELLED, order, previous_order_id=order.order_id, reason=reason)
        cancelled = PendingOrderState(
            order_id=order.order_id,
            intent_id=order.intent_id,
            symbol=order.symbol,
            side=order.side,
            entry_price=order.entry_price,
            quantity=order.quantity,
            signal_id=order.signal_id,
            signal_version=order.signal_version,
            signal=order.signal,
            status=PendingStatus.CANCELLED,
            created_at=order.created_at,
            cancelled_at=at,
            cancel_reason=reason,
            filled_at=order.filled_at,
            repricing_count=order.repricing_count,
            cumulative_entry_drift_pct=order.cumulative_entry_drift_pct,
        )
        self._orders.pop(order.order_id, None)
        self._history[order.order_id] = cancelled
        if self._active_by_intent.get(order.intent_id) == order.order_id:
            self._active_by_intent.pop(order.intent_id, None)
        self._lifecycle_port.record_pending_cancel(order.order_id, reason=reason, at=at)
        return LifecycleResult(RuntimeAction.CANCELLED, cancelled, previous_order_id=order.order_id, reason=reason)

    def _fill(self, order: PendingOrderState, market_price: float, at: datetime) -> PendingOrderState:
        if not order.active:
            raise RuntimeError("cancelled pending order cannot fill")
        filled = PendingOrderState(
            order_id=order.order_id,
            intent_id=order.intent_id,
            symbol=order.symbol,
            side=order.side,
            entry_price=order.entry_price,
            quantity=order.quantity,
            signal_id=order.signal_id,
            signal_version=order.signal_version,
            signal=order.signal,
            status=PendingStatus.FILLED,
            created_at=order.created_at,
            filled_at=at,
            repricing_count=order.repricing_count,
            cumulative_entry_drift_pct=order.cumulative_entry_drift_pct,
        )
        self._orders.pop(order.order_id, None)
        self._history[order.order_id] = filled
        if self._active_by_intent.get(order.intent_id) == order.order_id:
            self._active_by_intent.pop(order.intent_id, None)
        self._lifecycle_port.record_fill(order.order_id, symbol=order.symbol, side=order.side, price=float(market_price), quantity=order.quantity, at=at)
        return filled

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)


class PaperLifecycleState:
    """Deterministic paper implementation of the narrow D4 lifecycle port."""

    def __init__(self) -> None:
        self._open_positions: set[str] = set()
        self.events: list[tuple[str, str]] = []

    def position_exists(self, symbol: str) -> bool:
        return symbol in self._open_positions

    def record_pending_cancel(self, order_id: str, *, reason: CancelReason, at: datetime) -> None:
        self.events.append(("CANCEL", f"{order_id}:{reason.value}"))

    def record_pending_create(self, order_id: str, *, symbol: str, side: ExecutionSide, price: float, quantity: float, at: datetime) -> None:
        self.events.append(("CREATE", order_id))

    def record_fill(self, order_id: str, *, symbol: str, side: ExecutionSide, price: float, quantity: float, at: datetime) -> None:
        self.events.append(("FILL", order_id))
        self._open_positions.add(symbol)

    def close_position(self, symbol: str) -> None:
        self._open_positions.discard(symbol)


__all__ = [
    "CancelReason",
    "D4OrderPositionLifecyclePort",
    "LifecycleResult",
    "PaperLifecycleState",
    "PaperPendingOrderRuntime",
    "PendingOrderState",
    "PendingStatus",
    "RepricingPolicy",
    "RuntimeAction",
]
