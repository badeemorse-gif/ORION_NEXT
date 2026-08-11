"""
ORION
Module : models.opportunity
Version: 2.0.0

Future Trading Opportunity contracts.

This module is intentionally disconnected from the current pipeline. It defines
what a future opportunity consumer may exchange with ORION without coupling
Opportunity generation to Score, Decision, or Execution.
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


class OpportunityRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNACCEPTABLE = "UNACCEPTABLE"


@dataclass(slots=True, frozen=True)
class Opportunity:
    """A future near-term trading opportunity candidate.

    The contract carries evidence and validity state, but does not decide
    whether an order should be submitted. Missing optional market estimates
    remain explicit rather than being replaced by synthetic defaults.

    ``expected_move_pct`` is expressed as a percentage of the reference price
    used by the future opportunity engine.
    """

    symbol: str
    timeframe: str
    direction: OpportunityDirection
    confidence: float
    setup_quality: float
    risk: OpportunityRisk

    entry_candidate: Optional[float] = None
    invalidation: Optional[float] = None
    expected_move_pct: Optional[float] = None

    supporting_evidence: tuple[str, ...] = ()
    market_context: tuple[str, ...] = ()

    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    status: OpportunityStatus = OpportunityStatus.CANDIDATE

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if not self.timeframe.strip():
            raise ValueError("timeframe must be non-empty")
        if not isinstance(self.direction, OpportunityDirection):
            raise ValueError("direction must be OpportunityDirection")
        if not isinstance(self.risk, OpportunityRisk):
            raise ValueError("risk must be OpportunityRisk")
        if not isinstance(self.status, OpportunityStatus):
            raise ValueError("status must be OpportunityStatus")

        _bounded_finite(self.confidence, "confidence")
        _bounded_finite(self.setup_quality, "setup_quality")

        for name, value in (
            ("entry_candidate", self.entry_candidate),
            ("invalidation", self.invalidation),
            ("expected_move_pct", self.expected_move_pct),
        ):
            if value is not None:
                _finite(value, name)

        _aware(self.observed_at, "observed_at")
        if self.expires_at is not None:
            _aware(self.expires_at, "expires_at")
            if self.expires_at <= self.observed_at:
                raise ValueError("expires_at must be after observed_at")

        object.__setattr__(self, "supporting_evidence", tuple(str(x) for x in self.supporting_evidence))
        object.__setattr__(self, "market_context", tuple(str(x) for x in self.market_context))

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and datetime.now(timezone.utc) >= self.expires_at

    def is_fresh(self, at: Optional[datetime] = None) -> bool:
        """Return whether the opportunity is still within its declared window."""

        if self.status in {OpportunityStatus.EXPIRED, OpportunityStatus.REJECTED}:
            return False
        if self.expires_at is None:
            return True
        moment = at or datetime.now(timezone.utc)
        _aware(moment, "at")
        return moment < self.expires_at


def _finite(value: float, name: str) -> None:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite")


def _bounded_finite(value: float, name: str) -> None:
    _finite(value, name)
    if not 0.0 <= float(value) <= 100.0:
        raise ValueError(f"{name} must be between 0 and 100")


def _aware(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
