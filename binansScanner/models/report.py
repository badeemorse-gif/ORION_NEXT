"""
===============================================================================
ORION
Module : models.report
Version: 2.0.0

Canonical Report domain contract.

Architectural boundary:
    AnalysisResult
        +
    ProfileResult
        +
    ScoreResult
        +
    DecisionResult
        +
    ExecutionResult
        ↓
    ReportResult

ReportResult is a domain result contract.

It must not:
    - contain MarketDataset as pipeline state;
    - execute analysis logic;
    - depend on API / GUI / Scheduler;
    - depend on report renderers;
    - depend on export formats;
    - depend on engine-local result classes.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.execution import ExecutionResult
from models.profile import ProfileResult
from models.score import ScoreResult


@dataclass(slots=True, frozen=True)
class ReportMetadata:
    """
    Metadata describing report generation context.

    Metadata is descriptive only and must not contain pipeline state.
    """

    project_version: str = ""
    report_name: str = "ORION Report"
    execution_time_ms: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "execution_time_ms",
            max(float(self.execution_time_ms), 0.0),
        )


@dataclass(slots=True, frozen=True)
class ReportResult:
    """
    Canonical output of ReportBuilder / ReportEngine.

    ReportResult aggregates canonical results from the preceding pipeline
    stages without converting them into engine-local or export-specific
    representations.

    The contained result contracts remain the authoritative source of their
    respective domain information.
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

    metadata: ReportMetadata = field(
        default_factory=ReportMetadata
    )

    @property
    def has_warnings(self) -> bool:
        """Return True when report warnings are present."""
        return bool(self.warnings)

    @property
    def has_analysis(self) -> bool:
        """Return True when an AnalysisResult is attached."""
        return self.analysis is not None

    @property
    def has_profile(self) -> bool:
        """Return True when a ProfileResult is attached."""
        return self.profile is not None

    @property
    def has_score(self) -> bool:
        """Return True when a ScoreResult is attached."""
        return self.score is not None

    @property
    def has_decision(self) -> bool:
        """Return True when a DecisionResult is attached."""
        return self.decision is not None

    @property
    def has_execution(self) -> bool:
        """Return True when an ExecutionResult is attached."""
        return self.execution is not None

    @property
    def is_complete(self) -> bool:
        """
        Return True when all canonical upstream result contracts exist.

        This property describes structural completeness only.
        It does not perform business validation.
        """

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
    "ReportMetadata",
    "ReportResult",
]