"""Repeatable, observation-only experiment harness for ORION Phase A.

This module is deliberately isolated from Production Intelligence, Execution,
and Reporting. It owns experiment fixtures, immutable signal observations,
forward-outcome measurement, MFE/MAE calculation, and deterministic replay.

Safety contract:
    * no network or exchange access;
    * no ExecutionEngine / PaperExecutionAdapter imports;
    * no mutation of ORION Production contracts;
    * observations may reference only information available at emitted_at;
    * forward outcomes are calculated only from candles strictly after emitted_at.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import math
from types import MappingProxyType
from typing import Mapping, Sequence


UTC = timezone.utc


class ExperimentContractError(ValueError):
    """Raised when an experiment artifact violates the Phase A contract."""


class ExecutionDisabledError(RuntimeError):
    """Raised whenever a caller attempts execution from the experiment harness."""


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    FLAT = "FLAT"


HORIZONS_HOURS: tuple[int, ...] = (1, 4, 24)
HORIZON_NAMES: Mapping[int, str] = MappingProxyType(
    {1: "1h", 4: "4h", 24: "24h"}
)
Scalar = str | int | float | bool | None


def _utc(value: datetime, *, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise ExperimentContractError(f"{field} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ExperimentContractError(f"{field} must be timezone-aware UTC.")
    normalized = value.astimezone(UTC)
    if normalized.utcoffset() != timedelta(0):
        raise ExperimentContractError(f"{field} must be UTC.")
    return normalized


def _finite(value: float, *, field: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ExperimentContractError(f"{field} must be numeric.") from exc
    if not math.isfinite(numeric):
        raise ExperimentContractError(f"{field} must be finite.")
    return numeric


@dataclass(frozen=True, slots=True)
class Candle:
    """Immutable OHLC candle used exclusively by the experiment fixture."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        timestamp = _utc(self.timestamp, field="Candle.timestamp")
        open_price = _finite(self.open, field="Candle.open")
        high = _finite(self.high, field="Candle.high")
        low = _finite(self.low, field="Candle.low")
        close = _finite(self.close, field="Candle.close")
        volume = _finite(self.volume, field="Candle.volume")
        if low > min(open_price, close) or high < max(open_price, close):
            raise ExperimentContractError("Candle high/low must contain open and close.")
        if low < 0.0 or high < 0.0 or open_price < 0.0 or close < 0.0:
            raise ExperimentContractError("Candle prices cannot be negative.")
        if volume < 0.0:
            raise ExperimentContractError("Candle volume cannot be negative.")
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "open", open_price)
        object.__setattr__(self, "high", high)
        object.__setattr__(self, "low", low)
        object.__setattr__(self, "close", close)
        object.__setattr__(self, "volume", volume)


@dataclass(frozen=True, slots=True)
class ExperimentFixture:
    """Deterministic hourly market tape for repeatable historical experiments."""

    fixture_id: str
    symbol: str
    start_at: datetime
    candles: tuple[Candle, ...]
    seed: int

    def __post_init__(self) -> None:
        if not self.fixture_id.strip():
            raise ExperimentContractError("fixture_id cannot be empty.")
        if not self.symbol.strip():
            raise ExperimentContractError("symbol cannot be empty.")
        start = _utc(self.start_at, field="ExperimentFixture.start_at")
        if len(self.candles) < 25:
            raise ExperimentContractError("Fixture requires at least 25 hourly candles.")
        timestamps = tuple(candle.timestamp for candle in self.candles)
        if timestamps[0] != start:
            raise ExperimentContractError("First candle must equal start_at.")
        for previous, current in zip(timestamps, timestamps[1:]):
            if current - previous != timedelta(hours=1):
                raise ExperimentContractError("Fixture candles must be consecutive hourly UTC data.")
        object.__setattr__(self, "start_at", start)
        object.__setattr__(self, "candles", tuple(self.candles))

    @classmethod
    def generate(
        cls,
        *,
        fixture_id: str,
        symbol: str = "BTCUSDT",
        start_at: datetime | None = None,
        seed: int = 1,
        periods: int = 97,
    ) -> "ExperimentFixture":
        """Generate a deterministic fixture without any external data source."""
        start = _utc(
            start_at or datetime(2025, 1, 1, tzinfo=UTC),
            field="start_at",
        )
        if periods < 25:
            raise ExperimentContractError("periods must be >= 25.")
        base = 100_000.0 + float(abs(int(seed)) % 10_000)
        candles: list[Candle] = []
        previous_close = base
        for index in range(periods):
            timestamp = start + timedelta(hours=index)
            drift = 12.5 * index
            cycle = (((seed * 31 + index * 17) % 19) - 9) * 3.0
            close = base + drift + cycle
            open_price = previous_close
            high = max(open_price, close) + 20.0 + ((seed + index) % 5)
            low = min(open_price, close) - 20.0 - ((seed + index) % 7)
            volume = 1_000.0 + float((seed * 7 + index * 11) % 300)
            candles.append(
                Candle(
                    timestamp=timestamp,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
            previous_close = close
        return cls(
            fixture_id=fixture_id,
            symbol=symbol,
            start_at=start,
            candles=tuple(candles),
            seed=int(seed),
        )

    def index_at(self, timestamp: datetime) -> int:
        target = _utc(timestamp, field="timestamp")
        for index, candle in enumerate(self.candles):
            if candle.timestamp == target:
                return index
        raise ExperimentContractError(
            f"Timestamp {target.isoformat()} is not present in fixture {self.fixture_id}."
        )

    def candle_at(self, timestamp: datetime) -> Candle:
        return self.candles[self.index_at(timestamp)]

    def fingerprint(self) -> str:
        payload = "|".join(
            [
                self.fixture_id,
                self.symbol,
                self.start_at.isoformat(),
                str(self.seed),
                *(
                    f"{c.timestamp.isoformat()}:{c.open:.8f}:{c.high:.8f}:{c.low:.8f}:{c.close:.8f}:{c.volume:.8f}"
                    for c in self.candles
                ),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ObservationSpec:
    """Replay recipe; it contains no future market outcome fields."""

    emitted_at: datetime
    direction: SignalDirection
    confidence: float
    signal: str
    context: tuple[tuple[str, Scalar], ...] = ()
    context_timestamps: tuple[tuple[str, datetime], ...] = ()


@dataclass(frozen=True, slots=True)
class Observation:
    """Immutable point-in-time signal record with an explicit information boundary."""

    observation_id: str
    fixture_id: str
    symbol: str
    emitted_at: datetime
    direction: SignalDirection
    signal: str
    confidence: float
    entry_price: float
    context: tuple[tuple[str, Scalar], ...]
    context_timestamps: tuple[tuple[str, datetime], ...]

    def __post_init__(self) -> None:
        if not self.observation_id.strip():
            raise ExperimentContractError("observation_id cannot be empty.")
        if not self.fixture_id.strip() or not self.symbol.strip():
            raise ExperimentContractError("Observation fixture_id/symbol cannot be empty.")
        emitted_at = _utc(self.emitted_at, field="Observation.emitted_at")
        confidence = _finite(self.confidence, field="Observation.confidence")
        entry_price = _finite(self.entry_price, field="Observation.entry_price")
        if not 0.0 <= confidence <= 100.0:
            raise ExperimentContractError("Observation.confidence must be within [0, 100].")
        if entry_price <= 0.0:
            raise ExperimentContractError("Observation.entry_price must be > 0.")
        if not self.signal.strip():
            raise ExperimentContractError("Observation.signal cannot be empty.")

        normalized_context = tuple(self.context)
        normalized_times = tuple(
            (key, _utc(timestamp, field=f"Observation.context_timestamps[{key}]"))
            for key, timestamp in self.context_timestamps
        )
        for key, timestamp in normalized_times:
            if timestamp > emitted_at:
                raise ExperimentContractError(
                    f"Future leakage detected: context timestamp {key} exceeds emitted_at."
                )
        object.__setattr__(self, "emitted_at", emitted_at)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "entry_price", entry_price)
        object.__setattr__(self, "context", normalized_context)
        object.__setattr__(self, "context_timestamps", normalized_times)

    def validate_against_fixture(self, fixture: ExperimentFixture) -> None:
        if self.fixture_id != fixture.fixture_id or self.symbol != fixture.symbol:
            raise ExperimentContractError("Observation does not belong to the supplied fixture.")
        candle = fixture.candle_at(self.emitted_at)
        if not math.isclose(self.entry_price, candle.close, rel_tol=0.0, abs_tol=1e-9):
            raise ExperimentContractError("Observation entry_price must equal the point-in-time close.")
        for key, timestamp in self.context_timestamps:
            if timestamp > self.emitted_at:
                raise ExperimentContractError(
                    f"Future leakage detected in context field {key}."
                )

    def replay_key(self) -> tuple[object, ...]:
        return (
            self.fixture_id,
            self.symbol,
            self.emitted_at,
            self.direction.value,
            self.signal,
            round(self.confidence, 12),
            round(self.entry_price, 12),
            self.context,
            self.context_timestamps,
        )


@dataclass(frozen=True, slots=True)
class ForwardOutcome:
    """Directional forward result for a single horizon."""

    horizon: str
    observed_at: datetime
    as_of: datetime
    close_price: float
    return_pct: float
    mfe_pct: float
    mae_pct: float

    def __post_init__(self) -> None:
        observed_at = _utc(self.observed_at, field="ForwardOutcome.observed_at")
        as_of = _utc(self.as_of, field="ForwardOutcome.as_of")
        if as_of <= observed_at:
            raise ExperimentContractError("Forward outcome must be strictly after observation time.")
        for field_name in ("close_price", "return_pct", "mfe_pct", "mae_pct"):
            _finite(getattr(self, field_name), field=f"ForwardOutcome.{field_name}")
        if self.mfe_pct < 0.0 or self.mae_pct < 0.0:
            raise ExperimentContractError("MFE and MAE must be non-negative magnitudes.")
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "as_of", as_of)


@dataclass(frozen=True, slots=True)
class ObservationSet:
    """Observation plus its measured future outcomes."""

    observation: Observation
    outcomes: tuple[ForwardOutcome, ...]

    def __post_init__(self) -> None:
        self.observation.validate_against_fixture(
            ExperimentFixture.generate(
                fixture_id=self.observation.fixture_id,
                symbol=self.observation.symbol,
                start_at=self.observation.emitted_at,
                seed=0,
                periods=25,
            )
        ) if False else None
        horizons = tuple(outcome.horizon for outcome in self.outcomes)
        if horizons != tuple(HORIZON_NAMES[h] for h in HORIZONS_HOURS):
            raise ExperimentContractError("ObservationSet must contain 1h, 4h, and 24h outcomes in order.")


@dataclass(frozen=True, slots=True)
class ReplayMismatch:
    field: str
    expected: object
    actual: object


@dataclass(frozen=True, slots=True)
class ReplayComparison:
    matched: bool
    mismatches: tuple[ReplayMismatch, ...] = ()


class ExperimentHarness:
    """Observation-only harness; execution is structurally disabled."""

    EXECUTION_ENABLED = False

    def create_observation(
        self,
        fixture: ExperimentFixture,
        spec: ObservationSpec,
    ) -> Observation:
        emitted_at = _utc(spec.emitted_at, field="ObservationSpec.emitted_at")
        candle = fixture.candle_at(emitted_at)
        context_timestamps = tuple(
            (key, _utc(timestamp, field=f"context_timestamps[{key}]"))
            for key, timestamp in spec.context_timestamps
        )
        observation_payload = (
            fixture.fixture_id,
            fixture.symbol,
            emitted_at.isoformat(),
            spec.direction.value,
            spec.signal,
            f"{float(spec.confidence):.12f}",
            f"{candle.close:.12f}",
            repr(tuple(spec.context)),
            repr(context_timestamps),
        )
        observation_id = hashlib.sha256("|".join(observation_payload).encode("utf-8")).hexdigest()
        observation = Observation(
            observation_id=observation_id,
            fixture_id=fixture.fixture_id,
            symbol=fixture.symbol,
            emitted_at=emitted_at,
            direction=spec.direction,
            signal=spec.signal,
            confidence=spec.confidence,
            entry_price=candle.close,
            context=tuple(spec.context),
            context_timestamps=context_timestamps,
        )
        observation.validate_against_fixture(fixture)
        return observation

    def forward_outcomes(
        self,
        fixture: ExperimentFixture,
        observation: Observation,
        *,
        horizons_hours: Sequence[int] = HORIZONS_HOURS,
    ) -> tuple[ForwardOutcome, ...]:
        """Measure only future candles strictly after the signal timestamp."""
        observation.validate_against_fixture(fixture)
        origin = fixture.index_at(observation.emitted_at)
        results: list[ForwardOutcome] = []
        for horizon in horizons_hours:
            if horizon not in HORIZON_NAMES:
                raise ExperimentContractError(f"Unsupported horizon: {horizon}h")
            target_index = origin + int(horizon)
            if target_index >= len(fixture.candles):
                raise ExperimentContractError(
                    f"Fixture does not contain {horizon}h of future data for {observation.observation_id}."
                )
            future = fixture.candles[origin + 1 : target_index + 1]
            if len(future) != horizon:
                raise ExperimentContractError("Forward window length does not match horizon.")
            entry = observation.entry_price
            close_price = future[-1].close
            if observation.direction is SignalDirection.SELL:
                signed_return = (entry - close_price) / entry
                favorable_prices = [c.low for c in future]
                adverse_prices = [c.high for c in future]
                mfe_pct = max((entry - price) / entry for price in favorable_prices)
                mae_pct = max((price - entry) / entry for price in adverse_prices)
            elif observation.direction is SignalDirection.BUY:
                signed_return = (close_price - entry) / entry
                favorable_prices = [c.high for c in future]
                adverse_prices = [c.low for c in future]
                mfe_pct = max((price - entry) / entry for price in favorable_prices)
                mae_pct = max((entry - price) / entry for price in adverse_prices)
            else:
                signed_return = (close_price - entry) / entry
                mfe_pct = max(abs((c.high - entry) / entry) for c in future)
                mae_pct = max(abs((c.low - entry) / entry) for c in future)

            results.append(
                ForwardOutcome(
                    horizon=HORIZON_NAMES[horizon],
                    observed_at=observation.emitted_at,
                    as_of=future[-1].timestamp,
                    close_price=close_price,
                    return_pct=signed_return * 100.0,
                    mfe_pct=max(0.0, mfe_pct * 100.0),
                    mae_pct=max(0.0, mae_pct * 100.0),
                )
            )
        return tuple(results)

    def replay(self, fixture: ExperimentFixture, specs: Sequence[ObservationSpec]) -> tuple[Observation, ...]:
        """Rebuild observations deterministically from the same fixture/specs."""
        return tuple(self.create_observation(fixture, spec) for spec in specs)

    @staticmethod
    def compare(
        expected: Sequence[Observation],
        actual: Sequence[Observation],
    ) -> ReplayComparison:
        mismatches: list[ReplayMismatch] = []
        if len(expected) != len(actual):
            mismatches.append(ReplayMismatch("length", len(expected), len(actual)))
        for index, (left, right) in enumerate(zip(expected, actual)):
            if left.replay_key() != right.replay_key():
                mismatches.append(
                    ReplayMismatch(
                        field=f"observation[{index}]",
                        expected=left.replay_key(),
                        actual=right.replay_key(),
                    )
                )
        return ReplayComparison(matched=not mismatches, mismatches=tuple(mismatches))

    def execute(self, *_args: object, **_kwargs: object) -> None:
        """Explicitly refuse all execution from the experiment harness."""
        raise ExecutionDisabledError(
            "Experiment harness is observation-only; live and paper execution are disabled."
        )


__all__ = [
    "Candle",
    "ExperimentContractError",
    "ExperimentFixture",
    "ExperimentHarness",
    "ExecutionDisabledError",
    "ForwardOutcome",
    "HORIZONS_HOURS",
    "Observation",
    "ObservationSet",
    "ObservationSpec",
    "ReplayComparison",
    "ReplayMismatch",
    "SignalDirection",
]
