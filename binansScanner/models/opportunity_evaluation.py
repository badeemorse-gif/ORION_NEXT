"""Future evaluation boundary for Scalping Opportunity selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .opportunity import Opportunity

class OpportunityEvaluationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"

@dataclass(slots=True, frozen=True)
class OpportunityEvaluation:
    opportunity: Opportunity
    status: OpportunityEvaluationStatus
    reasons: tuple[str, ...] = ()
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.opportunity, Opportunity):
            raise ValueError("opportunity must be an Opportunity")
        if not isinstance(self.status, OpportunityEvaluationStatus):
            raise ValueError("status must be OpportunityEvaluationStatus")
        if not isinstance(self.evaluated_at, datetime) or self.evaluated_at.tzinfo is None or self.evaluated_at.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        object.__setattr__(self, "reasons", tuple(str(reason) for reason in self.reasons))
        if self.status is OpportunityEvaluationStatus.ACCEPTED and not self.opportunity.is_eligible:
            raise ValueError("an ineligible Opportunity cannot be accepted")
        if self.status is OpportunityEvaluationStatus.REJECTED and not self.reasons:
            raise ValueError("rejected evaluations must include at least one reason")

    @property
    def accepted(self) -> bool:
        return self.status is OpportunityEvaluationStatus.ACCEPTED
