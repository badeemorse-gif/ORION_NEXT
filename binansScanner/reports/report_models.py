"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : reports.report_models
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

Report data models representing immutable data structures for metadata,
symbol summaries, execution statistics, and complete diagnostic reports.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class ReportMetadata:
    """Immutable metadata container detailing report generation context."""
    generated_at: datetime
    project_version: str
    report_name: str
    execution_time_ms: float


@dataclass(frozen=True, slots=True)
class SymbolReport:
    """Immutable diagnostic report structure for an individual trading symbol."""
    symbol: str
    decision: str
    score: float
    confidence: float
    timeframes: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReportSummary:
    """Immutable statistical summary aggregating market scan results."""
    total_symbols: int
    buy_count: int
    sell_count: int
    hold_count: int
    execution_time_ms: float


@dataclass(frozen=True, slots=True)
class FullReport:
    """Immutable comprehensive report structure encompassing metadata, summary, and symbol details."""
    metadata: ReportMetadata
    summary: ReportSummary
    symbols: list[SymbolReport] = field(default_factory=list)


# =============================================================================
# End Of File
# =============================================================================