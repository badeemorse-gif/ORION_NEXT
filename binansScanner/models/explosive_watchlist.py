"""
ORION — Future Explosive Watchlist contracts.

The watchlist is an independent probabilistic radar. It is not a trading
signal, does not modify Scalping Opportunities, and is not connected to the
current pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Optional

from .opportunity import FreshnessStatus


class WatchlistStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    MONITOR = "MONITOR"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


@dataclass(slots=True, frozen=True)
class ExplosiveWatchCandidate:
    """Probabilistic evidence package for a possible strong future move."""

    symbol: str
    timeframe_window: str

    move_probability: Optional[float] = None
    readiness_score: Optional[float] = None
    confidence: Optional[float] = None

    freshness: FreshnessStatus = FreshnessStatus.UNKNOWN
    supporting_signals: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()

    estimated_time_window: Optional[str] = None
    status: WatchlistStatus = WatchlistStatus.CANDIDATE

    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if not self.timeframe_window.strip():
            raise ValueError("timeframe_window must be non-empty")

        for name, value in (
            ("move_probability", self.move_probability),
            ("readiness_score", self.readiness_score),
            ("confidence", self.confidence),
        ):
            if value is not None:
                numeric = float(value)
                if not isfinite(numeric) or not 0.0 <= numeric <= 100.0:
                    raise ValueError(f"{name} must be finite and between 0 and 100")

        if self.expires_at is not None and self.expires_at < self.generated_at:
            raise ValueError("expires_at cannot precede generated_at")

    @property
    def is_complete(self) -> bool:
        return (
            self.move_probability is not None
            and self.readiness_score is not None
            and self.confidence is not None
            and self.freshness is not FreshnessStatus.UNKNOWN
            and bool(self.supporting_signals)
            and bool(self.invalidation_conditions)
        )

    @property
    def is_monitorable(self) -> bool:
        """Future watchlist gate; no claim of deterministic price prediction."""

        return (
            self.is_complete
            and self.status is WatchlistStatus.MONITOR
            and self.freshness is FreshnessStatus.FRESH
            and not self.is_expired
        )

    @property
    def is_expired(self) -> bool:
        if self.status is WatchlistStatus.EXPIRED:
            return True
        return self.expires_at is not None and datetime.now(timezone.utc) >= self.expires_at
