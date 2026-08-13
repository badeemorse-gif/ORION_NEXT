"""
Canonical Report Engine.

Execution safety is enforced at the report boundary as well as the pipeline
boundary: a failed execution can never be wrapped as a successful report.
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
from models.execution import ExecutionResult, ExecutionStatus
from models.profile import ProfileResult
from models.report import ReportMetadata, ReportResult
from models.score import ScoreResult

logger = logging.getLogger(__name__)


class ReportEngineError(Exception):
    """Base exception for canonical report-engine failures."""


class InvalidReportData(ReportEngineError):
    """Raised when required canonical report inputs are invalid."""


class ReportEngine:
    def __init__(self, project_version: str = "", logger_instance: Optional[logging.Logger] = None) -> None:
        self._project_version = project_version
        self._logger = logger_instance if logger_instance is not None else logger

    def build_report(self, *, symbol: str, analysis: Optional[AnalysisResult], profile: Optional[ProfileResult], score: Optional[ScoreResult], decision: Optional[DecisionResult], execution: Optional[ExecutionResult], summary: tuple[str, ...] = (), highlights: tuple[str, ...] = (), warnings: tuple[str, ...] = (), execution_time_ms: float = 0.0, report_name: str = "ORION Report") -> ReportResult:
        if not isinstance(symbol, str) or not symbol.strip():
            raise InvalidReportData("Report symbol must be a non-empty string.")
        if analysis is not None and not isinstance(analysis, AnalysisResult):
            raise InvalidReportData("analysis must be an AnalysisResult or None.")
        if profile is not None and not isinstance(profile, ProfileResult):
            raise InvalidReportData("profile must be a ProfileResult or None.")
        if score is not None and not isinstance(score, ScoreResult):
            raise InvalidReportData("score must be a ScoreResult or None.")
        if decision is not None and not isinstance(decision, DecisionResult):
            raise InvalidReportData("decision must be a DecisionResult or None.")
        if execution is not None and not isinstance(execution, ExecutionResult):
            raise InvalidReportData("execution must be an ExecutionResult or None.")
        if execution is not None and execution.status is ExecutionStatus.FAILED:
            raise InvalidReportData("A failed execution cannot produce a successful report.")

        metadata = ReportMetadata(project_version=self._project_version, report_name=report_name, execution_time_ms=max(float(execution_time_ms), 0.0))
        return ReportResult(symbol=symbol.strip(), analysis=analysis, profile=profile, score=score, decision=decision, execution=execution, summary=tuple(str(item) for item in summary), highlights=tuple(str(item) for item in highlights), warnings=tuple(str(item) for item in warnings), metadata=metadata)

    def build_summary(self, report: ReportResult) -> tuple[str, ...]:
        if not isinstance(report, ReportResult):
            raise InvalidReportData("build_summary requires a ReportResult.")
        return report.summary

    def export_dict(self, report: ReportResult) -> dict[str, Any]:
        if not isinstance(report, ReportResult):
            raise InvalidReportData("export_dict requires a ReportResult.")
        if report.execution is not None and report.execution.status is ExecutionStatus.FAILED:
            raise InvalidReportData("A failed execution cannot be exported as a report.")
        return self._to_serializable(report)

    def export_json(self, report: ReportResult, *, pretty: bool = True) -> str:
        return json.dumps(self.export_dict(report), indent=2 if pretty else None, ensure_ascii=False, sort_keys=True)

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
