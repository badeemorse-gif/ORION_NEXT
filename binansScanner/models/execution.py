"""Canonical Execution domain contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class ExecutionSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NONE = "NONE"


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    EXECUTED = "EXECUTED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


@dataclass(slots=True, frozen=True)
class ExecutionPlan:
    """Execution intent; invalid values are preserved for boundary rejection."""
    symbol: str
    side: ExecutionSide = ExecutionSide.NONE
    price: float = 0.0
    quantity: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    decision: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        object.__setattr__(self, "price", float(self.price))
        object.__setattr__(self, "quantity", float(self.quantity))
        object.__setattr__(self, "confidence", float(self.confidence))
        if not isinstance(self.side, ExecutionSide):
            object.__setattr__(self, "side", ExecutionSide(str(self.side).strip().upper()))
        if self.decision is not None:
            object.__setattr__(self, "decision", str(self.decision).strip().upper())


@dataclass(slots=True, frozen=True)
class ExecutionRequest:
    """Execution request; no invalid numeric value is normalized into validity."""
    symbol: str
    side: ExecutionSide
    price: float
    quantity: float
    confidence: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        object.__setattr__(self, "price", float(self.price))
        object.__setattr__(self, "quantity", float(self.quantity))
        object.__setattr__(self, "confidence", float(self.confidence))
        if not isinstance(self.side, ExecutionSide):
            object.__setattr__(self, "side", ExecutionSide(str(self.side).strip().upper()))


@dataclass(slots=True, frozen=True)
class ExecutionResult:
    request: Optional[ExecutionRequest] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    message: str = ""
    execution_time_ms: float = 0.0
    executed_at: Optional[datetime] = None
    order_id: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "execution_time_ms", max(float(self.execution_time_ms), 0.0))
        if not isinstance(self.status, ExecutionStatus):
            object.__setattr__(self, "status", ExecutionStatus(str(self.status).strip().upper()))

    @property
    def executed(self) -> bool:
        return self.status is ExecutionStatus.EXECUTED

    @property
    def skipped(self) -> bool:
        return self.status is ExecutionStatus.SKIPPED

    @property
    def failed(self) -> bool:
        return self.status is ExecutionStatus.FAILED

    @property
    def has_order_id(self) -> bool:
        return bool(self.order_id)


__all__ = ["ExecutionSide", "ExecutionStatus", "ExecutionPlan", "ExecutionRequest", "ExecutionResult"]
