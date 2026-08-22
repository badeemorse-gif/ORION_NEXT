"""Paper Runner integration boundary for the canonical Capital Manager.

This adapter owns no accounting. It exposes the PaperLedger state through the
read-only AccountingView required by CapitalManager and keeps policy allocation
state recoverable without creating a second ledger.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from models.capital_management import AllocationAudit, AllocationCandidate, AllocationConfig, CapitalManager
from models.paper_capital import PaperLedger


@dataclass(frozen=True, slots=True)
class PaperLedgerAccountingView:
    """Read-only projection of canonical PaperLedger state for CapitalManager."""

    ledger: PaperLedger
    policy_reserved: float = 0.0

    @property
    def equity(self) -> float:
        return self.ledger.replay().equity

    @property
    def realized_pnl(self) -> float:
        return self.ledger.replay().realized_pnl

    @property
    def unrealized_pnl(self) -> float:
        return self.ledger.replay().unrealized_pnl

    @property
    def reserved_capital(self) -> float:
        return self.ledger.replay().wallet.reserved_cash + self.policy_reserved

    @property
    def committed_capital(self) -> float:
        state = self.ledger.replay()
        return sum(position.quantity * position.average_price for position in state.positions)


class PaperRunnerCapitalBridge:
    """Single sizing/reservation authority used by the paper runner."""

    def __init__(self, config: AllocationConfig, ledger: PaperLedger) -> None:
        self.config = config
        self.ledger = ledger
        self._pending_notional: dict[str, float] = {}
        self._order_to_allocation: dict[str, str] = {}
        self._allocation_to_order: dict[str, str] = {}
        self._operations: list[tuple[str, object]] = []
        self.manager = CapitalManager(config, accounting=self._view())

    def _view(self) -> PaperLedgerAccountingView:
        return PaperLedgerAccountingView(self.ledger, sum(self._pending_notional.values()))

    def _sync_ledger(self, ledger: PaperLedger) -> None:
        self.ledger = ledger
        self.manager.sync_from_accounting(self._view())

    def sync_policy_positions(self) -> None:
        state = self.ledger.replay()
        self.manager.set_active_positions(position.symbol for position in state.positions if position.quantity > 0.0)

    @property
    def pending_reserved(self) -> float:
        return sum(self._pending_notional.values())

    def allocation_for(
        self,
        *,
        symbol: str,
        rank: int,
        opportunity_score: float,
        required_symbol_minimum: float,
        intent: str = "ENTRY",
    ) -> AllocationAudit:
        self.sync_policy_positions()
        audit = self.manager.calculate(
            AllocationCandidate(symbol=symbol, rank=rank, opportunity_score=opportunity_score, intent=intent),
            required_symbol_minimum,
        )
        if audit.accepted:
            self._pending_notional[audit.allocation_id] = audit.final_order_notional
            self._operations.append(("reserve", audit))
        return audit

    def bind_order(self, allocation_id: str, order_id: str) -> None:
        notional = self._pending_notional.get(allocation_id)
        if notional is None:
            raise ValueError("allocation is not reserved")
        self._order_to_allocation[order_id] = allocation_id
        self._allocation_to_order[allocation_id] = order_id
        self._operations.append(("bind", allocation_id, order_id))

    def release(self, allocation_id: str, *, reason: str) -> None:
        self._pending_notional.pop(allocation_id, None)
        self.manager.on_cancel(allocation_id)
        self._operations.append(("release", allocation_id, reason))

    def release_for_order(self, order_id: str, *, reason: str) -> Optional[str]:
        allocation_id = self._order_to_allocation.pop(order_id, None)
        if allocation_id is None:
            return None
        self._allocation_to_order.pop(allocation_id, None)
        self.release(allocation_id, reason=reason)
        return allocation_id

    def on_fill(self, order_id: str) -> Optional[str]:
        allocation_id = self._order_to_allocation.get(order_id)
        if allocation_id is None:
            return None
        self._pending_notional.pop(allocation_id, None)
        self.manager.on_fill(allocation_id)
        self._operations.append(("fill", order_id, allocation_id))
        self.sync_policy_positions()
        return allocation_id

    def on_exit_symbol(self, symbol: str) -> None:
        for allocation_id, order_id in tuple(self._allocation_to_order.items()):
            if allocation_id.split("::", 1)[0] == symbol:
                self._pending_notional.pop(allocation_id, None)
                self._allocation_to_order.pop(allocation_id, None)
                self._order_to_allocation.pop(order_id, None)
                self.manager.on_exit(allocation_id)
                self._operations.append(("exit", symbol, allocation_id))
        self.sync_policy_positions()

    def audit_state(self) -> dict[str, float | int]:
        self.manager.sync_from_accounting(self._view())
        return {
            "reserved_capital": self.manager.reserved_capital,
            "committed_capital": self.manager.committed_capital,
            "available_capital": self.manager.available_capital,
            "trading_capital": self.manager.trading_capital,
        }

    def recover(self, ledger: PaperLedger) -> "PaperRunnerCapitalBridge":
        recovered = PaperRunnerCapitalBridge(self.config, ledger)
        for operation in self._operations:
            kind = operation[0]
            if kind == "reserve":
                audit = operation[1]
                assert isinstance(audit, AllocationAudit)
                recovered._pending_notional[audit.allocation_id] = audit.final_order_notional
                recovered.manager.calculate(
                    AllocationCandidate(audit.symbol, 1, 0.0, True, audit.intent),
                    audit.required_symbol_minimum,
                )
            elif kind == "bind":
                _, allocation_id, order_id = operation
                recovered._order_to_allocation[str(order_id)] = str(allocation_id)
                recovered._allocation_to_order[str(allocation_id)] = str(order_id)
            elif kind == "release":
                _, allocation_id, _reason = operation
                recovered._pending_notional.pop(str(allocation_id), None)
                recovered.manager.on_cancel(str(allocation_id))
            elif kind == "fill":
                _, order_id, allocation_id = operation
                recovered._pending_notional.pop(str(allocation_id), None)
                recovered.manager.on_fill(str(allocation_id))
                recovered._order_to_allocation[str(order_id)] = str(allocation_id)
            elif kind == "exit":
                _, symbol, allocation_id = operation
                recovered._pending_notional.pop(str(allocation_id), None)
                recovered.manager.on_exit(str(allocation_id))
                recovered._allocation_to_order.pop(str(allocation_id), None)
        recovered.sync_policy_positions()
        return recovered


__all__ = ["PaperLedgerAccountingView", "PaperRunnerCapitalBridge"]
