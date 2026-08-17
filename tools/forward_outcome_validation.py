"""Forward-outcome validation and calibration analysis for ORION Phase A.

This module consumes immutable historical Observations and ExperimentFixtures.
It does not modify Production contracts, recalculate score/decision, or execute
orders. Forward data is deliberately kept outside Observation.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import mean
from typing import Mapping, Sequence

from tools.experiment_harness import (
    HORIZON_NAMES,
    HORIZONS_HOURS,
    ExperimentContractError,
    ExperimentFixture,
    ExperimentHarness,
    ForwardOutcome,
    Observation,
)

HORIZONS: tuple[str, ...] = tuple(HORIZON_NAMES[h] for h in HORIZONS_HOURS)
CONFIDENCE_BAND_COUNT = 5
RELATIVE_RANK_BAND_COUNT = 5

@dataclass(frozen=True, slots=True)
class HistoricalObservation:
    fixture: ExperimentFixture
    observation: Observation
    score: float
    relative_rank: float

    def __post_init__(self) -> None:
        if self.fixture.fixture_id != self.observation.fixture_id:
            raise ExperimentContractError("Fixture and observation ids do not match.")
        if self.fixture.symbol != self.observation.symbol:
            raise ExperimentContractError("Fixture and observation symbols do not match.")
        for field_name, value in (("score", self.score), ("relative_rank", self.relative_rank)):
            numeric = float(value)
            if not isfinite(numeric):
                raise ExperimentContractError(f"{field_name} must be finite.")
            object.__setattr__(self, field_name, numeric)

@dataclass(frozen=True, slots=True)
class ForwardOutcomeRecord:
    signal_id: str
    entry_time: str
    entry_price: float
    score: float
    confidence: float
    relative_rank: float
    outcomes: tuple[ForwardOutcome, ...]

    def __post_init__(self) -> None:
        if tuple(outcome.horizon for outcome in self.outcomes) != HORIZONS:
            raise ExperimentContractError("A complete record must contain 1h, 4h, and 24h outcomes in order.")

    def outcome(self, horizon: str) -> ForwardOutcome:
        for outcome in self.outcomes:
            if outcome.horizon == horizon:
                return outcome
        raise ExperimentContractError(f"Missing outcome horizon: {horizon}.")

    def as_row(self) -> dict[str, object]:
        row: dict[str, object] = {
            "signal_id": self.signal_id,
            "entry_time": self.entry_time,
            "entry_price": self.entry_price,
            "score": self.score,
            "confidence": self.confidence,
            "relative_rank": self.relative_rank,
        }
        for horizon in HORIZONS:
            outcome = self.outcome(horizon)
            prefix = horizon.replace("h", "h_")
            row[f"{prefix}return_pct"] = outcome.return_pct
            row[f"{prefix}mfe_pct"] = outcome.mfe_pct
            row[f"{prefix}mae_pct"] = outcome.mae_pct
            row[f"{prefix}outcome_timestamp"] = outcome.as_of.isoformat()
        return row

@dataclass(frozen=True, slots=True)
class RejectedObservation:
    signal_id: str
    reason: str

@dataclass(frozen=True, slots=True)
class LeakageCheck:
    signal_id: str
    passed: bool
    checks: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class HorizonSummary:
    horizon: str
    observations: int
    valid_outcomes: int
    complete_outcomes: int
    mean_return_pct: float | None
    positive_return_rate: float | None
    mean_mfe_pct: float | None
    mean_mae_pct: float | None

@dataclass(frozen=True, slots=True)
class CalibrationBandSummary:
    band: str
    observations: int
    horizon_summaries: tuple[HorizonSummary, ...]

@dataclass(frozen=True, slots=True)
class ForwardOutcomeReport:
    observations_processed: int
    valid_outcomes: int
    rejected_outcomes: int
    outcome_completeness: Mapping[str, float]
    mfe_coverage: Mapping[str, float]
    mae_coverage: Mapping[str, float]
    leakage_checks: tuple[LeakageCheck, ...]
    records: tuple[ForwardOutcomeRecord, ...]
    rejected: tuple[RejectedObservation, ...]
    score_deciles: tuple[CalibrationBandSummary, ...]
    confidence_bands: tuple[CalibrationBandSummary, ...]
    relative_rank_bands: tuple[CalibrationBandSummary, ...]

    def export_rows(self) -> tuple[dict[str, object], ...]:
        return tuple(record.as_row() for record in self.records)

class ForwardOutcomeValidator:
    def __init__(self, harness: ExperimentHarness | None = None) -> None:
        self._harness = harness or ExperimentHarness()

    def process_one(self, item: HistoricalObservation) -> ForwardOutcomeRecord:
        observation = item.observation
        observation.validate_against_fixture(item.fixture)
        outcomes = self._harness.forward_outcomes(item.fixture, observation)
        if tuple(outcome.horizon for outcome in outcomes) != HORIZONS:
            raise ExperimentContractError("Forward outcome set is incomplete.")
        return ForwardOutcomeRecord(
            signal_id=observation.observation_id,
            entry_time=observation.emitted_at.isoformat(),
            entry_price=observation.entry_price,
            score=item.score,
            confidence=observation.confidence,
            relative_rank=item.relative_rank,
            outcomes=outcomes,
        )

    def process_many(self, observations: Sequence[HistoricalObservation]) -> ForwardOutcomeReport:
        records: list[ForwardOutcomeRecord] = []
        rejected: list[RejectedObservation] = []
        leakage: list[LeakageCheck] = []
        for item in observations:
            try:
                record = self.process_one(item)
                records.append(record)
                leakage.append(self._check_leakage(item.fixture, item.observation, record))
            except (ExperimentContractError, IndexError, ValueError) as exc:
                rejected.append(RejectedObservation(item.observation.observation_id, str(exc)))
        summaries = {horizon: self._horizon_summary(horizon, records) for horizon in HORIZONS}
        total = len(observations)
        completeness = {horizon: (summaries[horizon].valid_outcomes / total if total else 0.0) for horizon in HORIZONS}
        mfe_coverage = {horizon: self._coverage(horizon, records, field="mfe_pct", denominator=total) for horizon in HORIZONS}
        mae_coverage = {horizon: self._coverage(horizon, records, field="mae_pct", denominator=total) for horizon in HORIZONS}
        return ForwardOutcomeReport(
            observations_processed=total,
            valid_outcomes=len(records),
            rejected_outcomes=len(rejected),
            outcome_completeness=completeness,
            mfe_coverage=mfe_coverage,
            mae_coverage=mae_coverage,
            leakage_checks=tuple(leakage),
            records=tuple(records),
            rejected=tuple(rejected),
            score_deciles=self._ranked_bands(records, "score", 10, "Decile"),
            confidence_bands=self._ranked_bands(records, "confidence", CONFIDENCE_BAND_COUNT, "Band"),
            relative_rank_bands=self._ranked_bands(records, "relative_rank", RELATIVE_RANK_BAND_COUNT, "Band"),
        )

    @staticmethod
    def _check_leakage(fixture: ExperimentFixture, observation: Observation, record: ForwardOutcomeRecord) -> LeakageCheck:
        checks: list[str] = []
        passed = True
        if any(timestamp > observation.emitted_at for _, timestamp in observation.context_timestamps):
            checks.append("context_timestamp_after_signal")
            passed = False
        else:
            checks.append("context_timestamps_le_signal_time")
        if fixture.candle_at(observation.emitted_at).timestamp != observation.emitted_at:
            checks.append("entry_timestamp_mismatch")
            passed = False
        else:
            checks.append("entry_timestamp_exact")
        for outcome in record.outcomes:
            if outcome.observed_at != observation.emitted_at or outcome.as_of <= observation.emitted_at:
                checks.append(f"{outcome.horizon}_window_boundary_invalid")
                passed = False
            else:
                checks.append(f"{outcome.horizon}_future_only")
        return LeakageCheck(observation.observation_id, passed, tuple(checks))

    @staticmethod
    def _horizon_summary(horizon: str, records: Sequence[ForwardOutcomeRecord]) -> HorizonSummary:
        outcomes = [record.outcome(horizon) for record in records]
        returns = [outcome.return_pct for outcome in outcomes]
        mfes = [outcome.mfe_pct for outcome in outcomes]
        maes = [outcome.mae_pct for outcome in outcomes]
        return HorizonSummary(
            horizon=horizon,
            observations=len(records),
            valid_outcomes=len(outcomes),
            complete_outcomes=len(outcomes),
            mean_return_pct=mean(returns) if returns else None,
            positive_return_rate=(sum(value > 0.0 for value in returns) / len(returns)) if returns else None,
            mean_mfe_pct=mean(mfes) if mfes else None,
            mean_mae_pct=mean(maes) if maes else None,
        )

    @staticmethod
    def _coverage(horizon: str, records: Sequence[ForwardOutcomeRecord], *, field: str, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        covered = sum(isfinite(float(getattr(record.outcome(horizon), field))) for record in records)
        return covered / denominator

    @classmethod
    def _ranked_bands(cls, records: Sequence[ForwardOutcomeRecord], field: str, band_count: int, prefix: str) -> tuple[CalibrationBandSummary, ...]:
        if not records:
            return ()
        ranked = sorted(records, key=lambda record: (float(getattr(record, field)), record.signal_id))
        buckets: list[list[ForwardOutcomeRecord]] = [[] for _ in range(band_count)]
        for position, record in enumerate(ranked):
            band_index = min(band_count - 1, position * band_count // len(ranked))
            buckets[band_index].append(record)
        summaries: list[CalibrationBandSummary] = []
        for index, bucket in enumerate(buckets, start=1):
            if bucket:
                summaries.append(CalibrationBandSummary(
                    band=f"{prefix}_{index}",
                    observations=len(bucket),
                    horizon_summaries=tuple(cls._horizon_summary(horizon, bucket) for horizon in HORIZONS),
                ))
        return tuple(summaries)

__all__ = [
    "CalibrationBandSummary", "ForwardOutcomeRecord", "ForwardOutcomeReport",
    "ForwardOutcomeValidator", "HistoricalObservation", "HorizonSummary",
    "LeakageCheck", "RejectedObservation",
]
