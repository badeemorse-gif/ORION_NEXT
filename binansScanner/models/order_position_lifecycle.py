"""Canonical D4 order/position lifecycle contract consumed by D5.

This is a paper-only lifecycle state machine. D5 owns revalidation policy, while
this module owns order/position transition state and fill/position invariants.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Optional
import uuid

from models.execution import ExecutionSide


class LifecycleError(Exception):
    pass


class InvalidTransitionError(LifecycleError):
    pass


class DuplicatePositionError(LifecycleError):
    pass


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


class ExitReason(str, Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    SIGNAL_REVERSAL = "SIGNAL_REVERSAL"
    RISK_EXIT = "RISK_EXIT"
    TIME_EXIT = "TIME_EXIT"


@dataclass(frozen=True, slots=True)
class FillMetadata:
    fill_id: str
    quantity: float
    price: float
    occurred_at: datetime
    source: str = "PAPER"

    def __post_init__(self) -> None:
        if not self.fill_id.strip():
            raise LifecycleError("fill_id is required")
        if not math.isfinite(float(self.quantity)) or float(self.quantity) <= 0.0:
            raise LifecycleError("fill quantity must be finite and > 0")
        if not math.isfinite(float(self.price)) or float(self.price) <= 0.0:
            raise LifecycleError("fill price must be finite and > 0")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise LifecycleError("fill timestamp must be timezone-aware")


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


class OrderLifecycle:
    """D4 order FSM. A terminal order cannot be filled later."""

    def __init__(self) -> None:
        self._orders: dict[str, OrderRecord] = {}
        self._history: dict[str, tuple[OrderRecord, ...]] = {}

    @property
    def events(self) -> tuple[OrderRecord, ...]:
        values: list[OrderRecord] = []
        for history in self._history.values():
            values.extend(history)
        return tuple(values)

    def create(self, *, order_id: str, symbol: str, side: ExecutionSide, quantity: float, price: float, created_at: Optional[datetime] = None) -> OrderRecord:
        if order_id in self._orders:
            raise LifecycleError(f"order already exists: {order_id}")
        if not symbol.strip() or side not in (ExecutionSide.BUY, ExecutionSide.SELL):
            raise LifecycleError("order requires a symbol and BUY/SELL side")
        quantity = float(quantity)
        price = float(price)
        if not math.isfinite(quantity) or quantity <= 0.0 or not math.isfinite(price) or price <= 0.0:
            raise LifecycleError("order quantity and price must be finite and > 0")
        when = self._ts(created_at)
        record = OrderRecord(order_id, symbol, side, quantity, price, OrderState.PENDING, when, when)
        self._orders[order_id] = record
        self._history[order_id] = (record,)
        return record

    def get(self, order_id: str) -> OrderRecord:
        if order_id not in self._orders and order_id not in self._history:
            raise LifecycleError(f"unknown order: {order_id}")
        return self._orders.get(order_id, self._history[order_id][-1])

    def history(self, order_id: str) -> tuple[OrderRecord, ...]:
        if order_id not in self._history:
            raise LifecycleError(f"unknown order: {order_id}")
        return self._history[order_id]

    def cancel(self, order_id: str, *, reason: str = "", occurred_at: Optional[datetime] = None) -> OrderRecord:
        return self._terminal(order_id, OrderState.CANCELLED, reason, occurred_at)

    def replace(self, order_id: str, *, replacement_order_id: str, occurred_at: Optional[datetime] = None) -> OrderRecord:
        return self._terminal(order_id, OrderState.REPLACED, replacement_order_id, occurred_at)

    def expire(self, order_id: str, *, reason: str = "", occurred_at: Optional[datetime] = None) -> OrderRecord:
        return self._terminal(order_id, OrderState.EXPIRED, reason, occurred_at)

    def fail(self, order_id: str, *, reason: str = "", occurred_at: Optional[datetime] = None) -> OrderRecord:
        return self._terminal(order_id, OrderState.FAILED, reason, occurred_at)

    def fill(self, order_id: str, fill: FillMetadata) -> OrderRecord:
        order = self.get(order_id)
        if order.state is not OrderState.PENDING:
            raise InvalidTransitionError(f"illegal order transition: {order.state.value} -> FILLED")
        if not math.isclose(order.quantity, float(fill.quantity), rel_tol=0.0, abs_tol=1e-12):
            raise LifecycleError("fill quantity must exactly match pending order quantity")
        filled = OrderRecord(order.order_id, order.symbol, order.side, order.quantity, order.price, OrderState.FILLED, order.created_at, fill.occurred_at, fill)
        self._orders.pop(order_id, None)
        self._history[order_id] = (*self._history[order_id], filled)
        return filled

    def _terminal(self, order_id: str, state: OrderState, reason: str, occurred_at: Optional[datetime]) -> OrderRecord:
        order = self.get(order_id)
        if order.state is not OrderState.PENDING:
            raise InvalidTransitionError(f"illegal order transition: {order.state.value} -> {state.value}")
        when = self._ts(occurred_at)
        record = OrderRecord(order.order_id, order.symbol, order.side, order.quantity, order.price, state, order.created_at, when, order.fill, reason or None)
        self._orders.pop(order_id, None)
        self._history[order_id] = (*self._history[order_id], record)
        return record

    @staticmethod
    def _ts(value: Optional[datetime]) -> datetime:
        when = value or datetime.now(timezone.utc)
        if when.tzinfo is None or when.utcoffset() is None:
            raise LifecycleError("timestamp must be timezone-aware")
        return when.astimezone(timezone.utc)


class PositionBook:
    """D4 position FSM with one active position per symbol."""

    def __init__(self) -> None:
        self._positions: dict[str, PositionRecord] = {}
        self._active_by_symbol: dict[str, str] = {}

    def active_for_symbol(self, symbol: str) -> Optional[PositionRecord]:
        position_id = self._active_by_symbol.get(symbol)
        return None if position_id is None else self._positions.get(position_id)

    def get(self, position_id: str) -> PositionRecord:
        return self._positions[position_id]

    def create_from_fill(self, *, fill: FillMetadata, symbol: str, side: ExecutionSide, source_order_id: str, position_id: Optional[str] = None) -> PositionRecord:
        if side not in (ExecutionSide.BUY, ExecutionSide.SELL):
            raise LifecycleError("position side must be BUY or SELL")
        if self.active_for_symbol(symbol) is not None:
            raise DuplicatePositionError(f"active position already exists for {symbol}")
        pid = position_id or f"POS-{uuid.uuid4().hex[:12]}"
        opened = PositionRecord(pid, symbol, side, float(fill.quantity), PositionState.OPEN, fill.occurred_at, fill.occurred_at, source_order_id)
        self._positions[pid] = opened
        self._active_by_symbol[symbol] = pid
        return opened


__all__ = [
    "DuplicatePositionError",
    "ExitReason",
    "FillMetadata",
    "InvalidTransitionError",
    "LifecycleError",
    "OrderLifecycle",
    "OrderRecord",
    "OrderState",
    "PositionBook",
    "PositionRecord",
    "PositionState",
]
