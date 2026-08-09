"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.execution_engine
Version      : 2.1.0
Status       : ORION Production Candidate V2.1
===============================================================================

Execution Engine responsible for translating Orion pipeline decisions into
simulated market orders exclusively via an isolated ExecutionPlan from OrchestratorResult,
strictly enforcing clean architecture, absolute zero dataset coupling, dependency injection,
stateless processing, and zero external exchange dependencies.
===============================================================================
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from core.orchestrator import OrchestratorResult
from models.execution import ExecutionPlan
from models.execution import ExecutionSide, ExecutionStatus, ExecutionRequest, ExecutionResult

base_logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

@dataclass(slots=True)
class ExecutionStatistics:
    """Aggregated metrics tracking execution activity for operational monitoring."""
    total_processed: int = 0
    total_executed: int = 0
    total_skipped: int = 0
    total_failed: int = 0
    last_executed_at: Optional[datetime] = None


# =============================================================================
# Custom Exceptions
# =============================================================================

class ExecutionError(Exception):
    """Base exception class for all execution engine related failures."""
    pass


class ExecutionValidationError(ExecutionError):
    """Raised when request parameters or payload integrity checks fail."""
    pass



# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting execution context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Abstract Execution Adapter Interface
# =============================================================================

class ExecutionAdapter(ABC):
    """Abstract Base Class defining the protocol for order execution backends."""

    @abstractmethod
    def validate(self, request: ExecutionRequest) -> bool:
        """Validate execution parameters prior to submission."""
        pass

    @abstractmethod
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Process execution request and return outcome details."""
        pass

    @abstractmethod
    def cancel(self, order_id: str) -> bool:
        """Cancel an active pending order by identifier."""
        pass


# =============================================================================
# Trade Executor (Delegated Order Execution Handler)
# =============================================================================

class TradeExecutor:
    """
    Dedicated component responsible strictly for handling order execution logic,
    adapter communication, and transaction simulations.
    """

    def __init__(self, adapter: ExecutionAdapter, logger: Optional[logging.Logger] = None) -> None:
        if not adapter:
            raise ExecutionError("ExecutionAdapter dependency is required for TradeExecutor.")
        self._adapter = adapter
        self._logger = logger if logger is not None else base_logger

    def execute_order(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Validates and executes the trade request via the underlying adapter.
        """
        start_time = time.perf_counter()

        if not self._adapter.validate(request):
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                request=request,
                status=ExecutionStatus.FAILED,
                message="Adapter validation failed for execution request.",
                execution_time_ms=elapsed_ms,
                executed_at=datetime.now(timezone.utc),
                order_id=None,
            )

        result = self._adapter.execute(request)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return result


# =============================================================================
# Default Paper Execution Adapter
# =============================================================================

class PaperExecutionAdapter(ExecutionAdapter):
    """
    Simulated execution adapter for paper trading and backtesting.
    Generates unique UUID-based order IDs, measures elapsed execution time, and never connects to live exchanges.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(f"{__name__}.PaperExecutionAdapter")

    def validate(self, request: ExecutionRequest) -> bool:
        """Validate request parameters locally without network calls."""
        if not request.symbol:
            return False
        if request.quantity <= 0.0:
            return False
        if request.price < 0.0:
            return False
        return True

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Simulate order execution locally and return populated ExecutionResult."""
        start_time = time.perf_counter()
        
        if not self.validate(request):
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                request=request,
                status=ExecutionStatus.FAILED,
                message="Paper execution validation failed.",
                execution_time_ms=elapsed_ms,
                executed_at=datetime.now(timezone.utc),
                order_id=None,
            )

        # Simulate local paper trading delay and unique UUID order generation
        fake_order_id = f"PAPER-ORD-{uuid.uuid4()}"
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        self._logger.info(f"Simulated order filled: {fake_order_id} for {request.symbol} at {request.price}")

        return ExecutionResult(
            request=request,
            status=ExecutionStatus.EXECUTED,
            message="Paper order executed successfully.",
            execution_time_ms=elapsed_ms,
            executed_at=datetime.now(timezone.utc),
            order_id=fake_order_id,
        )

    def cancel(self, order_id: str) -> bool:
        """Simulate cancellation of a paper order."""
        self._logger.info(f"Simulated order cancelled: {order_id}")
        return True


# =============================================================================
# Main Execution Engine
# =============================================================================

class ExecutionEngine:
    """
    Stateless, dependency-injected execution engine that consumes OrchestratorResults
    exclusively via ExecutionPlan, ensuring zero knowledge or access to market datasets
    or underlying analytical models, delegating actual order execution to TradeExecutor.
    """

    def __init__(
        self,
        adapter: ExecutionAdapter,
        logger: Optional[logging.Logger] = None,
        trade_executor: Optional[TradeExecutor] = None,
    ) -> None:
        if not adapter:
            raise ExecutionError("ExecutionAdapter dependency is required.")

        self._adapter = adapter
        self._logger_instance = logger if logger is not None else base_logger
        self._trade_executor = trade_executor if trade_executor is not None else TradeExecutor(adapter=adapter, logger=self._logger_instance)
        
        self._last_result: Optional[ExecutionResult] = None
        self._statistics = ExecutionStatistics()

        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "symbol": "NONE",
                "decision": "NONE",
                "status": "INIT",
                "operation": "init",
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def execute(self, orchestrator_result: OrchestratorResult, quantity: Optional[float] = None) -> ExecutionResult:
        """
        Main entry point for coordinating the processing of an OrchestratorResult exclusively through its ExecutionPlan.
        """
        perf_start = time.perf_counter()
        
        if not orchestrator_result:
            raise ExecutionValidationError("OrchestratorResult is missing.")

        self._statistics.total_processed += 1

        try:
            # Step 1: Extract and validate ExecutionPlan strictly from OrchestratorResult
            payload = self._extract_payload(orchestrator_result)
            symbol = payload.symbol
            raw_decision = payload.side
            price = payload.price
            confidence = payload.confidence
            
            req_quantity = quantity if quantity is not None and quantity > 0.0 else payload.quantity

            self._logger.extra.update({
                "symbol": symbol,
                "operation": "execute",
            })

            # Step 2: Normalize decision into ExecutionSide Enum once
            decision = self._parse_decision(raw_decision)
            self._logger.extra["decision"] = decision.value

            # Step 3: Handle HOLD, NONE, or neutral decisions gracefully (Skip execution)
            if decision in (ExecutionSide.HOLD, ExecutionSide.NONE):
                elapsed_ms = (time.perf_counter() - perf_start) * 1000.0
                result = ExecutionResult(
                    request=None,
                    status=ExecutionStatus.SKIPPED,
                    message=f"Decision is [{decision.value}]. Execution skipped.",
                    execution_time_ms=elapsed_ms,
                    executed_at=datetime.now(timezone.utc),
                    order_id=None,
                )
                self._statistics.total_skipped += 1
                self._last_result = result
                self._log_execution(result)
                return result

            # Step 4: Create Execution Request with strongly typed Enum decision
            request = self._build_request(
                symbol=symbol,
                side=decision,
                price=price,
                quantity=req_quantity,
                confidence=confidence,
            )

            # Step 5: Adapter Validation status check
            if not self._adapter.validate(request):
                raise ExecutionValidationError("Adapter validation failed for execution request.")

            self._logger.extra["status"] = ExecutionStatus.VALIDATED.value

            # Step 6: Delegate Execution to TradeExecutor
            result = self._trade_executor.execute_order(request)
            
            self._statistics.total_executed += 1
            self._statistics.last_executed_at = result.executed_at
            self._last_result = result
            
            self._log_execution(result)
            return result

        except Exception as e:
            elapsed_ms = (time.perf_counter() - perf_start) * 1000.0
            failed_result = ExecutionResult(
                request=None,
                status=ExecutionStatus.FAILED,
                message=str(e),
                execution_time_ms=elapsed_ms,
                executed_at=datetime.now(timezone.utc),
                order_id=None,
            )
            self._statistics.total_failed += 1
            self._last_result = failed_result
            self._logger.extra["status"] = ExecutionStatus.FAILED.value
            self._logger.error(f"Execution failed: {e}")
            return failed_result

    def validate(self, orchestrator_result: OrchestratorResult) -> bool:
        """Expose standalone validation check for orchestrator results via payload."""
        try:
            if not orchestrator_result:
                return False
            self._extract_payload(orchestrator_result)
            return True
        except Exception:
            return False

    def statistics(self) -> ExecutionStatistics:
        """Return cumulative execution engine operational statistics."""
        return self._statistics

    def last_execution(self) -> Optional[ExecutionResult]:
        """Return the result container of the most recent execution call."""
        return self._last_result

    def reset(self) -> None:
        """Reset internal state and operational statistics."""
        self._last_result = None
        self._statistics = ExecutionStatistics()
        self._logger.extra.update({"symbol": "NONE", "decision": "NONE", "status": "RESET"})
        self._logger.info("Execution engine state reset.")

    # -------------------------------------------------------------------------
    # Internal Methods (Isolated & Structured Steps)
    # -------------------------------------------------------------------------

    def _extract_payload(self, orchestrator_result: OrchestratorResult) -> ExecutionPlan:
        """
        Extract ExecutionPlan strictly from OrchestratorResult.execution_payload.
        Ensures absolute zero inspection or coupling with MarketDataset, reports, or analytical models.
        """
        if not hasattr(orchestrator_result, "execution_payload") or orchestrator_result.execution_payload is None:
            raise ExecutionValidationError("OrchestratorResult lacks a valid execution_payload.")
        
        payload = orchestrator_result.execution_payload
        if not isinstance(payload, ExecutionPlan):
            raise ExecutionValidationError("Execution payload is not an instance of ExecutionPlan.")
            
        return payload

    def _parse_decision(self, decision_val: Any) -> ExecutionSide:
        if isinstance(decision_val, ExecutionSide):
            return decision_val
            
        decision_str = str(decision_val).strip().upper()
        try:
            return ExecutionSide(decision_str)
        except ValueError:
            if decision_str == "NEUTRAL":
                return ExecutionSide.HOLD
            raise ExecutionValidationError(f"Invalid execution decision classification: [{decision_val}]")

    def _build_request(
        self,
        symbol: str,
        side: ExecutionSide,
        price: float,
        quantity: float,
        confidence: float,
    ) -> ExecutionRequest:
        return ExecutionRequest(
            symbol=symbol,
            side=side,
            price=price,
            quantity=quantity,
            confidence=confidence,
        )

    def _log_execution(self, result: ExecutionResult) -> None:
        req = result.request
        sym = req.symbol if req else "N/A"
        dec = req.side.value if req and isinstance(req.side, ExecutionSide) else "N/A"
        prc = req.price if req else 0.0
        qty = req.quantity if req else 0.0
        
        self._logger.extra.update({
            "symbol": sym,
            "decision": dec,
            "status": result.status.value,
        })
        
        self._logger.info(
            f"Execution finished | Status={result.status.value} | "
            f"Price={prc} | Qty={qty} | TimeMs={result.execution_time_ms:.2f} | "
            f"OrderID={result.order_id or 'NONE'} | Message={result.message}"
        )


# =============================================================================
# End Of File
# =============================================================================