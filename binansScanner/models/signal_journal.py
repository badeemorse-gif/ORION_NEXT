"""Canonical signal-time observation and retrospective outcome contracts."""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timezone
import math
from typing import Any, ClassVar, Mapping, Optional


OBSERVED_EVIDENCE = "SIGNAL_TIME_OBSERVED"
RETROSPECTIVE_LABEL = "RETROSPECTIVE_LABEL"


def _utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _finite(value: float, field_name: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite")
    return numeric


@dataclass(frozen=True, slots=True)
class SignalObservation:
    """Immutable evidence available at signal time only."""

    observation_id: str
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
        field.name: OBSERVED_EVIDENCE
        for field in fields(__class__) if not field.name.startswith("_")
    } if False else {}

    def __post_init__(self) -> None:
        if not str(self.observation_id).strip():
            raise ValueError("observation_id must be non-empty")
        timestamp = _utc(self.timestamp, "timestamp")
        if not str(self.symbol).strip() or not str(self.timeframe).strip():
            raise ValueError("symbol and timeframe must be non-empty")
        if not str(self.decision).strip():
            raise ValueError("decision must be non-empty")
        if not str(self.market_regime).strip():
            raise ValueError("market_regime must be non-empty")
        object.__setattr__(self, "observation_id", str(self.observation_id).strip())
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", str(self.symbol).strip())
        object.__setattr__(self, "timeframe", str(self.timeframe).strip())
        object.__setattr__(self, "decision", str(self.decision).strip())
        object.__setattr__(self, "market_regime", str(self.market_regime).strip())
        object.__setattr__(self, "raw_score", _finite(self.raw_score, "raw_score"))
        object.__setattr__(self, "confidence", _finite(self.confidence, "confidence"))
        for name in ("directional_raw_strength", "context_score", "composite", "relative_rank", "relative_percentile", "volume", "relative_volume", "volatility", "relative_volatility", "liquidity", "momentum"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _finite(value, name))
        if self.relative_percentile is not None and not 0.0 <= self.relative_percentile <= 100.0:
            raise ValueError("relative_percentile must be between 0 and 100")
        if self.multi_timeframe_alignment is not None:
            object.__setattr__(self, "multi_timeframe_alignment", str(self.multi_timeframe_alignment).strip())
        object.__setattr__(self, "reasons", tuple(str(reason) for reason in self.reasons))

    @classmethod
    def field_provenance(cls) -> dict[str, str]:
        return {
            "observation_id": OBSERVED_EVIDENCE,
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


@dataclass(frozen=True, slots=True)
class SignalOutcome:
    """Retrospective labels measured strictly after signal time."""

    outcome_1h: Optional[float] = None
    outcome_4h: Optional[float] = None
    outcome_24h: Optional[float] = None
    mfe: Optional[float] = None
    mae: Optional[float] = None
    outcome_timestamp: Optional[datetime] = None
    metric_unit: Optional[str] = None

    @classmethod
    def field_provenance(cls) -> dict[str, str]:
        return {name: RETROSPECTIVE_LABEL for name in ("outcome_1h", "outcome_4h", "outcome_24h", "mfe", "mae", "outcome_timestamp", "metric_unit")}

    def __post_init__(self) -> None:
        for name in ("outcome_1h", "outcome_4h", "outcome_24h", "mfe", "mae"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _finite(value, name))
        if self.outcome_timestamp is not None:
            object.__setattr__(self, "outcome_timestamp", _utc(self.outcome_timestamp, "outcome_timestamp"))
        if self.metric_unit is not None:
            unit = str(self.metric_unit).strip()
            if not unit:
                raise ValueError("metric_unit must be non-empty when provided")
            object.__setattr__(self, "metric_unit", unit)
        if (self.mfe is not None or self.mae is not None) and not self.metric_unit:
            raise ValueError("metric_unit is required when MFE or MAE is provided")


@dataclass(frozen=True, slots=True)
class SignalJournalEntry:
    observation: SignalObservation
    outcome: Optional[SignalOutcome] = None

    def __post_init__(self) -> None:
        if self.outcome is not None and self.outcome.outcome_timestamp is not None:
            if self.outcome.outcome_timestamp <= self.observation.timestamp:
                raise ValueError("outcome_timestamp must be strictly after observation timestamp")

    def to_dict(self) -> dict[str, Any]:
        return {"observation": self.observation, "outcome": self.outcome}

    @classmethod
    def field_provenance(cls) -> dict[str, str]:
        return {
            **{f"observation.{k}": v for k, v in SignalObservation.field_provenance().items()},
            **{f"outcome.{k}": v for k, v in SignalOutcome.field_provenance().items()},
        }


@dataclass(frozen=True, slots=True)
class SignalJournal:
    entries: tuple[SignalJournalEntry, ...] = ()

    def record(self, entry: SignalJournalEntry) -> "SignalJournal":
        if not isinstance(entry, SignalJournalEntry):
            raise TypeError("entry must be a SignalJournalEntry")
        return SignalJournal(self.entries + (entry,))

    def __len__(self) -> int:
        return len(self.entries)


__all__ = ["OBSERVED_EVIDENCE", "RETROSPECTIVE_LABEL", "SignalObservation", "SignalOutcome", "SignalJournalEntry", "SignalJournal"]
