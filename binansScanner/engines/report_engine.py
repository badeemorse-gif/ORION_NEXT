"""Canonical Report Engine.

The engine aggregates canonical result contracts and makes their evidence
operationally visible. It does not generate intelligence or decision logic.
"""

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
from models.execution import ExecutionResult
from models.profile import ProfileResult
from models.report import (
    ReportAudit,
    ReportAuditStatus,
    ReportMetadata,
    ReportResult,
)
from models.score import ScoreResult

logger = logging.getLogger(__name__)


class ReportEngineError(Exception):
    """Base exception for canonical report-engine failures."""


class InvalidReportData(ReportEngineError):
    """Raised when required canonical report inputs are invalid."""


class ReportEngine:
    """Aggregate upstream evidence into the canonical ReportResult."""

    def __init__(
        self,
        project_version: str = "",
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
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
        """Build a report from already-computed canonical contracts only."""
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
                raise InvalidReportData(
                    f"{name} must be a {expected_type.__name__} or None."
                )

        if decision is not None:
            decision_reasons = tuple(str(item) for item in decision.reasons)
            decision_warnings = tuple(str(item) for item in decision.warnings)
        else:
            decision_reasons = ()
            decision_warnings = ()

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
        execution_message = execution.message if execution is not None else ""
        order_id = execution.order_id if execution is not None else None

        if execution_status is not None and execution_status.value == "FAILED":
            audit_status = ReportAuditStatus.FAILED
        elif failure_stage is not None:
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
            execution_message=str(execution_message),
            order_id=order_id,
            failure_stage=failure_stage,
            failure_message=(
                str(failure_message) if failure_message is not None else None
            ),
        )

        metadata = ReportMetadata(
            project_version=self._project_version,
            report_name=report_name,
            execution_time_ms=max(float(execution_time_ms), 0.0),
        )

        normalized_warnings = tuple(str(item) for item in warnings)
        if failure_message is not None:
            normalized_warnings = normalized_warnings + (str(failure_message),)

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
            metadata=metadata,
            audit=audit,
        )

    def build_summary(self, report: ReportResult) -> tuple[str, ...]:
        if not isinstance(report, ReportResult):
            raise InvalidReportData("build_summary requires a ReportResult.")
        return report.summary

    def export_dict(self, report: ReportResult) -> dict[str, Any]:
        if not isinstance(report, ReportResult):
            raise InvalidReportData("export_dict requires a ReportResult.")
        return self._to_serializable(report)

    def export_json(self, report: ReportResult, *, pretty: bool = True) -> str:
        data = self.export_dict(report)
        return json.dumps(
            data,
            indent=2 if pretty else None,
            ensure_ascii=False,
            sort_keys=True,
        )

    def save_json(
        self,
        report: ReportResult,
        output_path: str | Path,
        *,
        pretty: bool = True,
    ) -> Path:
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
            return {
                field.name: ReportEngine._to_serializable(getattr(value, field.name))
                for field in fields(value)
            }
        if isinstance(value, dict):
            return {
                str(key): ReportEngine._to_serializable(item)
                for key, item in value.items()
            }
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
