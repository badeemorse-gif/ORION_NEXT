"""Canonical Report Engine for evidence aggregation only."""
from __future__ import annotations

import json
import logging
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.execution import ExecutionResult, ExecutionStatus
from models.profile import ProfileResult
from models.report import ReportAudit, ReportAuditStatus, ReportMetadata, ReportResult
from models.score import ScoreResult

logger = logging.getLogger(__name__)


class ReportEngineError(Exception):
    """Base exception for report-engine failures."""


class InvalidReportData(ReportEngineError):
    """Raised when canonical report inputs are invalid."""


class ReportEngine:
    """Aggregate upstream evidence; never generate intelligence or decision semantics."""

    def __init__(self, project_version: str = "", logger_instance: Optional[logging.Logger] = None) -> None:
        self._project_version = project_version
        self._logger = logger_instance if logger_instance is not None else logger

    def build_report(
        self,
        *,
        symbol: str,
        analysis: Optional[AnalysisResult],
        profile: Optional[ProfileResult],
        score: Optional[ScoreResult],
        decision: Optional[DecisionResult],
        execution: Optional[ExecutionResult],
        summary: tuple[str, ...] = (),
        highlights: tuple[str, ...] = (),
        warnings: tuple[str, ...] = (),
        execution_time_ms: float = 0.0,
        report_name: str = "ORION Report",
        stage_trace: tuple[str, ...] = (),
        failure_stage: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> ReportResult:
        if not isinstance(symbol, str) or not symbol.strip():
            raise InvalidReportData("Report symbol must be a non-empty string.")

        expected = (
            (analysis, AnalysisResult, "analysis"),
            (profile, ProfileResult, "profile"),
            (score, ScoreResult, "score"),
            (decision, DecisionResult, "decision"),
            (execution, ExecutionResult, "execution"),
        )
        for value, expected_type, name in expected:
            if value is not None and not isinstance(value, expected_type):
                raise InvalidReportData(f"{name} must be a {expected_type.__name__} or None.")

        decision_reasons = tuple(str(item) for item in decision.reasons) if decision is not None else ()
        decision_warnings = tuple(str(item) for item in decision.warnings) if decision is not None else ()

        if not stage_trace:
            stage_trace = tuple(
                name
                for present, name in (
                    (analysis is not None, "ANALYSIS"),
                    (profile is not None, "PROFILE"),
                    (score is not None, "SCORE"),
                    (decision is not None, "DECISION"),
                    (execution is not None, "EXECUTION"),
                )
                if present
            )

        execution_status = execution.status if execution is not None else None
        execution_message = str(execution.message) if execution is not None else ""
        order_id = execution.order_id if execution is not None else None

        resolved_failure_message = str(failure_message) if failure_message is not None else None
        if execution_status is ExecutionStatus.FAILED and not resolved_failure_message:
            resolved_failure_message = execution_message or "ExecutionEngine returned FAILED."

        if execution_status is ExecutionStatus.FAILED or failure_stage is not None or resolved_failure_message is not None:
            audit_status = ReportAuditStatus.FAILED
        elif all(value is not None for value, _, _ in expected):
            audit_status = ReportAuditStatus.COMPLETE
        else:
            audit_status = ReportAuditStatus.INCOMPLETE

        audit = ReportAudit(
            status=audit_status,
            stage_trace=tuple(str(item) for item in stage_trace),
            decision_reasons=decision_reasons,
            decision_warnings=decision_warnings,
            execution_status=execution_status,
            execution_message=execution_message,
            order_id=order_id,
            failure_stage=str(failure_stage) if failure_stage is not None else None,
            failure_message=resolved_failure_message,
        )

        normalized_warnings = tuple(str(item) for item in warnings)
        if resolved_failure_message is not None and resolved_failure_message not in normalized_warnings:
            normalized_warnings += (resolved_failure_message,)

        return ReportResult(
            symbol=symbol.strip(),
            analysis=analysis,
            profile=profile,
            score=score,
            decision=decision,
            execution=execution,
            summary=tuple(str(item) for item in summary),
            highlights=tuple(str(item) for item in highlights),
            warnings=normalized_warnings,
            metadata=ReportMetadata(
                project_version=self._project_version,
                report_name=report_name,
                execution_time_ms=max(float(execution_time_ms), 0.0),
            ),
            audit=audit,
        )

    def build_summary(self, report: ReportResult) -> tuple[str, ...]:
        if not isinstance(report, ReportResult):
            raise InvalidReportData("build_summary requires a ReportResult.")
        return report.summary

    def export_dict(self, report: ReportResult) -> dict[str, Any]:
        """Serialize the canonical contract without deriving a success flag."""
        if not isinstance(report, ReportResult):
            raise InvalidReportData("export_dict requires a ReportResult.")
        return self._to_serializable(report)

    def export_json(self, report: ReportResult, *, pretty: bool = True) -> str:
        return json.dumps(
            self.export_dict(report),
            indent=2 if pretty else None,
            ensure_ascii=False,
            sort_keys=True,
        )

    def save_json(self, report: ReportResult, output_path: str | Path, *, pretty: bool = True) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.export_json(report, pretty=pretty), encoding="utf-8")
        return path

    @staticmethod
    def _to_serializable(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if is_dataclass(value):
            return {field.name: ReportEngine._to_serializable(getattr(value, field.name)) for field in fields(value)}
        if isinstance(value, dict):
            return {str(key): ReportEngine._to_serializable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set, frozenset)):
            return [ReportEngine._to_serializable(item) for item in value]
        if hasattr(value, "tolist"):
            try:
                return value.tolist()
            except Exception:
                pass
        if isinstance(value, (str, int, float, bool)):
            return value
        return str(value)


__all__ = ["ReportEngine", "ReportEngineError", "InvalidReportData"]
