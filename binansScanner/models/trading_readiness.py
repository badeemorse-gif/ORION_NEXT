"""Future ORION trading-bot readiness contract.

This module defines a future consumer-side gate only. It performs no order
submission, has no Binance dependency, and is not wired into the current
Execution stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True, frozen=True)
class TradingReadiness:
    """Explicit fail-closed prerequisites for a future trading bot.

    The contract deliberately separates intelligence validity from execution
    intent. A bot may only proceed when every mandatory prerequisite is true.
    """

    intelligence_complete: bool
    confidence_acceptable: bool
    opportunity_fresh: bool
    risk_acceptable: bool
    market_conditions_valid: bool

    reasons: tuple[str, ...] = ()
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        for name in (
            "intelligence_complete",
            "confidence_acceptable",
            "opportunity_fresh",
            "risk_acceptable",
            "market_conditions_valid",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be bool")

        if (
            not isinstance(self.evaluated_at, datetime)
            or self.evaluated_at.tzinfo is None
            or self.evaluated_at.utcoffset() is None
        ):
            raise ValueError("evaluated_at must be timezone-aware")

        object.__setattr__(self, "reasons", tuple(str(reason) for reason in self.reasons))

    @property
    def eligible(self) -> bool:
        """Return True only when every mandatory readiness gate is satisfied."""

        return all(
            (
                self.intelligence_complete,
                self.confidence_acceptable,
                self.opportunity_fresh,
                self.risk_acceptable,
                self.market_conditions_valid,
            )
        )
