"""
===============================================================================
ORION
Module : models.report
Version: 2.1.0

Canonical Report domain contract with auditability metadata.
===============================================================================
"""

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
        object.__setattr__(
            self,
            "execution_time_ms",
            max(float(self.execution_time_ms), 0.0),
        )


class ReportAuditStatus(str, Enum):
    """Operational state of the evidence carried by a report."""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    FAILED = "FAILED"


@dataclass(slots=True, frozen=True)
class ReportAudit:
    """
    Evidence-only audit record for a ReportResult.

    This contract records facts supplied by upstream result contracts and the
    application pipeline. It does not calculate intelligence or decision
    semantics.
    """

    status: ReportAuditStatus = ReportAuditStatus.INCOMPLETE
    stage_trace: tuple[str, ...] = ()
    decision_reasons: tuple[str, ...] = ()
    decision_warnings: tuple[str, ...] = ()
    execution_status: Optional[ExecutionStatus] = None
    execution_message: str = ""
    order_id: Optional[str] = None
    failure_stage: Optional[str] = None
    failure_message: Optional[str] = None

    @property
    def execution_failed(self) -> bool:
        """Return True only when the canonical execution result is FAILED."""
        return self.execution_status is ExecutionStatus.FAILED

    @property
    def execution_executed(self) -> bool:
        """Return True only when the canonical execution result is EXECUTED."""
        return self.execution_status is ExecutionStatus.EXECUTED

    @property
    def has_failure(self) -> bool:
        """Return True when either execution or an upstream stage failed."""
        return self.execution_failed or self.failure_stage is not None


@dataclass(slots=True, frozen=True)
class ReportResult:
    """
    Canonical output of ReportBuilder / ReportEngine.

    ReportResult aggregates canonical results from preceding pipeline stages.
    It contains audit evidence but never generates business intelligence.
    """

    symbol: str
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
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
        """Expose the canonical execution failure state without inference."""
        return self.audit.execution_failed

    @property
    def is_complete(self) -> bool:
        """Return True when all canonical upstream result contracts exist."""
        return all(
            (
                self.analysis is not None,
                self.profile is not None,
                self.score is not None,
                self.decision is not None,
                self.execution is not None,
            )
        )


__all__ = [
    "ReportAuditStatus",
    "ReportAudit",
    "ReportMetadata",
    "ReportResult",
]
