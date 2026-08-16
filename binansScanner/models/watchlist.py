"""
ORION
Module : models.watchlist
Version: 2.0.0

Future Explosive Watchlist contracts.

This is a probabilistic research/watchlist boundary. It is deliberately
independent from Scalping Opportunities and from the current Score/Decision
pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Optional


class WatchlistStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    WATCH = "WATCH"
    STALE = "STALE"
    REJECTED = "REJECTED"


class EstimateKind(str, Enum):
    PROBABILISTIC = "PROBABILISTIC"


@dataclass(slots=True, frozen=True)
class ExplosiveWatchCandidate:
    """Evidence-backed candidate for a potentially strong future move.

    ``strong_move_probability`` is an estimate, not a price prediction. The
    contract intentionally has no promised return or deterministic future
    outcome field.
    """

    symbol: str
    timeframe: str
    strong_move_probability: float
    readiness_score: float
    confidence: float

    supporting_signals: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()

    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    status: WatchlistStatus = WatchlistStatus.CANDIDATE
    estimate_kind: EstimateKind = EstimateKind.PROBABILISTIC

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if not self.timeframe.strip():
            raise ValueError("timeframe must be non-empty")
        if not isinstance(self.status, WatchlistStatus):
            raise ValueError("status must be WatchlistStatus")
        if self.estimate_kind is not EstimateKind.PROBABILISTIC:
            raise ValueError("watchlist estimates must remain probabilistic")

        _bounded(self.strong_move_probability, "strong_move_probability", 0.0, 1.0)
        _bounded(self.readiness_score, "readiness_score", 0.0, 100.0)
        _bounded(self.confidence, "confidence", 0.0, 100.0)

        _aware(self.observed_at, "observed_at")
        if self.window_start is not None:
            _aware(self.window_start, "window_start")
        if self.window_end is not None:
            _aware(self.window_end, "window_end")
        if self.window_start and self.window_end and self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")

        object.__setattr__(self, "supporting_signals", tuple(str(x) for x in self.supporting_signals))
        object.__setattr__(self, "invalidation_conditions", tuple(str(x) for x in self.invalidation_conditions))

    def is_fresh(self, at: Optional[datetime] = None) -> bool:
        if self.status in {WatchlistStatus.STALE, WatchlistStatus.REJECTED}:
            return False
        moment = at or datetime.now(timezone.utc)
        _aware(moment, "at")
        return self.window_end is None or moment < self.window_end


def _bounded(value: float, name: str, low: float, high: float) -> None:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not isfinite(numeric) or not low <= numeric <= high:
        raise ValueError(f"{name} must be finite and between {low} and {high}")


def _aware(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
