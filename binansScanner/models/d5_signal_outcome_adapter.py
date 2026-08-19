"""Narrow D5-to-D6 signal journal adapter.

The adapter performs mapping only. It does not recompute outcomes or create
missing signal-time intelligence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from models.signal_journal import SignalObservation, SignalOutcome


@dataclass(frozen=True, slots=True)
class D5D6SignalOutcomeAdapter:
    """Map D5 observation/outcomes into the canonical D6 contracts."""

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    def observation(
        self,
        d5_observation: Any,
        *,
        timeframe: str,
        raw_score: float | None = None,
        market_regime: str | None = None,
        context_score: float | None = None,
        directional_raw_strength: float | None = None,
        composite: float | None = None,
        relative_rank: float | None = None,
        relative_percentile: float | None = None,
        volume: float | None = None,
        relative_volume: float | None = None,
        volatility: float | None = None,
        relative_volatility: float | None = None,
        liquidity: float | None = None,
        momentum: float | None = None,
        multi_timeframe_alignment: str | None = None,
        reasons: Sequence[str] = (),
    ) -> SignalObservation:
        context = dict(getattr(d5_observation, "context", ()))
        resolved_raw_score = raw_score if raw_score is not None else context.get("score")
        if resolved_raw_score is None:
            raise ValueError("D5 observation does not provide canonical raw_score")
        resolved_regime = market_regime if market_regime is not None else context.get("market_state")
        if resolved_regime is None:
            raise ValueError("D5 observation does not provide canonical market_regime")
        direction = getattr(d5_observation, "direction", None)
        decision = getattr(direction, "value", direction)
        if decision == "FLAT":
            decision = "WAIT"
        confidence = getattr(d5_observation, "confidence")
        # D5 stores confidence on its own scale; preserve the value exactly.
        return SignalObservation(
            observation_id=str(getattr(d5_observation, "observation_id")),
            timestamp=self._utc(getattr(d5_observation, "emitted_at")),
            symbol=str(getattr(d5_observation, "symbol")),
            timeframe=timeframe,
            raw_score=resolved_raw_score,
            directional_raw_strength=directional_raw_strength,
            context_score=context_score,
            composite=composite,
            relative_rank=relative_rank,
            relative_percentile=relative_percentile,
            confidence=confidence,
            decision=str(decision),
            market_regime=str(resolved_regime),
            volume=volume,
            relative_volume=relative_volume,
            volatility=volatility,
            relative_volatility=relative_volatility,
            liquidity=liquidity,
            momentum=momentum,
            multi_timeframe_alignment=multi_timeframe_alignment,
            reasons=tuple(reasons),
        )

    def outcome(
        self,
        d5_observation: Any,
        forward_outcomes: Sequence[Any],
    ) -> SignalOutcome:
        """Map D5 ForwardOutcome records without recalculating their metrics."""
        by_horizon = {str(item.horizon): item for item in forward_outcomes}
        outcome_values = {
            "1h": by_horizon.get("1h"),
            "4h": by_horizon.get("4h"),
            "24h": by_horizon.get("24h"),
        }
        if any(value is None for value in outcome_values.values()):
            raise ValueError("D5 forward_outcomes must contain 1h, 4h, and 24h records")
        latest = max(self._utc(item.as_of) for item in outcome_values.values() if item is not None)
        observation_time = self._utc(getattr(d5_observation, "emitted_at"))
        if latest <= observation_time:
            raise ValueError("latest as_of must be strictly after observation timestamp")
        mfe = max(float(item.mfe_pct) for item in outcome_values.values() if item is not None)
        mae = max(float(item.mae_pct) for item in outcome_values.values() if item is not None)
        return SignalOutcome(
            outcome_1h=float(outcome_values["1h"].return_pct),
            outcome_4h=float(outcome_values["4h"].return_pct),
            outcome_24h=float(outcome_values["24h"].return_pct),
            mfe=mfe,
            mae=mae,
            outcome_timestamp=latest,
            metric_unit="percent",
        )
