"""
===============================================================================
ORION
Module : models.execution
Version: 1.1.0

Canonical Execution domain contracts.
===============================================================================
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class ExecutionSide(str, Enum):
    """Canonical execution side."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NONE = "NONE"


class ExecutionStatus(str, Enum):
    """Canonical execution lifecycle status."""

    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    EXECUTED = "EXECUTED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


@dataclass(slots=True, frozen=True)
class ExecutionPlan:
    """Canonical execution intent produced from a completed decision."""

    symbol: str
    side: ExecutionSide = ExecutionSide.NONE
    price: float = 0.0
    quantity: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    decision: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        confidence = float(self.confidence)
        if math.isfinite(confidence):
            confidence = min(max(confidence, 0.0), 100.0)
        price = max(float(self.price), 0.0)
        quantity = max(float(self.quantity), 0.0)

        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "price", price)
        object.__setattr__(self, "quantity", quantity)

        if not isinstance(self.side, ExecutionSide):
            object.__setattr__(self, "side", ExecutionSide(str(self.side).strip().upper()))

        if self.decision is not None:
            object.__setattr__(self, "decision", str(self.decision).strip().upper())


@dataclass(slots=True, frozen=True)
class ExecutionRequest:
    """Canonical request submitted to the execution subsystem."""

    symbol: str
    side: ExecutionSide
    price: float
    quantity: float
    confidence: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        confidence = float(self.confidence)
        if math.isfinite(confidence):
            confidence = min(max(confidence, 0.0), 100.0)
        price = max(float(self.price), 0.0)
        quantity = max(float(self.quantity), 0.0)

        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "price", price)
        object.__setattr__(self, "quantity", quantity)

        if not isinstance(self.side, ExecutionSide):
            object.__setattr__(self, "side", ExecutionSide(str(self.side).strip().upper()))


@dataclass(slots=True, frozen=True)
class ExecutionResult:
    """Canonical output of the Execution layer."""

    request: Optional[ExecutionRequest] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    message: str = ""
    execution_time_ms: float = 0.0
    executed_at: Optional[datetime] = None
    order_id: Optional[str] = None

    def __post_init__(self) -> None:
        execution_time_ms = max(float(self.execution_time_ms), 0.0)
        object.__setattr__(self, "execution_time_ms", execution_time_ms)

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


__all__ = [
    "ExecutionSide",
    "ExecutionStatus",
    "ExecutionPlan",
    "ExecutionRequest",
    "ExecutionResult",
]
