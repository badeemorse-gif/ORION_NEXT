"""
ORION — Future Trading Opportunity contracts.

This module is intentionally independent from the current pipeline.
It defines the future consumer-facing contract for near-term scalping
opportunities without changing Analysis, Profile, Score, Decision, or
Execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Optional


class OpportunityDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class OpportunityStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


class FreshnessStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class RiskState(str, Enum):
    ACCEPTABLE = "ACCEPTABLE"
    ELEVATED = "ELEVATED"
    UNACCEPTABLE = "UNACCEPTABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(slots=True, frozen=True)
class OpportunityRisk:
    """Risk context supplied by future intelligence/risk layers."""

    state: RiskState = RiskState.UNKNOWN
    invalidation: Optional[str] = None
    notes: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class Opportunity:
    """Canonical future representation of a near-term opportunity.

    This contract carries evidence and state; it does not calculate scores,
    trading thresholds, or execution instructions.
    """

    symbol: str
    timeframe: str
    direction: OpportunityDirection

    entry_candidate: Optional[float] = None
    confidence: Optional[float] = None
    setup_quality: Optional[float] = None

    risk: OpportunityRisk = field(default_factory=OpportunityRisk)
    expected_move: Optional[float] = None

    supporting_evidence: tuple[str, ...] = ()
    market_context: tuple[str, ...] = ()

    freshness: FreshnessStatus = FreshnessStatus.UNKNOWN
    status: OpportunityStatus = OpportunityStatus.CANDIDATE
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if not self.timeframe.strip():
            raise ValueError("timeframe must be non-empty")

        for name, value in (
            ("entry_candidate", self.entry_candidate),
            ("expected_move", self.expected_move),
        ):
            if value is not None and not isfinite(float(value)):
                raise ValueError(f"{name} must be finite when provided")

        for name, value in (
            ("confidence", self.confidence),
            ("setup_quality", self.setup_quality),
        ):
            if value is not None:
                numeric = float(value)
                if not isfinite(numeric) or not 0.0 <= numeric <= 100.0:
                    raise ValueError(f"{name} must be finite and between 0 and 100")

        if self.expires_at is not None and self.expires_at < self.generated_at:
            raise ValueError("expires_at cannot precede generated_at")

    @property
    def is_complete(self) -> bool:
        """Whether the contract contains the minimum intelligence needed by a future consumer."""

        return (
            self.entry_candidate is not None
            and self.confidence is not None
            and self.setup_quality is not None
            and bool(self.supporting_evidence)
            and self.risk.state is not RiskState.UNKNOWN
            and self.freshness is not FreshnessStatus.UNKNOWN
        )

    @property
    def is_eligible(self) -> bool:
        """Conservative gate for future consumers; no numeric trading threshold is embedded."""

        return (
            self.is_complete
            and self.status is OpportunityStatus.ACTIVE
            and self.freshness is FreshnessStatus.FRESH
            and self.risk.state is RiskState.ACCEPTABLE
        )

    @property
    def is_expired(self) -> bool:
        if self.status is OpportunityStatus.EXPIRED:
            return True
        return self.expires_at is not None and datetime.now(timezone.utc) >= self.expires_at
