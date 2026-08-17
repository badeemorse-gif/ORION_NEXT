"""Canonical signal-time observation and retrospective outcome contracts."""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
import math
from typing import Any, ClassVar, Mapping, Optional


OBSERVED_EVIDENCE = "SIGNAL_TIME_OBSERVED"
RETROSPECTIVE_LABEL = "RETROSPECTIVE_LABEL"


@dataclass(frozen=True, slots=True)
class SignalObservation:
    """Immutable evidence that existed at signal time only."""

    timestamp: datetime
    symbol: str
    timeframe: str
    raw_score: float
    directional_raw_strength: Optional[float] = None
    context_score: Optional[float] = None
    composite: Optional[float] = None
    relative_rank: Optional[float] = None
    relative_percentile: Optional[float] = None
    confidence: float = 0.0
    decision: str = ""
    market_regime: str = ""
    volume: Optional[float] = None
    relative_volume: Optional[float] = None
    volatility: Optional[float] = None
    relative_volatility: Optional[float] = None
    liquidity: Optional[float] = None
    momentum: Optional[float] = None
    multi_timeframe_alignment: Optional[str] = None
    reasons: tuple[str, ...] = ()

    PROVENANCE: ClassVar[Mapping[str, str]] = {
        "timestamp": OBSERVED_EVIDENCE,
        "symbol": OBSERVED_EVIDENCE,
        "timeframe": OBSERVED_EVIDENCE,
        "raw_score": OBSERVED_EVIDENCE,
        "directional_raw_strength": OBSERVED_EVIDENCE,
        "context_score": OBSERVED_EVIDENCE,
        "composite": OBSERVED_EVIDENCE,
        "relative_rank": OBSERVED_EVIDENCE,
        "relative_percentile": OBSERVED_EVIDENCE,
        "confidence": OBSERVED_EVIDENCE,
        "decision": OBSERVED_EVIDENCE,
        "market_regime": OBSERVED_EVIDENCE,
        "volume": OBSERVED_EVIDENCE,
        "relative_volume": OBSERVED_EVIDENCE,
        "volatility": OBSERVED_EVIDENCE,
        "relative_volatility": OBSERVED_EVIDENCE,
        "liquidity": OBSERVED_EVIDENCE,
        "momentum": OBSERVED_EVIDENCE,
        "multi_timeframe_alignment": OBSERVED_EVIDENCE,
        "reasons": OBSERVED_EVIDENCE,
    }

    def __post_init__(self) -> None:
        _require_timezone_aware(self.timestamp, "timestamp")
        object.__setattr__(self, "symbol", str(self.symbol).strip())
        object.__setattr__(self, "timeframe", str(self.timeframe).strip())
        object.__setattr__(self, "decision", str(self.decision).strip())
        object.__setattr__(self, "market_regime", str(self.market_regime).strip())
        object.__setattr__(self, "raw_score", float(self.raw_score))
        object.__setattr__(self, "confidence", float(self.confidence))
        for field_name in (
            "directional_raw_strength",
            "context_score",
            "composite",
            "relative_rank",
            "relative_percentile",
            "volume",
            "relative_volume",
            "volatility",
            "relative_volatility",
            "liquidity",
            "momentum",
        ):
            value = getattr(self, field_name)
            if value is not None:
                numeric_value = float(value)
                if field_name in {
                    "directional_raw_strength",
                    "context_score",
                    "composite",
                } and not math.isfinite(numeric_value):
                    raise ValueError(f"{field_name} must be a finite numeric value")
                object.__setattr__(self, field_name, numeric_value)
        if self.multi_timeframe_alignment is not None:
            object.__setattr__(
                self,
                "multi_timeframe_alignment",
                str(self.multi_timeframe_alignment).strip(),
            )
        object.__setattr__(self, "reasons", tuple(str(reason) for reason in self.reasons))
        if not self.symbol:
            raise ValueError("symbol must be non-empty")
        if not self.timeframe:
            raise ValueError("timeframe must be non-empty")
        if not self.decision:
            raise ValueError("decision must be non-empty")
        if not self.market_regime:
            raise ValueError("market_regime must be non-empty")
        if self.relative_percentile is not None and not 0.0 <= self.relative_percentile <= 100.0:
            raise ValueError("relative_percentile must be between 0 and 100")

    @classmethod
    def field_provenance(cls) -> dict[str, str]:
        return dict(cls.PROVENANCE)


@dataclass(frozen=True, slots=True)
class SignalOutcome:
    """Retrospective labels computed only after the signal timestamp."""

    outcome_1h: Optional[float] = None
    outcome_4h: Optional[float] = None
    outcome_24h: Optional[float] = None
    mfe: Optional[float] = None
    mae: Optional[float] = None
    outcome_timestamp: Optional[datetime] = None
    metric_unit: Optional[str] = None

    PROVENANCE: ClassVar[Mapping[str, str]] = {
        "outcome_1h": RETROSPECTIVE_LABEL,
        "outcome_4h": RETROSPECTIVE_LABEL,
        "outcome_24h": RETROSPECTIVE_LABEL,
        "mfe": RETROSPECTIVE_LABEL,
        "mae": RETROSPECTIVE_LABEL,
        "outcome_timestamp": RETROSPECTIVE_LABEL,
        "metric_unit": RETROSPECTIVE_LABEL,
    }

    def __post_init__(self) -> None:
        for field_name in ("outcome_1h", "outcome_4h", "outcome_24h", "mfe", "mae"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, float(value))
        if self.outcome_timestamp is not None:
            _require_timezone_aware(self.outcome_timestamp, "outcome_timestamp")
        if self.metric_unit is not None:
            normalized = str(self.metric_unit).strip()
            object.__setattr__(self, "metric_unit", normalized)
            if not normalized:
                raise ValueError("metric_unit must be non-empty when provided")
        if (self.mfe is not None or self.mae is not None) and not self.metric_unit:
            raise ValueError("metric_unit is required when MFE or MAE is provided")

    @classmethod
    def field_provenance(cls) -> dict[str, str]:
        return dict(cls.PROVENANCE)


@dataclass(frozen=True, slots=True)
class SignalJournalEntry:
    """Auditable pairing of immutable signal-time evidence and later labels."""

    observation: SignalObservation
    outcome: Optional[SignalOutcome] = None

    def __post_init__(self) -> None:
        if self.outcome is not None and self.outcome.outcome_timestamp is not None:
            if self.outcome.outcome_timestamp < self.observation.timestamp:
                raise ValueError("outcome_timestamp cannot precede observation timestamp")

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation": _serialize(self.observation),
            "outcome": _serialize(self.outcome) if self.outcome is not None else None,
        }

    @classmethod
    def field_provenance(cls) -> dict[str, str]:
        provenance = {
            f"observation.{key}": value
            for key, value in SignalObservation.PROVENANCE.items()
        }
        provenance.update(
            {
                f"outcome.{key}": value
                for key, value in SignalOutcome.PROVENANCE.items()
            }
        )
        return provenance


@dataclass(frozen=True, slots=True)
class SignalJournal:
    """Immutable append-only collection representing the official experiment journal."""

    entries: tuple[SignalJournalEntry, ...] = ()

    def record(self, entry: SignalJournalEntry) -> "SignalJournal":
        """Return a new journal containing ``entry``; existing records never mutate."""
        if not isinstance(entry, SignalJournalEntry):
            raise TypeError("entry must be a SignalJournalEntry")
        return SignalJournal(entries=self.entries + (entry,))

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [_serialize(entry) for entry in self.entries]}

    def __len__(self) -> int:
        return len(self.entries)


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _serialize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            field.name: _serialize(getattr(value, field.name))
            for field in fields(value)
        }
    return value


__all__ = [
    "OBSERVED_EVIDENCE",
    "RETROSPECTIVE_LABEL",
    "SignalObservation",
    "SignalOutcome",
    "SignalJournalEntry",
    "SignalJournal",
]
