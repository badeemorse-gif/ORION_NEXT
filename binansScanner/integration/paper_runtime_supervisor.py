"""Release-readiness supervision for the integrated paper runtime.

This module adds orchestration, recovery, and deterministic observability around
PaperRealtimeLifecycle without redefining D1-D6 contracts or adding execution I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional

from integration.paper_realtime_lifecycle import PaperRealtimeLifecycle
from models.market_event import MarketEvent
from models.order_position_lifecycle import OrderState
from models.signal_snapshot import SignalSnapshot
from tools.pending_order_revalidation import PendingOrder, RevalidationAction


@dataclass(frozen=True, slots=True)
class RuntimeHealth:
    healthy: bool
    paper_only: bool
    last_market_event_id: Optional[str]
    last_market_event_at: Optional[datetime]
    processed_events: int
    duplicate_events: int
    active_orders: int
    active_positions: int


@dataclass(slots=True)
class PaperRuntimeSupervisor:
    """Continuous, fail-closed supervisor for the integrated paper runtime."""

    runtime: PaperRealtimeLifecycle = field(default_factory=PaperRealtimeLifecycle)
    _operations: list[tuple] = field(default_factory=list, init=False, repr=False)
    _processed_event_ids: set[str] = field(default_factory=set, init=False, repr=False)
    _last_event: Optional[MarketEvent] = field(default=None, init=False, repr=False)
    _duplicate_events: int = field(default=0, init=False, repr=False)
    _failed: bool = field(default=False, init=False, repr=False)
    _equity_high_water: Optional[float] = field(default=None, init=False, repr=False)

    @property
    def active_orders(self) -> tuple[PendingOrder, ...]:
        return tuple(self.runtime.pending.pending())

    @property
    def terminal_orders(self) -> tuple[str, ...]:
        ids = {event.aggregate_id for event in self.runtime.orders.events if event.aggregate_type == "ORDER"}
        return tuple(
            order_id
            for order_id in sorted(ids)
            if self.runtime.orders.get(order_id).state is not OrderState.PENDING
        )

    @property
    def active_positions(self) -> tuple:
        symbols = {event.payload.get("symbol") for event in self.runtime.positions.events if event.payload.get("symbol")}
        positions = []
        for symbol in sorted(symbols):
            position = self.runtime.positions.active_for_symbol(str(symbol))
            if position is not None:
                positions.append(position)
        return tuple(positions)

    @property
    def account_equity(self) -> float:
        equity = float(self.runtime.replay_account().wallet.cash)
        if self._equity_high_water is None or equity > self._equity_high_water:
            self._equity_high_water = equity
        return equity

    @property
    def current_drawdown(self) -> float:
        equity = self.account_equity
        high_water = self._equity_high_water if self._equity_high_water is not None else equity
        return max(0.0, high_water - equity)

    @property
    def last_processed_market_event(self) -> Optional[MarketEvent]:
        return self._last_event

    @property
    def health(self) -> RuntimeHealth:
        return RuntimeHealth(
            healthy=not self._failed,
            paper_only=self.runtime.no_live_execution(),
            last_market_event_id=self._last_event.event_id if self._last_event else None,
            last_market_event_at=self._last_event.event_timestamp if self._last_event else None,
            processed_events=len(self._processed_event_ids),
            duplicate_events=self._duplicate_events,
            active_orders=len(self.active_orders),
            active_positions=len(self.active_positions),
        )

    def submit_signal(self, snapshot: SignalSnapshot, *, now: datetime, timeframe: str = "1m", market_regime: str = "PAPER", intent_id: Optional[str] = None) -> PendingOrder:
        if self._failed:
            raise RuntimeError("paper runtime is failed closed")
        pending = self.runtime.submit_signal(snapshot, now=now, timeframe=timeframe, market_regime=market_regime, intent_id=intent_id)
        self._operations.append(("submit", snapshot, now, timeframe, market_regime, intent_id))
        return pending

    def revalidate(self, *, intent_id: str, snapshot: SignalSnapshot, market_price: float, now: datetime, timeframe: str = "1m", market_regime: str = "PAPER") -> RevalidationAction:
        if self._failed:
            raise RuntimeError("paper runtime is failed closed")
        action = self.runtime.revalidate(intent_id=intent_id, snapshot=snapshot, market_price=market_price, now=now, timeframe=timeframe, market_regime=market_regime)
        self._operations.append(("revalidate", intent_id, snapshot, market_price, now, timeframe, market_regime))
        return action

    def process_market_event(self, event: MarketEvent) -> tuple[str, ...]:
        """Process one event immediately; duplicate events are suppressed before fill routing."""
        if self._failed:
            return ()
        if event.event_id in self._processed_event_ids:
            self._duplicate_events += 1
            return ()
        try:
            result = self.runtime.on_market_event(event)
        except Exception:
            self._failed = True
            raise
        self._processed_event_ids.add(event.event_id)
        self._last_event = event
        self._operations.append(("market", event))
        self.account_equity
        return result

    def consume(self, events: Iterable[MarketEvent]) -> int:
        """Consume an event stream continuously, without polling or sleeps."""
        processed = 0
        for event in events:
            before = len(self._processed_event_ids)
            self.process_market_event(event)
            processed += int(len(self._processed_event_ids) > before)
        return processed

    def recover(self) -> "PaperRuntimeSupervisor":
        """Rebuild a fresh runtime from the deterministic operation journal."""
        recovered = PaperRuntimeSupervisor(runtime=PaperRealtimeLifecycle(revalidation_policy=self.runtime.revalidation_policy))
        for operation in self._operations:
            if operation[0] == "submit":
                _, snapshot, now, timeframe, market_regime, intent_id = operation
                recovered.submit_signal(snapshot, now=now, timeframe=timeframe, market_regime=market_regime, intent_id=intent_id)
            elif operation[0] == "revalidate":
                _, intent_id, snapshot, market_price, now, timeframe, market_regime = operation
                recovered.revalidate(intent_id=intent_id, snapshot=snapshot, market_price=market_price, now=now, timeframe=timeframe, market_regime=market_regime)
            elif operation[0] == "market":
                recovered.process_market_event(operation[1])
        return recovered

    def replay_state(self) -> tuple:
        """Return deterministic account/lifecycle state suitable for comparison."""
        order_ids = sorted({event.aggregate_id for event in self.runtime.orders.events if event.aggregate_type == "ORDER"})
        position_ids = sorted({event.aggregate_id for event in self.runtime.positions.events if event.aggregate_type == "POSITION"})
        return (
            tuple((order_id, self.runtime.orders.get(order_id).state.value, self.runtime.orders.get(order_id).price, self.runtime.orders.get(order_id).quantity) for order_id in order_ids),
            tuple((position_id, next(event.payload.get("symbol") for event in self.runtime.positions.events if event.aggregate_id == position_id), next(event.payload.get("side") for event in self.runtime.positions.events if event.aggregate_id == position_id), next(event.payload.get("quantity") for event in self.runtime.positions.events if event.aggregate_id == position_id)) for position_id in position_ids),
            self.runtime.replay_account(),
        )

    def no_live_path(self) -> bool:
        """Explicit release gate: the supervisor has no exchange/live adapter."""
        return self.runtime.no_live_execution()


__all__ = ["PaperRuntimeSupervisor", "RuntimeHealth"]
