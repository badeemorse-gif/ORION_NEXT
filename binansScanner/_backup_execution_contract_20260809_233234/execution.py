"""
===============================================================================
ORION
Module : models.execution
Version: 1.0.0

Canonical Execution domain contracts.

This module defines the stable contracts used by the Execution layer.

Architectural boundary:
    DecisionResult
        ↓
    ExecutionPlan
        ↓
    ExecutionRequest
        ↓
    ExecutionResult

This module must remain independent from:
    - MarketDataset
    - Orchestrator internals
    - API implementations
    - Exchange implementations
    - Execution adapters

The models here describe execution intent and execution outcome only.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# =============================================================================
# Execution Enums
# =============================================================================


class ExecutionSide(str, Enum):
    """
    Canonical execution side.

    HOLD and NONE explicitly represent decisions that must not create
    an executable market order.
    """

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NONE = "NONE"


class ExecutionStatus(str, Enum):
    """
    Canonical execution lifecycle status.
    """

    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    EXECUTED = "EXECUTED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


# =============================================================================
# Execution Plan
# =============================================================================


@dataclass(slots=True, frozen=True)
class ExecutionPlan:
    """
    Canonical execution intent produced before physical execution.

    ExecutionPlan contains only information required to determine whether
    execution should occur and what should be requested.

    It intentionally does not contain:
        - MarketDataset
        - AnalysisResult
        - ScoreResult
        - DecisionResult
        - OrchestratorResult
        - adapter-specific state
        - exchange-specific state
    """

    symbol: str

    side: ExecutionSide = ExecutionSide.NONE

    price: float = 0.0

    quantity: float = 0.0

    confidence: float = 0.0

    reason: str = ""

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        """
        Enforce structural domain bounds.

        Business decision rules remain outside this model.
        """

        confidence = min(max(float(self.confidence), 0.0), 100.0)
        price = max(float(self.price), 0.0)
        quantity = max(float(self.quantity), 0.0)

        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "price", price)
        object.__setattr__(self, "quantity", quantity)

        if not isinstance(self.side, ExecutionSide):
            object.__setattr__(
                self,
                "side",
                ExecutionSide(str(self.side).strip().upper()),
            )


# =============================================================================
# Execution Request
# =============================================================================


@dataclass(slots=True, frozen=True)
class ExecutionRequest:
    """
    Canonical request submitted to the execution subsystem.

    This is deliberately independent from any Orchestrator type.
    """

    symbol: str

    side: ExecutionSide

    price: float

    quantity: float

    confidence: float

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        confidence = min(max(float(self.confidence), 0.0), 100.0)
        price = max(float(self.price), 0.0)
        quantity = max(float(self.quantity), 0.0)

        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "price", price)
        object.__setattr__(self, "quantity", quantity)

        if not isinstance(self.side, ExecutionSide):
            object.__setattr__(
                self,
                "side",
                ExecutionSide(str(self.side).strip().upper()),
            )


# =============================================================================
# Execution Result
# =============================================================================


@dataclass(slots=True, frozen=True)
class ExecutionResult:
    """
    Canonical output of the Execution layer.

    ExecutionResult describes what actually happened.

    It does not own:
        - decision state
        - analysis state
        - market data
        - reporting state
        - orchestrator state
    """

    request: Optional[ExecutionRequest] = None

    status: ExecutionStatus = ExecutionStatus.PENDING

    message: str = ""

    execution_time_ms: float = 0.0

    executed_at: Optional[datetime] = None

    order_id: Optional[str] = None

    def __post_init__(self) -> None:
        execution_time_ms = max(float(self.execution_time_ms), 0.0)

        object.__setattr__(
            self,
            "execution_time_ms",
            execution_time_ms,
        )

        if not isinstance(self.status, ExecutionStatus):
            object.__setattr__(
                self,
                "status",
                ExecutionStatus(str(self.status).strip().upper()),
            )

    @property
    def executed(self) -> bool:
        """
        Return True only when an execution actually occurred.
        """

        return self.status is ExecutionStatus.EXECUTED

    @property
    def skipped(self) -> bool:
        """
        Return True when execution was intentionally skipped.
        """

        return self.status is ExecutionStatus.SKIPPED

    @property
    def failed(self) -> bool:
        """
        Return True when execution failed.
        """

        return self.status is ExecutionStatus.FAILED

    @property
    def has_order_id(self) -> bool:
        """
        Return True when an execution order identifier exists.
        """

        return bool(self.order_id)


__all__ = [
    "ExecutionSide",
    "ExecutionStatus",
    "ExecutionPlan",
    "ExecutionRequest",
    "ExecutionResult",
]