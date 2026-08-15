"""Future ORION Trading Opportunity contract.

This module is isolated from the current pipeline and contains no execution logic.
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
    state: RiskState = RiskState.UNKNOWN
    invalidation: Optional[str] = None
    notes: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class Opportunity:
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
        if not self.symbol.strip() or not self.timeframe.strip():
            raise ValueError("symbol and timeframe must be non-empty")
        for name, value in (("entry_candidate", self.entry_candidate), ("expected_move", self.expected_move)):
            if value is not None and not isfinite(float(value)):
                raise ValueError(f"{name} must be finite when provided")
        for name, value in (("confidence", self.confidence), ("setup_quality", self.setup_quality)):
            if value is not None:
                numeric = float(value)
                if not isfinite(numeric) or not 0.0 <= numeric <= 100.0:
                    raise ValueError(f"{name} must be finite and between 0 and 100")
        if self.expires_at is not None and self.expires_at < self.generated_at:
            raise ValueError("expires_at cannot precede generated_at")

    @property
    def is_complete(self) -> bool:
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
        return (
            self.is_complete
            and self.status is OpportunityStatus.ACTIVE
            and self.freshness is FreshnessStatus.FRESH
            and self.risk.state is RiskState.ACCEPTABLE
            and not self.is_expired
        )

    @property
    def is_expired(self) -> bool:
        return self.status is OpportunityStatus.EXPIRED or (
            self.expires_at is not None and datetime.now(timezone.utc) >= self.expires_at
        )
