"""Deterministic order and position lifecycle contracts for paper execution.

The module is deliberately independent of real-time ingestion, opportunity
ranking, signal-versioning, cancel/replace policy, and live execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional
import uuid

from models.execution import ExecutionRequest, ExecutionResult, ExecutionSide, ExecutionStatus


class LifecycleError(Exception):
    """Base lifecycle error."""


class InvalidTransitionError(LifecycleError):
    """Raised when a lifecycle transition is not permitted."""


class DuplicatePositionError(LifecycleError):
    """Raised when an active position already exists for a symbol."""


class ReplayError(LifecycleError):
    """Raised when an event history cannot be replayed safely."""


class OrderState(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REPLACED = "REPLACED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class PositionState(str, Enum):
    OPEN = "OPEN"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    EXIT = "EXIT"
    REVERSE = "REVERSE"
    CLOSED = "CLOSED"


class PositionAction(str, Enum):
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    EXIT = "EXIT"
    REVERSE = "REVERSE"


class ExitReason(str, Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    SIGNAL_REVERSAL = "SIGNAL_REVERSAL"
    RISK_EXIT = "RISK_EXIT"
    TIME_EXIT = "TIME_EXIT"


@dataclass(frozen=True, slots=True)
class FillMetadata:
    """Immutable fill metadata persisted in the order event history."""

    fill_id: str
    quantity: float
    price: float
    occurred_at: datetime
    source: str = "PAPER"
    fee: float = 0.0
    fee_asset: Optional[str] = None

    def __post_init__(self) -> None:
        quantity = float(self.quantity)
        price = float(self.price)
        fee = float(self.fee)
        if not self.fill_id.strip():
            raise LifecycleError("fill_id is required.")
        if not math.isfinite(quantity) or quantity <= 0.0:
            raise LifecycleError("Fill quantity must be finite and greater than zero.")
        if not math.isfinite(price) or price <= 0.0:
            raise LifecycleError("Fill price must be finite and greater than zero.")
        if not math.isfinite(fee) or fee < 0.0:
            raise LifecycleError("Fill fee must be finite and non-negative.")
        if self.occurred_at.tzinfo is None:
            raise LifecycleError("Fill timestamp must be timezone-aware.")
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "price", price)
        object.__setattr__(self, "fee", fee)


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    """Append-only event used for deterministic replay."""

    event_id: str
    aggregate_id: str
    aggregate_type: str
    sequence: int
    event_type: str
    occurred_at: datetime
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sequence <= 0:
            raise LifecycleError("Event sequence must be positive.")
        if self.occurred_at.tzinfo is None:
            raise LifecycleError("Event timestamp must be timezone-aware.")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "sequence": self.sequence,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "payload": dict(self.payload),
        }


class LifecycleEventStore:
    """In-memory append-only event store used by both order and position FSMs."""

    def __init__(self, events: Iterable[LifecycleEvent] = ()) -> None:
        self._events: list[LifecycleEvent] = []
        for event in events:
            self.append(event)

    def append(self, event: LifecycleEvent) -> None:
        if self._events and event.sequence != self._next_sequence():
            raise ReplayError("Event sequence is not contiguous.")
        if not self._events and event.sequence != 1:
            raise ReplayError("The first event sequence must be 1.")
        self._events.append(event)

    def _next_sequence(self) -> int:
        return len(self._events) + 1

    @property
    def events(self) -> tuple[LifecycleEvent, ...]:
        return tuple(self._events)

    def for_aggregate(self, aggregate_id: str) -> tuple[LifecycleEvent, ...]:
        return tuple(event for event in self._events if event.aggregate_id == aggregate_id)


@dataclass(frozen=True, slots=True)
class OrderRecord:
    order_id: str
    symbol: str
    side: ExecutionSide
    quantity: float
    price: float
    state: OrderState
    created_at: datetime
    updated_at: datetime
    fill: Optional[FillMetadata] = None
    terminal_reason: Optional[str] = None


@dataclass(frozen=True, slots=True)
class PositionRecord:
    position_id: str
    symbol: str
    side: ExecutionSide
    quantity: float
    state: PositionState
    opened_at: datetime
    updated_at: datetime
    source_order_id: str
    closed_at: Optional[datetime] = None
    exit_reason: Optional[ExitReason] = None


_ORDER_TRANSITIONS: dict[OrderState, frozenset[OrderState]] = {
    OrderState.PENDING: frozenset(
        {
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.REPLACED,
            OrderState.EXPIRED,
            OrderState.FAILED,
        }
    ),
    OrderState.FILLED: frozenset(),
    OrderState.CANCELLED: frozenset(),
    OrderState.REPLACED: frozenset(),
    OrderState.EXPIRED: frozenset(),
    OrderState.FAILED: frozenset(),
}

_POSITION_ACTION_STATES: dict[PositionAction, PositionState] = {
    PositionAction.HOLD: PositionState.HOLD,
    PositionAction.REDUCE: PositionState.REDUCE,
    PositionAction.EXIT: PositionState.EXIT,
    PositionAction.REVERSE: PositionState.REVERSE,
}

_ACTIVE_POSITION_STATES = frozenset(
    {PositionState.OPEN, PositionState.HOLD, PositionState.REDUCE}
)


class OrderLifecycle:
    """Order FSM with exactly-one-fill semantics and event-sourced history."""

    def __init__(self, event_store: Optional[LifecycleEventStore] = None) -> None:
        self._store = event_store or LifecycleEventStore()
        self._orders: dict[str, OrderRecord] = {}
        self._seen_event_ids: set[str] = set()

    @property
    def events(self) -> tuple[LifecycleEvent, ...]:
        return self._store.events

    def create(
        self,
        *,
        order_id: str,
        symbol: str,
        side: ExecutionSide,
        quantity: float,
        price: float,
        created_at: Optional[datetime] = None,
    ) -> OrderRecord:
        if order_id in self._orders:
            raise LifecycleError(f"Order already exists: {order_id}")
        if not symbol.strip():
            raise LifecycleError("Order symbol is required.")
        if side not in (ExecutionSide.BUY, ExecutionSide.SELL):
            raise LifecycleError("Lifecycle orders must be BUY or SELL.")
        quantity = float(quantity)
        price = float(price)
        if not math.isfinite(quantity) or quantity <= 0.0:
            raise LifecycleError("Order quantity must be finite and greater than zero.")
        if not math.isfinite(price) or price <= 0.0:
            raise LifecycleError("Order price must be finite and greater than zero.")
        timestamp = self._timestamp(created_at)
        event = self._event(
            aggregate_id=order_id,
            event_type="ORDER_CREATED",
            occurred_at=timestamp,
            payload={
                "order_id": order_id,
                "symbol": symbol,
                "side": side.value,
                "quantity": quantity,
                "price": price,
                "created_at": timestamp.isoformat(),
            },
        )
        self._append_and_apply(event)
        return self._orders[order_id]

    def fill(self, order_id: str, fill: FillMetadata) -> OrderRecord:
        order = self.get(order_id)
        self._assert_transition(order, OrderState.FILLED)
        if order.fill is not None:
            raise InvalidTransitionError(f"Order already has a fill: {order_id}")
        if not math.isclose(fill.quantity, order.quantity, rel_tol=0.0, abs_tol=1e-12):
            raise LifecycleError("Fill quantity must exactly match the pending order quantity.")
        event = self._event(
            aggregate_id=order_id,
            event_type="ORDER_FILLED",
            occurred_at=fill.occurred_at,
            payload={
                "fill_id": fill.fill_id,
                "quantity": fill.quantity,
                "price": fill.price,
                "occurred_at": fill.occurred_at.isoformat(),
                "source": fill.source,
                "fee": fill.fee,
                "fee_asset": fill.fee_asset,
            },
        )
        self._append_and_apply(event)
        return self._orders[order_id]

    def cancel(self, order_id: str, *, reason: str = "", occurred_at: Optional[datetime] = None) -> OrderRecord:
        return self._terminal(order_id, OrderState.CANCELLED, reason, occurred_at)

    def replace(self, order_id: str, *, replacement_order_id: str, occurred_at: Optional[datetime] = None) -> OrderRecord:
        if not replacement_order_id.strip():
            raise LifecycleError("replacement_order_id is required.")
        return self._terminal(
            order_id,
            OrderState.REPLACED,
            replacement_order_id,
            occurred_at,
            event_payload={"replacement_order_id": replacement_order_id},
        )

    def expire(self, order_id: str, *, reason: str = "", occurred_at: Optional[datetime] = None) -> OrderRecord:
        return self._terminal(order_id, OrderState.EXPIRED, reason, occurred_at)

    def fail(self, order_id: str, *, reason: str = "", occurred_at: Optional[datetime] = None) -> OrderRecord:
        return self._terminal(order_id, OrderState.FAILED, reason, occurred_at)

    def get(self, order_id: str) -> OrderRecord:
        try:
            return self._orders[order_id]
        except KeyError as exc:
            raise LifecycleError(f"Unknown order: {order_id}") from exc

    def history(self, order_id: str) -> tuple[LifecycleEvent, ...]:
        return self._store.for_aggregate(order_id)

    def replay(self, events: Iterable[LifecycleEvent]) -> None:
        for event in events:
            if event.aggregate_type != "ORDER":
                continue
            self._apply_event(event, record_event=False)

    def _terminal(
        self,
        order_id: str,
        target: OrderState,
        reason: str,
        occurred_at: Optional[datetime],
        event_payload: Optional[Mapping[str, Any]] = None,
    ) -> OrderRecord:
        order = self.get(order_id)
        self._assert_transition(order, target)
        timestamp = self._timestamp(occurred_at)
        payload = {"reason": reason}
        if event_payload:
            payload.update(event_payload)
        event = self._event(
            aggregate_id=order_id,
            event_type=f"ORDER_{target.value}",
            occurred_at=timestamp,
            payload=payload,
        )
        self._append_and_apply(event)
        return self._orders[order_id]

    def _assert_transition(self, order: OrderRecord, target: OrderState) -> None:
        if target not in _ORDER_TRANSITIONS[order.state]:
            raise InvalidTransitionError(
                f"Illegal order transition: {order.state.value} -> {target.value}"
            )

    def _event(
        self,
        *,
        aggregate_id: str,
        event_type: str,
        occurred_at: datetime,
        payload: Mapping[str, Any],
    ) -> LifecycleEvent:
        return LifecycleEvent(
            event_id=str(uuid.uuid4()),
            aggregate_id=aggregate_id,
            aggregate_type="ORDER",
            sequence=len(self._store.events) + 1,
            event_type=event_type,
            occurred_at=occurred_at,
            payload=payload,
        )

    def _append_and_apply(self, event: LifecycleEvent) -> None:
        if event.event_id in self._seen_event_ids:
            raise ReplayError(f"Duplicate event id: {event.event_id}")
        self._apply_event(event, record_event=True)

    def _apply_event(self, event: LifecycleEvent, *, record_event: bool) -> None:
        if event.aggregate_type != "ORDER":
            raise ReplayError("Order lifecycle cannot consume a non-order event.")
        if record_event:
            self._store.append(event)
            self._seen_event_ids.add(event.event_id)
        p = event.payload
        if event.event_type == "ORDER_CREATED":
            order_id = str(p["order_id"])
            if order_id in self._orders:
                raise ReplayError(f"Duplicate order creation: {order_id}")
            self._orders[order_id] = OrderRecord(
                order_id=order_id,
                symbol=str(p["symbol"]),
                side=ExecutionSide(str(p["side"])),
                quantity=float(p["quantity"]),
                price=float(p["price"]),
                state=OrderState.PENDING,
                created_at=datetime.fromisoformat(str(p["created_at"])),
                updated_at=event.occurred_at,
            )
            return
        order = self.get(event.aggregate_id)
        target = OrderState(event.event_type.removeprefix("ORDER_"))
        self._assert_transition(order, target)
        fill = order.fill
        terminal_reason = order.terminal_reason
        if target is OrderState.FILLED:
            fill = FillMetadata(
                fill_id=str(p["fill_id"]),
                quantity=float(p["quantity"]),
                price=float(p["price"]),
                occurred_at=datetime.fromisoformat(str(p["occurred_at"])),
                source=str(p["source"]),
                fee=float(p["fee"]),
                fee_asset=p.get("fee_asset"),
            )
        else:
            terminal_reason = str(p.get("reason", "")) or None
        self._orders[event.aggregate_id] = OrderRecord(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.price,
            state=target,
            created_at=order.created_at,
            updated_at=event.occurred_at,
            fill=fill,
            terminal_reason=terminal_reason,
        )

    @staticmethod
    def _timestamp(value: Optional[datetime]) -> datetime:
        timestamp = value or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise LifecycleError("Lifecycle timestamp must be timezone-aware.")
        return timestamp


class PositionBook:
    """Position FSM plus single-active-position-per-symbol protection."""

    def __init__(self, event_store: Optional[LifecycleEventStore] = None) -> None:
        self._store = event_store or LifecycleEventStore()
        self._positions: dict[str, PositionRecord] = {}
        self._active_by_symbol: dict[str, str] = {}
        self._seen_event_ids: set[str] = set()

    @property
    def events(self) -> tuple[LifecycleEvent, ...]:
        return self._store.events

    def create_from_fill(
        self,
        *,
        fill: FillMetadata,
        symbol: str,
        side: ExecutionSide,
        source_order_id: str,
        position_id: Optional[str] = None,
    ) -> PositionRecord:
        if side not in (ExecutionSide.BUY, ExecutionSide.SELL):
            raise LifecycleError("Position side must be BUY or SELL.")
        if self.active_for_symbol(symbol) is not None:
            raise DuplicatePositionError(f"Active position already exists for symbol: {symbol}")
        position_id = position_id or f"POS-{uuid.uuid4()}"
        if position_id in self._positions:
            raise LifecycleError(f"Position already exists: {position_id}")
        event = self._event(
            aggregate_id=position_id,
            event_type="POSITION_OPENED",
            occurred_at=fill.occurred_at,
            payload={
                "position_id": position_id,
                "symbol": symbol,
                "side": side.value,
                "quantity": fill.quantity,
                "opened_at": fill.occurred_at.isoformat(),
                "source_order_id": source_order_id,
                "fill_id": fill.fill_id,
            },
        )
        self._append_and_apply(event)
        return self._positions[position_id]

    def hold(self, position_id: str, *, occurred_at: Optional[datetime] = None) -> PositionRecord:
        position = self.get(position_id)
        self._assert_active(position)
        return self._apply_action(position, PositionAction.HOLD, occurred_at=occurred_at)

    def reduce(self, position_id: str, quantity: float, *, occurred_at: Optional[datetime] = None) -> PositionRecord:
        position = self.get(position_id)
        self._assert_active(position)
        quantity = float(quantity)
        if not math.isfinite(quantity) or quantity <= 0.0 or quantity >= position.quantity:
            raise LifecycleError("Reduce quantity must be finite, positive, and less than current quantity.")
        timestamp = self._timestamp(occurred_at)
        event = self._event(
            aggregate_id=position_id,
            event_type="POSITION_REDUCED",
            occurred_at=timestamp,
            payload={"reduced_quantity": quantity, "remaining_quantity": position.quantity - quantity},
        )
        self._append_and_apply(event)
        return self._positions[position_id]

    def exit(
        self,
        position_id: str,
        *,
        reason: ExitReason,
        occurred_at: Optional[datetime] = None,
    ) -> PositionRecord:
        position = self.get(position_id)
        self._assert_active(position)
        timestamp = self._timestamp(occurred_at)
        self._emit_close_pair(position, PositionAction.EXIT, reason, timestamp)
        return self._positions[position_id]

    def reverse(
        self,
        position_id: str,
        *,
        reason: ExitReason = ExitReason.SIGNAL_REVERSAL,
        occurred_at: Optional[datetime] = None,
    ) -> PositionRecord:
        position = self.get(position_id)
        self._assert_active(position)
        timestamp = self._timestamp(occurred_at)
        self._emit_close_pair(position, PositionAction.REVERSE, reason, timestamp)
        return self._positions[position_id]

    def get(self, position_id: str) -> PositionRecord:
        try:
            return self._positions[position_id]
        except KeyError as exc:
            raise LifecycleError(f"Unknown position: {position_id}") from exc

    def active_for_symbol(self, symbol: str) -> Optional[PositionRecord]:
        position_id = self._active_by_symbol.get(symbol)
        return self._positions.get(position_id) if position_id else None

    def history(self, position_id: str) -> tuple[LifecycleEvent, ...]:
        return self._store.for_aggregate(position_id)

    def replay(self, events: Iterable[LifecycleEvent]) -> None:
        for event in events:
            if event.aggregate_type != "POSITION":
                continue
            self._apply_event(event, record_event=False)

    def _apply_action(
        self,
        position: PositionRecord,
        action: PositionAction,
        *,
        occurred_at: Optional[datetime],
    ) -> PositionRecord:
        timestamp = self._timestamp(occurred_at)
        event = self._event(
            aggregate_id=position.position_id,
            event_type=f"POSITION_{action.value}",
            occurred_at=timestamp,
            payload={},
        )
        self._append_and_apply(event)
        return self._positions[position.position_id]

    def _emit_close_pair(
        self,
        position: PositionRecord,
        action: PositionAction,
        reason: ExitReason,
        timestamp: datetime,
    ) -> None:
        action_event = self._event(
            aggregate_id=position.position_id,
            event_type=f"POSITION_{action.value}",
            occurred_at=timestamp,
            payload={"reason": reason.value},
        )
        close_event = self._event(
            aggregate_id=position.position_id,
            event_type="POSITION_CLOSED",
            occurred_at=timestamp,
            payload={"reason": reason.value},
        )
        self._append_and_apply(action_event)
        self._append_and_apply(close_event)

    def _assert_active(self, position: PositionRecord) -> None:
        if position.state not in _ACTIVE_POSITION_STATES:
            raise InvalidTransitionError(
                f"Position is not active: {position.position_id} [{position.state.value}]"
            )

    def _event(
        self,
        *,
        aggregate_id: str,
        event_type: str,
        occurred_at: datetime,
        payload: Mapping[str, Any],
    ) -> LifecycleEvent:
        return LifecycleEvent(
            event_id=str(uuid.uuid4()),
            aggregate_id=aggregate_id,
            aggregate_type="POSITION",
            sequence=len(self._store.events) + 1,
            event_type=event_type,
            occurred_at=occurred_at,
            payload=payload,
        )

    def _append_and_apply(self, event: LifecycleEvent) -> None:
        if event.event_id in self._seen_event_ids:
            raise ReplayError(f"Duplicate event id: {event.event_id}")
        self._apply_event(event, record_event=True)

    def _apply_event(self, event: LifecycleEvent, *, record_event: bool) -> None:
        if event.aggregate_type != "POSITION":
            raise ReplayError("Position book cannot consume a non-position event.")
        if record_event:
            self._store.append(event)
            self._seen_event_ids.add(event.event_id)
        p = event.payload
        event_name = event.event_type
        if event_name == "POSITION_OPENED":
            position_id = str(p["position_id"])
            symbol = str(p["symbol"])
            if position_id in self._positions:
                raise ReplayError(f"Duplicate position creation: {position_id}")
            if self.active_for_symbol(symbol) is not None:
                raise ReplayError(f"Replay would create duplicate active position: {symbol}")
            record = PositionRecord(
                position_id=position_id,
                symbol=symbol,
                side=ExecutionSide(str(p["side"])),
                quantity=float(p["quantity"]),
                state=PositionState.OPEN,
                opened_at=datetime.fromisoformat(str(p["opened_at"])),
                updated_at=event.occurred_at,
                source_order_id=str(p["source_order_id"]),
            )
            self._positions[position_id] = record
            self._active_by_symbol[symbol] = position_id
            return
        position = self.get(event.aggregate_id)
        if event_name == "POSITION_HOLD":
            target = PositionState.HOLD
            if position.state not in _ACTIVE_POSITION_STATES:
                raise InvalidTransitionError(f"Illegal position transition: {position.state.value} -> HOLD")
            record = self._replace(position, state=target, updated_at=event.occurred_at)
        elif event_name == "POSITION_REDUCED":
            if position.state not in _ACTIVE_POSITION_STATES:
                raise InvalidTransitionError(f"Illegal position transition: {position.state.value} -> REDUCE")
            remaining = float(p["remaining_quantity"])
            if remaining <= 0.0 or remaining >= position.quantity:
                raise ReplayError("Invalid remaining quantity in REDUCE event.")
            record = self._replace(position, quantity=remaining, state=PositionState.REDUCE, updated_at=event.occurred_at)
        elif event_name in {"POSITION_EXIT", "POSITION_REVERSE"}:
            if position.state not in _ACTIVE_POSITION_STATES:
                raise InvalidTransitionError(f"Illegal position transition: {position.state.value} -> {event_name.removeprefix('POSITION_')}")
            target = PositionState(event_name.removeprefix("POSITION_"))
            record = self._replace(position, state=target, updated_at=event.occurred_at)
        elif event_name == "POSITION_CLOSED":
            if position.state not in {PositionState.EXIT, PositionState.REVERSE}:
                raise InvalidTransitionError(f"Illegal position transition: {position.state.value} -> CLOSED")
            reason = ExitReason(str(p["reason"]))
            record = self._replace(
                position,
                state=PositionState.CLOSED,
                updated_at=event.occurred_at,
                closed_at=event.occurred_at,
                exit_reason=reason,
            )
            self._active_by_symbol.pop(position.symbol, None)
        else:
            raise ReplayError(f"Unknown position event type: {event_name}")
        self._positions[position.position_id] = record

    @staticmethod
    def _replace(position: PositionRecord, **changes: Any) -> PositionRecord:
        values = {
            "position_id": position.position_id,
            "symbol": position.symbol,
            "side": position.side,
            "quantity": position.quantity,
            "state": position.state,
            "opened_at": position.opened_at,
            "updated_at": position.updated_at,
            "source_order_id": position.source_order_id,
            "closed_at": position.closed_at,
            "exit_reason": position.exit_reason,
        }
        values.update(changes)
        return PositionRecord(**values)

    @staticmethod
    def _timestamp(value: Optional[datetime]) -> datetime:
        timestamp = value or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise LifecycleError("Lifecycle timestamp must be timezone-aware.")
        return timestamp


class ExecutionLifecycleBridge:
    """Maps canonical ExecutionResult contracts into the D4 order lifecycle."""

    @staticmethod
    def record_paper_execution(
        result: ExecutionResult,
        *,
        lifecycle: OrderLifecycle,
        fill_id: str,
        source: str = "PAPER",
    ) -> OrderRecord:
        if result.status is not ExecutionStatus.EXECUTED or result.request is None or not result.order_id:
            raise LifecycleError("Only a successful executed request can be recorded as a filled order.")
        request: ExecutionRequest = result.request
        lifecycle.create(
            order_id=result.order_id,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            created_at=request.created_at,
        )
        fill_time = result.executed_at or datetime.now(timezone.utc)
        return lifecycle.fill(
            result.order_id,
            FillMetadata(
                fill_id=fill_id,
                quantity=request.quantity,
                price=request.price,
                occurred_at=fill_time,
                source=source,
            ),
        )


__all__ = [
    "DuplicatePositionError",
    "ExecutionLifecycleBridge",
    "ExitReason",
    "FillMetadata",
    "InvalidTransitionError",
    "LifecycleError",
    "LifecycleEvent",
    "LifecycleEventStore",
    "OrderLifecycle",
    "OrderRecord",
    "OrderState",
    "PositionAction",
    "PositionBook",
    "PositionRecord",
    "PositionState",
    "ReplayError",
]
