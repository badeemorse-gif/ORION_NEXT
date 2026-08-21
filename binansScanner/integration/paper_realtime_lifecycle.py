"""Cross-layer Paper Bot lifecycle coordinator.

This module composes the delivered D3, D4, D5 and D6 runtime contracts without
redefining them. D1/D2 remain upstream producers; this boundary consumes their
canonical outputs. No live execution or exchange I/O is performed here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from models.execution import ExecutionPlan, ExecutionSide
from models.market_event import MarketEvent
from models.order_position_lifecycle import (
    ExitReason,
    FillMetadata,
    LifecycleEvent,
    LifecycleEventStore,
    OrderLifecycle,
    PositionBook,
)
from models.paper_capital import LedgerSide, PaperLedger
from models.signal_journal import SignalObservation
from models.signal_snapshot import SignalSnapshot, SignalValidity, material_change_reasons
from tools.pending_order_revalidation import (
    PendingOrder,
    PendingOrderBook,
    RevalidationAction,
    RevalidationPolicy,
    build_pending_order,
    revalidate_pending_order,
)


@dataclass(slots=True)
class PaperRealtimeLifecycle:
    """Deterministic integration state for one Paper Bot strategy stream."""

    revalidation_policy: RevalidationPolicy = field(default_factory=RevalidationPolicy)
    pending: PendingOrderBook = field(default_factory=PendingOrderBook)
    orders: OrderLifecycle = field(default_factory=OrderLifecycle)
    positions: PositionBook = field(default_factory=PositionBook)
    ledger: PaperLedger = field(default_factory=PaperLedger)
    _seen_market_events: set[str] = field(default_factory=set, init=False, repr=False)
    _last_signal: dict[str, SignalSnapshot] = field(default_factory=dict, init=False, repr=False)

    @staticmethod
    def _observation(snapshot: SignalSnapshot, *, timeframe: str, market_regime: str) -> SignalObservation:
        entry_price = snapshot.entry_plan.get("entry_price")
        if entry_price is None:
            raise ValueError("SignalSnapshot entry_plan must contain entry_price")
        return SignalObservation(
            observation_id=snapshot.signal_id,
            timestamp=snapshot.generated_at,
            symbol=snapshot.identity.symbol,
            timeframe=timeframe,
            raw_score=float(snapshot.quality if snapshot.quality is not None else 0.0),
            confidence=snapshot.confidence,
            decision=snapshot.decision,
            market_regime=market_regime,
        )

    @staticmethod
    def _execution_plan(snapshot: SignalSnapshot, *, now: datetime) -> ExecutionPlan:
        entry_price = float(snapshot.entry_plan["entry_price"])
        quantity = float(snapshot.entry_plan.get("quantity", 1.0))
        direction = snapshot.direction.strip().upper()
        side = ExecutionSide.BUY if direction == "BUY" else ExecutionSide.SELL if direction == "SELL" else ExecutionSide.NONE
        return ExecutionPlan(
            symbol=snapshot.identity.symbol,
            side=side,
            price=entry_price,
            quantity=quantity,
            confidence=snapshot.confidence,
            decision=snapshot.decision,
            created_at=now,
        )

    def submit_signal(
        self,
        snapshot: SignalSnapshot,
        *,
        now: datetime,
        timeframe: str = "1m",
        market_regime: str = "PAPER",
        intent_id: Optional[str] = None,
    ) -> PendingOrder:
        observation = self._observation(snapshot, timeframe=timeframe, market_regime=market_regime)
        plan = self._execution_plan(snapshot, now=now)
        pending = build_pending_order(
            observation,
            plan,
            intent_id=intent_id or snapshot.identity.identity_key,
            now=now,
            policy=self.revalidation_policy,
            signal_version=snapshot.version,
        )
        self.pending.add(pending)
        self.orders.create(
            order_id=pending.order_id,
            symbol=pending.symbol,
            side=pending.side,
            quantity=pending.quantity,
            price=pending.entry_price,
            created_at=now,
        )
        self.ledger = self.ledger.record_order(
            now,
            pending.symbol,
            LedgerSide(pending.side.value),
            pending.quantity,
            pending.entry_price,
        )
        self._last_signal[pending.intent_id] = snapshot
        return pending

    def revalidate(
        self,
        *,
        intent_id: str,
        snapshot: SignalSnapshot,
        market_price: float,
        now: datetime,
        timeframe: str = "1m",
        market_regime: str = "PAPER",
    ) -> RevalidationAction:
        current = self.pending.active_for_intent(intent_id)
        if current is None:
            return RevalidationAction.NO_TRADE
        previous = self._last_signal.get(intent_id)
        validity = SignalValidity.EXPIRED.value if snapshot.is_expired(now) else SignalValidity.ACTIVE.value
        material = previous is not None and bool(material_change_reasons(previous, snapshot, policy=self._material_policy()))
        observation = self._observation(snapshot, timeframe=timeframe, market_regime=market_regime)
        plan = self._execution_plan(snapshot, now=now)
        result = revalidate_pending_order(
            current,
            observation,
            plan,
            market_price=market_price,
            now=now,
            policy=self.revalidation_policy,
            signal_validity=validity,
            material_signal_change=material,
            signal_version=snapshot.version,
            position_state=self.positions,
        )
        if result.action is RevalidationAction.KEEP:
            self._last_signal[intent_id] = snapshot
            return result.action
        if result.action is RevalidationAction.CANCEL:
            self.pending.cancel(current.order_id)
            self.orders.cancel(current.order_id, reason=result.reason.value if result.reason else "CANCEL", occurred_at=now)
            self._last_signal[intent_id] = snapshot
            return result.action
        if result.action is RevalidationAction.REPLACE:
            replacement = result.replacement
            if replacement is None:
                raise RuntimeError("D5 returned REPLACE without replacement order")
            self.pending.replace(current.order_id, replacement)
            self.orders.replace(current.order_id, replacement_order_id=replacement.order_id, occurred_at=now)
            self.orders.create(
                order_id=replacement.order_id,
                symbol=replacement.symbol,
                side=replacement.side,
                quantity=replacement.quantity,
                price=replacement.entry_price,
                created_at=now,
            )
            self.ledger = self.ledger.record_order(
                now,
                replacement.symbol,
                LedgerSide(replacement.side.value),
                replacement.quantity,
                replacement.entry_price,
            )
            self._last_signal[intent_id] = snapshot
            return result.action
        self._last_signal[intent_id] = snapshot
        return result.action

    def _material_policy(self):
        from models.signal_snapshot import MaterialChangePolicy
        return MaterialChangePolicy(entry_price_change_pct=self.revalidation_policy.minimum_entry_change_pct / 100.0)

    def on_market_event(self, event: MarketEvent) -> tuple[str, ...]:
        if event.event_id in self._seen_market_events:
            return ()
        self._seen_market_events.add(event.event_id)
        price = event.payload.get("price")
        if price is None:
            return ()
        now = event.event_timestamp
        filled: list[str] = []
        for order in self.pending.pending():
            if order.symbol != event.symbol:
                continue
            try:
                matched = self.pending.try_fill(order.order_id, float(price), now)
            except (RuntimeError, KeyError, ValueError):
                continue
            fill = FillMetadata(
                fill_id=f"FILL-{matched.order_id}",
                quantity=matched.quantity,
                price=matched.entry_price,
                occurred_at=now,
                source="PAPER",
            )
            self.orders.fill(matched.order_id, fill)
            self.positions.create_from_fill(
                fill=fill,
                symbol=matched.symbol,
                side=matched.side,
                source_order_id=matched.order_id,
                position_id=f"POS-{matched.order_id}",
            )
            self.ledger = self.ledger.record_fill(
                now,
                matched.symbol,
                LedgerSide(matched.side.value),
                matched.quantity,
                matched.entry_price,
            )
            filled.append(matched.order_id)
        return tuple(filled)

    def exit_position(self, *, symbol: str, price: float, now: datetime, reason: ExitReason = ExitReason.SIGNAL_REVERSAL) -> str:
        position = self.positions.active_for_symbol(symbol)
        if position is None:
            raise ValueError(f"no active position for {symbol}")
        order_id = f"EXIT-{position.position_id}"
        self.orders.create(
            order_id=order_id,
            symbol=symbol,
            side=ExecutionSide.SELL if position.side is ExecutionSide.BUY else ExecutionSide.BUY,
            quantity=position.quantity,
            price=price,
            created_at=now,
        )
        fill = FillMetadata(
            fill_id=f"FILL-{order_id}",
            quantity=position.quantity,
            price=price,
            occurred_at=now,
            source="PAPER",
        )
        self.orders.fill(order_id, fill)
        self.positions.exit(position.position_id, reason=reason, occurred_at=now)
        self.ledger = self.ledger.record_fill(
            now,
            symbol,
            LedgerSide.SELL if position.side is ExecutionSide.BUY else LedgerSide.BUY,
            position.quantity,
            price,
        )
        return order_id

    def replay(self) -> tuple[LifecycleEvent, ...]:
        return tuple(self.orders.events) + tuple(self.positions.events)

    def replay_account(self):
        return self.ledger.replay()

    def no_live_execution(self) -> bool:
        return True


__all__ = ["PaperRealtimeLifecycle"]
