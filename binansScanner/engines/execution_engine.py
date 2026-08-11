"""ORION execution subsystem.

Consumes only the canonical ExecutionPlan contract and returns ExecutionResult.
No dependency on Core, MarketDataset, AnalysisResult, or DecisionResult.
"""
from __future__ import annotations

import logging
import math
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from models.execution import ExecutionPlan, ExecutionRequest, ExecutionResult, ExecutionSide, ExecutionStatus

base_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ExecutionStatistics:
    total_processed: int = 0
    total_executed: int = 0
    total_skipped: int = 0
    total_failed: int = 0
    last_executed_at: Optional[datetime] = None


class ExecutionError(Exception):
    pass


class ExecutionValidationError(ExecutionError):
    pass


class ExecutionAdapter(ABC):
    @abstractmethod
    def validate(self, request: ExecutionRequest) -> bool:
        ...

    @abstractmethod
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        ...

    @abstractmethod
    def cancel(self, order_id: str) -> bool:
        ...


class TradeExecutor:
    def __init__(self, adapter: ExecutionAdapter, logger: Optional[logging.Logger] = None) -> None:
        if adapter is None:
            raise ExecutionError("ExecutionAdapter dependency is required for TradeExecutor.")
        self._adapter = adapter
        self._logger = logger if logger is not None else base_logger

    def execute_order(self, request: ExecutionRequest) -> ExecutionResult:
        if not self._adapter.validate(request):
            return ExecutionResult(
                request=request,
                status=ExecutionStatus.FAILED,
                message="Adapter validation failed for execution request.",
                execution_time_ms=0.0,
                executed_at=datetime.now(timezone.utc),
                order_id=None,
            )
        return self._adapter.execute(request)


class PaperExecutionAdapter(ExecutionAdapter):
    """Local paper-trading adapter; never contacts a live exchange."""

    def validate(self, request: ExecutionRequest) -> bool:
        """Fail closed on malformed numeric execution inputs."""
        if not request.symbol:
            return False
        if not all(
            math.isfinite(float(value))
            for value in (request.price, request.quantity, request.confidence)
        ):
            return False
        if request.quantity <= 0.0:
            return False
        if request.side in (ExecutionSide.BUY, ExecutionSide.SELL):
            return request.price > 0.0
        return request.price >= 0.0

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        started = time.perf_counter()
        if not self.validate(request):
            return ExecutionResult(
                request=request,
                status=ExecutionStatus.FAILED,
                message="Paper execution validation failed.",
                execution_time_ms=(time.perf_counter() - started) * 1000.0,
                executed_at=datetime.now(timezone.utc),
                order_id=None,
            )
        order_id = f"PAPER-ORD-{uuid.uuid4()}"
        return ExecutionResult(
            request=request,
            status=ExecutionStatus.EXECUTED,
            message="Paper order executed successfully.",
            execution_time_ms=(time.perf_counter() - started) * 1000.0,
            executed_at=datetime.now(timezone.utc),
            order_id=order_id,
        )

    def cancel(self, order_id: str) -> bool:
        return bool(order_id)


class ExecutionEngine:
    """Canonical execution coordinator operating exclusively on ExecutionPlan."""

    def __init__(
        self,
        adapter: ExecutionAdapter,
        logger: Optional[logging.Logger] = None,
        trade_executor: Optional[TradeExecutor] = None,
    ) -> None:
        if adapter is None:
            raise ExecutionError("ExecutionAdapter dependency is required.")
        self._adapter = adapter
        self._logger = logger if logger is not None else base_logger
        self._trade_executor = trade_executor or TradeExecutor(adapter, self._logger)
        self._last_result: Optional[ExecutionResult] = None
        self._statistics = ExecutionStatistics()

    def execute(self, plan: ExecutionPlan, quantity: Optional[float] = None) -> ExecutionResult:
        """Execute one canonical plan; HOLD/NONE become SKIPPED."""
        started = time.perf_counter()
        self._statistics.total_processed += 1
        try:
            if not isinstance(plan, ExecutionPlan):
                raise ExecutionValidationError("ExecutionEngine.execute requires ExecutionPlan.")

            side = plan.side if isinstance(plan.side, ExecutionSide) else ExecutionSide(str(plan.side).upper())
            if side in (ExecutionSide.HOLD, ExecutionSide.NONE):
                result = ExecutionResult(
                    request=None,
                    status=ExecutionStatus.SKIPPED,
                    message=f"Decision is [{side.value}]. Execution skipped.",
                    execution_time_ms=(time.perf_counter() - started) * 1000.0,
                    executed_at=datetime.now(timezone.utc),
                    order_id=None,
                )
                self._statistics.total_skipped += 1
                self._last_result = result
                return result

            request = ExecutionRequest(
                symbol=plan.symbol,
                side=side,
                price=plan.price,
                quantity=quantity if quantity is not None and quantity > 0 else plan.quantity,
                confidence=plan.confidence,
            )
            if not self._adapter.validate(request):
                raise ExecutionValidationError("Adapter validation failed for execution request.")

            result = self._trade_executor.execute_order(request)
            if result.status == ExecutionStatus.EXECUTED:
                self._statistics.total_executed += 1
                self._statistics.last_executed_at = result.executed_at
            elif result.status == ExecutionStatus.FAILED:
                self._statistics.total_failed += 1
            self._last_result = result
            return result
        except Exception as exc:
            result = ExecutionResult(
                request=None,
                status=ExecutionStatus.FAILED,
                message=str(exc),
                execution_time_ms=(time.perf_counter() - started) * 1000.0,
                executed_at=datetime.now(timezone.utc),
                order_id=None,
            )
            self._statistics.total_failed += 1
            self._last_result = result
            return result

    def execute_plan(self, plan: ExecutionPlan, quantity: Optional[float] = None) -> ExecutionResult:
        return self.execute(plan, quantity=quantity)

    def validate(self, plan: ExecutionPlan) -> bool:
        try:
            if not isinstance(plan, ExecutionPlan):
                return False
            if plan.side in (ExecutionSide.HOLD, ExecutionSide.NONE):
                return True
            request = ExecutionRequest(plan.symbol, plan.side, plan.price, plan.quantity, plan.confidence)
            return self._adapter.validate(request)
        except Exception:
            return False

    def statistics(self) -> ExecutionStatistics:
        return self._statistics

    def last_execution(self) -> Optional[ExecutionResult]:
        return self._last_result

    def reset(self) -> None:
        self._last_result = None
        self._statistics = ExecutionStatistics()


# End Of File
