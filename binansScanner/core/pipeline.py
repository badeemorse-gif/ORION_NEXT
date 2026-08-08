"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : core.pipeline
Version      : 2.0.0
Status       : ORION Production Candidate V2.0 (Stateless Pure Execution)
===============================================================================

Core Pipeline Engine acting as a purely stateless, dependency-injected execution
coordinator for running symbol analysis and trade execution workflows. Completely
stripped of internal state accumulation, history caching, and summary states,
enforcing pure execute-and-return semantics.
===============================================================================
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from core.orchestrator import (
    Orchestrator,
    OrchestratorResult,
)
from engines.execution_engine import (
    ExecutionEngine,
    ExecutionResult,
)

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class PipelineError(Exception):
    """Base exception class for all pipeline related failures."""
    pass


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass(slots=True)
class PipelineItemResult:
    """Immutable metrics and result container for a single processed symbol cycle."""
    symbol: str
    orchestrator_result: Optional[OrchestratorResult] = None
    execution_result: Optional[ExecutionResult] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    elapsed_ms: float = 0.0
    success: bool = False
    error_message: Optional[str] = None


@dataclass(slots=True)
class PipelineSummary:
    """Aggregated operational summary metrics for a complete multi-symbol batch execution."""
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    elapsed_ms: float = 0.0
    processed_symbols: int = 0
    successful_symbols: int = 0
    failed_symbols: int = 0
    execution_count: int = 0
    success: bool = False


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting pipeline operation context and timing metrics into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Main Pipeline Class (Stateless Execution Coordinator)
# =============================================================================

class Pipeline:
    """
    Purely stateless, dependency-injected pipeline coordinator managing symbol execution
    flows, coordinating Orchestrator and ExecutionEngine exclusively, enforcing isolated
    symbol failure handling, and maintaining zero internal state or result history cache.
    """

    def __init__(
        self,
        orchestrator: Orchestrator,
        execution_engine: ExecutionEngine,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if not orchestrator:
            raise PipelineError("Orchestrator dependency is required.")
        if not execution_engine:
            raise PipelineError("ExecutionEngine dependency is required.")

        self._orchestrator = orchestrator
        self._execution_engine = execution_engine
        self._logger_instance = logger if logger is not None else base_logger

        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "symbol": "NONE",
                "operation": "init",
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods (Stateless Execute-and-Return)
    # -------------------------------------------------------------------------

    def run_symbol(
        self,
        symbol: str,
        timeframes: list[str],
        quantity: Optional[float] = None,
    ) -> PipelineItemResult:
        """
        Execute analysis and execution pipeline for a single trading symbol statelessly.
        """
        perf_start = time.perf_counter()
        started_at = datetime.now(timezone.utc)
        
        self._logger.extra.update({
            "symbol": symbol,
            "operation": "run_symbol",
        })
        self._logger.info(f"Pipeline started for symbol: {symbol}")

        orch_res: Optional[OrchestratorResult] = None
        exec_res: Optional[ExecutionResult] = None
        error_msg: Optional[str] = None
        success = False

        try:
            # Step 1: Validate input symbol
            self._validate_symbol(symbol)

            # Step 2: Run Orchestrator stage
            orch_res = self._run_orchestrator(symbol=symbol, timeframes=timeframes)

            # Step 3: Run ExecutionEngine stage
            exec_res = self._run_execution(orchestrator_result=orch_res, quantity=quantity)

            success = True
            self._logger.info(f"Pipeline successfully processed symbol: {symbol}")

        except Exception as e:
            error_msg = str(e)
            self._logger.error(f"Pipeline failed for symbol [{symbol}]: {error_msg}")
            success = False

        finally:
            elapsed_ms = (time.perf_counter() - perf_start) * 1000.0
            finished_at = datetime.now(timezone.utc)

            item_result = PipelineItemResult(
                symbol=symbol,
                orchestrator_result=orch_res,
                execution_result=exec_res,
                started_at=started_at,
                finished_at=finished_at,
                elapsed_ms=elapsed_ms,
                success=success,
                error_message=error_msg,
            )

            self._logger.info(
                f"Pipeline finished for symbol {symbol} | Success={success} | Elapsed={elapsed_ms:.2f}ms"
            )

        return item_result

    def run_symbols(
        self,
        symbols: Iterable[str],
        timeframes: list[str],
        quantity: Optional[float] = None,
    ) -> tuple[PipelineSummary, list[PipelineItemResult]]:
        """
        Execute pipeline across a batch of symbols independently, insuring that failure
        in one symbol never aborts or impacts processing of remaining symbols, returning
        both batch summary and individual results directly without state caching.
        """
        perf_start = time.perf_counter()
        started_at = datetime.now(timezone.utc)

        symbol_list = list(symbols)
        item_results: list[PipelineItemResult] = []

        self._logger.extra.update({
            "symbol": "BATCH",
            "operation": "run_symbols",
        })
        self._logger.info(f"Pipeline batch execution started for symbols: {symbol_list}")

        processed_count = 0
        successful_count = 0
        failed_count = 0
        execution_count = 0

        for symbol in symbol_list:
            item_res = self.run_symbol(symbol=symbol, timeframes=timeframes, quantity=quantity)
            item_results.append(item_res)

            processed_count += 1
            if item_res.success:
                successful_count += 1
                if item_res.execution_result and item_res.execution_result.status.value == "EXECUTED":
                    execution_count += 1
            else:
                failed_count += 1

        elapsed_ms = (time.perf_counter() - perf_start) * 1000.0
        finished_at = datetime.now(timezone.utc)

        batch_success = failed_count == 0 and processed_count > 0

        summary = PipelineSummary(
            started_at=started_at,
            finished_at=finished_at,
            elapsed_ms=elapsed_ms,
            processed_symbols=processed_count,
            successful_symbols=successful_count,
            failed_symbols=failed_count,
            execution_count=execution_count,
            success=batch_success,
        )

        self._logger.info(
            f"Batch Pipeline Finished | Success={batch_success} | "
            f"Processed={summary.processed_symbols} | Successful={summary.successful_symbols} | "
            f"Failed={summary.failed_symbols} | Executions={summary.execution_count} | "
            f"ElapsedMs={summary.elapsed_ms:.2f}"
        )

        return summary, item_results

    # -------------------------------------------------------------------------
    # Internal Methods (Isolated Execution Steps)
    # -------------------------------------------------------------------------

    def _validate_symbol(self, symbol: str) -> None:
        if not symbol or not isinstance(symbol, str) or not symbol.strip():
            raise PipelineError(f"Invalid symbol provided for pipeline execution: [{symbol}]")

    def _run_orchestrator(self, symbol: str, timeframes: list[str]) -> OrchestratorResult:
        try:
            result = self._orchestrator.run(symbol=symbol, timeframes=timeframes)
            if not result:
                raise PipelineError(f"Orchestrator returned empty result for symbol {symbol}.")
            return result
        except Exception as e:
            raise PipelineError(f"Orchestration stage failed: {e}") from e

    def _run_execution(
        self,
        orchestrator_result: OrchestratorResult,
        quantity: Optional[float] = None,
    ) -> ExecutionResult:
        try:
            result = self._execution_engine.execute(orchestrator_result=orchestrator_result, quantity=quantity)
            if not result:
                raise PipelineError("ExecutionEngine returned empty result.")
            return result
        except Exception as e:
            raise PipelineError(f"Execution stage failed: {e}") from e


# =============================================================================
# End Of File
# =============================================================================