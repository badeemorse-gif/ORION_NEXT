"""Canonical Report domain contract with explicit auditability semantics."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.execution import ExecutionResult, ExecutionStatus
from models.profile import ProfileResult
from models.score import ScoreResult


@dataclass(slots=True, frozen=True)
class ReportMetadata:
    """Metadata describing report generation context."""

    project_version: str = ""
    report_name: str = "ORION Report"
    execution_time_ms: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "execution_time_ms", max(float(self.execution_time_ms), 0.0))


class ReportAuditStatus(str, Enum):
    """Official status of the evidence carried by a report."""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    FAILED = "FAILED"


@dataclass(slots=True, frozen=True)
class ReportAudit:
    """Evidence-only audit contract; it never creates intelligence or decisions."""

    status: ReportAuditStatus = ReportAuditStatus.INCOMPLETE
    stage_trace: tuple[str, ...] = ()
    decision_reasons: tuple[str, ...] = ()
    decision_warnings: tuple[str, ...] = ()
    execution_status: Optional[ExecutionStatus] = None
    execution_message: str = ""
    order_id: Optional[str] = None
    failure_stage: Optional[str] = None
    failure_message: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ReportAuditStatus):
            object.__setattr__(self, "status", ReportAuditStatus(str(self.status).strip().upper()))
        if self.execution_status is not None and not isinstance(self.execution_status, ExecutionStatus):
            object.__setattr__(self, "execution_status", ExecutionStatus(str(self.execution_status).strip().upper()))
        if self.status is ReportAuditStatus.FAILED:
            if self.execution_status is not ExecutionStatus.FAILED and not self.failure_stage and not self.failure_message:
                raise ValueError("FAILED audit status requires failure evidence.")
        elif self.execution_status is ExecutionStatus.FAILED:
            raise ValueError("ExecutionStatus.FAILED requires ReportAuditStatus.FAILED.")
        elif self.status is ReportAuditStatus.COMPLETE and (self.failure_stage or self.failure_message):
            raise ValueError("COMPLETE audit status cannot contain failure evidence.")

    @property
    def execution_failed(self) -> bool:
        """True only when the canonical execution contract reports FAILED."""
        return self.execution_status is ExecutionStatus.FAILED

    @property
    def execution_succeeded(self) -> bool:
        """True only when execution evidence explicitly reports EXECUTED."""
        return self.execution_status is ExecutionStatus.EXECUTED

    @property
    def has_failure(self) -> bool:
        """True only when the report carries failed-stage evidence."""
        return self.status is ReportAuditStatus.FAILED


@dataclass(slots=True, frozen=True)
class ReportResult:
    """Canonical report result aggregating upstream evidence without generating intelligence."""

    symbol: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    analysis: Optional[AnalysisResult] = None
    profile: Optional[ProfileResult] = None
    score: Optional[ScoreResult] = None
    decision: Optional[DecisionResult] = None
    execution: Optional[ExecutionResult] = None
    summary: tuple[str, ...] = ()
    highlights: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: ReportMetadata = field(default_factory=ReportMetadata)
    audit: ReportAudit = field(default_factory=ReportAudit)

    def __post_init__(self) -> None:
        if self.audit.status is ReportAuditStatus.COMPLETE:
            if not self.is_complete:
                raise ValueError("COMPLETE report audit requires all canonical upstream results.")
            if self.audit.execution_status is None:
                raise ValueError("COMPLETE report audit requires execution_status.")

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)

    @property
    def has_analysis(self) -> bool:
        return self.analysis is not None

    @property
    def has_profile(self) -> bool:
        return self.profile is not None

    @property
    def has_score(self) -> bool:
        return self.score is not None

    @property
    def has_decision(self) -> bool:
        return self.decision is not None

    @property
    def has_execution(self) -> bool:
        return self.execution is not None

    @property
    def execution_failed(self) -> bool:
        return self.audit.execution_failed

    @property
    def execution_succeeded(self) -> bool:
        """Expose execution success evidence only; this is not pipeline success."""
        return self.audit.execution_succeeded

    @property
    def is_complete(self) -> bool:
        """Structural completeness of the canonical upstream result set only."""
        return all((
            self.analysis is not None,
            self.profile is not None,
            self.score is not None,
            self.decision is not None,
            self.execution is not None,
        ))


__all__ = ["ReportAuditStatus", "ReportAudit", "ReportMetadata", "ReportResult"]
