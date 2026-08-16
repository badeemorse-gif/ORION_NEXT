"""Canonical Signal Journal evidence contract.

The journal is an observational/audit boundary. It records what ORION knew at
signal time and keeps retrospective outcomes in a separate section so future
information cannot silently become part of the original observation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Any, ClassVar, Optional


class SignalFieldProvenance(str, Enum):
    """Provenance class for journal fields."""

    SIGNAL_TIME_OBSERVED = "SIGNAL_TIME_OBSERVED"
    RETROSPECTIVE_LABEL = "RETROSPECTIVE_LABEL"


@dataclass(slots=True, frozen=True)
class SignalObservation:
    """Immutable snapshot of evidence available at signal time only."""

    timestamp: datetime
    symbol: str
    timeframe: str
    raw_score: Optional[float] = None
    confidence: Optional[float] = None
    decision: Optional[str] = None
    market_regime: Optional[str] = None
    volume: Optional[float] = None
    relative_volume: Optional[float] = None
    volatility: Optional[float] = None
    relative_volatility: Optional[float] = None
    liquidity: Optional[float] = None
    momentum: Optional[float] = None
    multi_timeframe_alignment: Optional[str] = None
    reasons: tuple[str, ...] = ()

    FIELD_PROVENANCE: ClassVar[dict[str, SignalFieldProvenance]] = {
        "timestamp": SignalFieldProvenance.SIGNAL_TIME_OBSERVED,
        "symbol": SignalFieldProvenance.SIGNAL_TIME_OBSERVED,
        "timeframe": SignalFieldProvenance.SIGNAL_TIME_OBSERVED,
        "raw_score": SignalFieldProvenance.SIGNAL_TIME_OBSERVED,
        "confidence": SignalFieldProvenance.SIGNAL_TIME_OBSERVED,
        "decision": SignalFieldProvenance.SIGNAL_TIME_OBSERVED,
        "market_regime": SignalFieldProvenance.SIGNAL_TIME_OBSERVED,
        "volume": SignalFieldProvenance.SIGNAL_TIME_OBSERVED,
        "relative_volume": SignalFieldProvenance.SIGNAL_TIME_OBSERVED,
        "volatility": SignalFieldProvenance.SIGNAL_TIME_OBSERVED,
        "relative_volatility": SignalFieldProvenance.SIGNAL_TIME_OBSERVED,
        "liquidity": SignalFieldProvenance.SIGNAL_TIME_OBSERVED,
        "momentum": SignalFieldProvenance.SIGNAL_TIME_OBSERVED,
        "multi_timeframe_alignment": SignalFieldProvenance.SIGNAL_TIME_OBSERVED,
        "reasons": SignalFieldProvenance.SIGNAL_TIME_OBSERVED,
    }

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be a datetime.")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware.")
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string.")
        if not isinstance(self.timeframe, str) or not self.timeframe.strip():
            raise ValueError("timeframe must be a non-empty string.")
        object.__setattr__(self, "symbol", self.symbol.strip())
        object.__setattr__(self, "timeframe", self.timeframe.strip())
        object.__setattr__(self, "reasons", tuple(str(item) for item in self.reasons))
        for name in (
            "raw_score",
            "confidence",
            "volume",
            "relative_volume",
            "volatility",
            "relative_volatility",
            "liquidity",
            "momentum",
        ):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, (int, float)) or not isfinite(float(value))):
                raise ValueError(f"{name} must be a finite number or None.")

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe observation data without retrospective fields."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.astimezone(timezone.utc).isoformat()
        data["reasons"] = list(self.reasons)
        return data

    @classmethod
    def field_provenance(cls) -> dict[str, SignalFieldProvenance]:
        """Return the authoritative provenance map for observation fields."""
        return dict(cls.FIELD_PROVENANCE)


@dataclass(slots=True, frozen=True)
class SignalOutcome:
    """Retrospective labels and measurements appended after signal time.

    Outcome labels are intentionally opaque strings: the journal schema does not
    invent a win/loss rule, return formula, threshold, or forecasting method.
    MFE/MAE are scalar measurements whose unit is supplied by the retrospective
    labeling process via ``metric_unit``.
    """

    outcome_1h: Optional[str] = None
    outcome_4h: Optional[str] = None
    outcome_24h: Optional[str] = None
    mfe: Optional[float] = None
    mae: Optional[float] = None
    metric_unit: Optional[str] = None
    outcome_timestamp: Optional[datetime] = None

    FIELD_PROVENANCE: ClassVar[dict[str, SignalFieldProvenance]] = {
        "outcome_1h": SignalFieldProvenance.RETROSPECTIVE_LABEL,
        "outcome_4h": SignalFieldProvenance.RETROSPECTIVE_LABEL,
        "outcome_24h": SignalFieldProvenance.RETROSPECTIVE_LABEL,
        "mfe": SignalFieldProvenance.RETROSPECTIVE_LABEL,
        "mae": SignalFieldProvenance.RETROSPECTIVE_LABEL,
        "metric_unit": SignalFieldProvenance.RETROSPECTIVE_LABEL,
        "outcome_timestamp": SignalFieldProvenance.RETROSPECTIVE_LABEL,
    }

    def __post_init__(self) -> None:
        if self.outcome_timestamp is not None and (
            self.outcome_timestamp.tzinfo is None or self.outcome_timestamp.utcoffset() is None
        ):
            raise ValueError("outcome_timestamp must be timezone-aware.")
        for name in ("mfe", "mae"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, (int, float)) or not isfinite(float(value))):
                raise ValueError(f"{name} must be a finite number or None.")
        if (self.mfe is not None or self.mae is not None) and not self.metric_unit:
            raise ValueError("metric_unit is required when MFE or MAE is present.")
        if self.metric_unit is not None and not self.metric_unit.strip():
            raise ValueError("metric_unit must be non-empty when provided.")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.outcome_timestamp is not None:
            data["outcome_timestamp"] = self.outcome_timestamp.astimezone(timezone.utc).isoformat()
        return data

    @classmethod
    def field_provenance(cls) -> dict[str, SignalFieldProvenance]:
        return dict(cls.FIELD_PROVENANCE)


@dataclass(slots=True, frozen=True)
class SignalJournalEntry:
    """Auditable record separating signal-time evidence from later labels."""

    observation: SignalObservation
    outcome: Optional[SignalOutcome] = None

    def __post_init__(self) -> None:
        if self.outcome is not None and self.outcome.outcome_timestamp is not None:
            if self.outcome.outcome_timestamp < self.observation.timestamp:
                raise ValueError("outcome_timestamp cannot precede signal observation timestamp.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation": self.observation.to_dict(),
            "outcome": self.outcome.to_dict() if self.outcome is not None else None,
        }

    @property
    def outcome_attached(self) -> bool:
        return self.outcome is not None


__all__ = ["SignalFieldProvenance", "SignalObservation", "SignalOutcome", "SignalJournalEntry"]
