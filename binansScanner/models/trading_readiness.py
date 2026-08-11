"""
ORION
Module : models.trading_readiness
Version: 2.0.0

Future bot-readiness boundary.

This contract describes the information a future execution bot must validate
before it may consider an ORION Opportunity. It performs no order submission
and is not wired into the current Execution stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True, frozen=True)
class TradingReadiness:
    """Explicit gate state for a future bot consumer.

    Every prerequisite is represented independently so a future bot cannot
    infer permission merely from the existence of an Opportunity object.
    """

    intelligence_complete: bool
    confidence_acceptable: bool
    opportunity_fresh: bool
    risk_acceptable: bool
    market_conditions_valid: bool

    reasons: tuple[str, ...] = ()
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.evaluated_at.tzinfo is None or self.evaluated_at.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        object.__setattr__(self, "reasons", tuple(str(reason) for reason in self.reasons))

    @property
    def eligible(self) -> bool:
        """Whether every mandatory future-bot gate is satisfied."""

        return all(
            (
                self.intelligence_complete,
                self.confidence_acceptable,
                self.opportunity_fresh,
                self.risk_acceptable,
                self.market_conditions_valid,
            )
        )
