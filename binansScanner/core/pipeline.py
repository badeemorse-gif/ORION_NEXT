"""ORION application-level pipeline coordinator."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from core.orchestrator import Orchestrator, OrchestratorResult
from engines.execution_engine import ExecutionEngine
from engines.report_engine import ReportEngine
from models.execution import ExecutionResult, ExecutionStatus
from models.report import ReportResult

base_logger = logging.getLogger(__name__)


class PipelineError(Exception):
    pass


@dataclass(slots=True)
class PipelineItemResult:
    symbol: str
    orchestrator_result: Optional[OrchestratorResult] = None
    execution_result: Optional[ExecutionResult] = None
    report_result: Optional[ReportResult] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    elapsed_ms: float = 0.0
    success: bool = False
    error_message: Optional[str] = None
    failed_stage: Optional[str] = None


@dataclass(slots=True)
class PipelineSummary:
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    elapsed_ms: float = 0.0
    processed_symbols: int = 0
    successful_symbols: int = 0
    failed_symbols: int = 0
    execution_count: int = 0
    success: bool = False


class LoggerAdapter(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        text = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        return (f"[{text}] {msg}" if text else msg), kwargs


class Pipeline:
    """Stateless application flow: Orchestrator -> Execution -> Report."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        execution_engine: ExecutionEngine,
        report_engine: ReportEngine,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if orchestrator is None:
            raise PipelineError("Orchestrator dependency is required.")
        if execution_engine is None:
            raise PipelineError("ExecutionEngine dependency is required.")
        if report_engine is None:
            raise PipelineError("ReportEngine dependency is required.")
        self._orchestrator = orchestrator
        self._execution_engine = execution_engine
        self._report_engine = report_engine
        self._last_summary: Optional[PipelineSummary] = None
        self._logger = LoggerAdapter(logger or base_logger, {"symbol": "NONE", "operation": "init"})

    def run_symbol(
        self,
        symbol: str,
        timeframes: list[str],
        quantity: Optional[float] = None,
    ) -> PipelineItemResult:
        started = datetime.now(timezone.utc)
        perf = time.perf_counter()
        orch_res = None
        exec_res = None
        report_res = None
        error_message = None
        failed_stage: Optional[str] = None
        success = False
        self._logger.extra.update({"symbol": symbol, "operation": "run_symbol"})

        try:
            self._validate_symbol(symbol)

            failed_stage = "ORCHESTRATION"
            orch_res = self._orchestrator.run(symbol, timeframes)
            if orch_res.execution_plan is None:
                raise PipelineError("Orchestrator did not produce an ExecutionPlan.")

            failed_stage = "EXECUTION"
            exec_res = self._execution_engine.execute(
                orch_res.execution_plan,
                quantity=quantity,
            )
            if not isinstance(exec_res, ExecutionResult):
                raise PipelineError("ExecutionEngine returned an invalid ExecutionResult.")

            execution_failed = exec_res.status is ExecutionStatus.FAILED

            failed_stage = "REPORT"
            report_res = self._report_engine.build_report(
                symbol=symbol,
                analysis=orch_res.analysis,
                profile=orch_res.profile,
                score=orch_res.score,
                decision=orch_res.decision,
                execution=exec_res,
                execution_time_ms=(
                    orch_res.statistics.elapsed_ms + exec_res.execution_time_ms
                ),
                stage_trace=("ORCHESTRATION", "EXECUTION", "REPORT"),
                failure_stage="EXECUTION" if execution_failed else None,
                failure_message=(
                    exec_res.message or "ExecutionEngine returned FAILED."
                    if execution_failed
                    else None
                ),
            )
            if not isinstance(report_res, ReportResult):
                raise PipelineError("ReportEngine returned an invalid ReportResult.")

            if execution_failed:
                failed_stage = "EXECUTION"
                raise PipelineError(
                    f"Execution failed: {exec_res.message or 'ExecutionEngine returned FAILED.'}"
                )

            success = True
            failed_stage = None
        except Exception as exc:
            error_message = str(exc)
            if orch_res is None:
                orch_res = self._orchestrator.last_result()

            # Preserve operational evidence even when orchestration itself
            # fails before an ExecutionResult exists. Execution failures are
            # already materialized above so the report cannot imply success.
            if report_res is None and orch_res is not None:
                try:
                    trace = (
                        ("ORCHESTRATION", "EXECUTION", "REPORT")
                        if exec_res is not None
                        else ("ORCHESTRATION", "REPORT")
                    )
                    report_res = self._report_engine.build_report(
                        symbol=symbol,
                        analysis=orch_res.analysis,
                        profile=orch_res.profile,
                        score=orch_res.score,
                        decision=orch_res.decision,
                        execution=exec_res,
                        execution_time_ms=(
                            orch_res.statistics.elapsed_ms
                            + (exec_res.execution_time_ms if exec_res is not None else 0.0)
                        ),
                        stage_trace=trace,
                        failure_stage=failed_stage or "UNKNOWN",
                        failure_message=error_message,
                    )
                    if not isinstance(report_res, ReportResult):
                        report_res = None
                        raise PipelineError("ReportEngine returned an invalid failure ReportResult.")
                except Exception as report_exc:
                    self._logger.error(
                        f"Failure evidence report could not be built for [{symbol}]: {report_exc}"
                    )

            self._logger.error(
                f"Pipeline failed for [{symbol}] at stage [{failed_stage}]: {exc}"
            )

        finished = datetime.now(timezone.utc)
        elapsed = (time.perf_counter() - perf) * 1000.0
        return PipelineItemResult(
            symbol=symbol,
            orchestrator_result=orch_res,
            execution_result=exec_res,
            report_result=report_res,
            started_at=started,
            finished_at=finished,
            elapsed_ms=elapsed,
            success=success,
            error_message=error_message,
            failed_stage=failed_stage,
        )

    def run_symbols(
        self,
        symbols: Iterable[str],
        timeframes: list[str],
        quantity: Optional[float] = None,
    ) -> tuple[PipelineSummary, list[PipelineItemResult]]:
        started = datetime.now(timezone.utc)
        perf = time.perf_counter()
        results: list[PipelineItemResult] = []
        for symbol in list(symbols):
            results.append(self.run_symbol(symbol, timeframes, quantity))

        processed = len(results)
        successful = sum(1 for item in results if item.success)
        failed = processed - successful
        executed = sum(
            1
            for item in results
            if item.execution_result is not None
            and item.execution_result.status is ExecutionStatus.EXECUTED
        )
        finished = datetime.now(timezone.utc)
        elapsed = (time.perf_counter() - perf) * 1000.0
        summary = PipelineSummary(
            started_at=started,
            finished_at=finished,
            elapsed_ms=elapsed,
            processed_symbols=processed,
            successful_symbols=successful,
            failed_symbols=failed,
            execution_count=executed,
            success=processed > 0 and failed == 0,
        )
        self._last_summary = summary
        return summary, results

    def statistics(self) -> Optional[PipelineSummary]:
        """Return the summary of the most recent batch execution, if any."""
        return self._last_summary

    def reset(self) -> None:
        """Reset pipeline-level cached state without rebuilding dependencies."""
        self._last_summary = None
        self._logger.extra.update({"symbol": "NONE", "operation": "reset"})

    @staticmethod
    def _validate_symbol(symbol: str) -> None:
        if not isinstance(symbol, str) or not symbol.strip():
            raise PipelineError(f"Invalid symbol provided for pipeline execution: [{symbol}]")


# End Of File
