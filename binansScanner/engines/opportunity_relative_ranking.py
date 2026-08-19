"""Standalone contextual relative ranking for Opportunity candidates.

This module is intentionally isolated from Opportunity eligibility, selection,
TradingReadiness, Core, Execution, and pipeline wiring. It consumes existing
canonical market/Profile/Score evidence and returns ranking metadata only.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import median
from typing import Sequence

import pandas as pd

from enums import Timeframe
from models.market import MarketDataset
from models.opportunity import Opportunity, OpportunityDirection
from models.profile import ProfileResult
from models.score import ScoreResult


@dataclass(frozen=True, slots=True)
class OpportunityRankingInput:
    opportunity: Opportunity
    score: ScoreResult
    profile: ProfileResult
    dataset: MarketDataset


@dataclass(frozen=True, slots=True)
class OpportunityContext:
    volume_expansion: float
    relative_volume: float
    volatility: float
    relative_volatility: float
    volatility_fit: float
    momentum: float
    liquidity: float
    mtf_alignment: float
    market_regime: float

    @property
    def score(self) -> float:
        weights = (
            (self.volume_expansion, 0.10),
            (self.relative_volume, 0.15),
            (self.volatility_fit, 0.10),
            (self.relative_volatility, 0.10),
            (self.momentum, 0.15),
            (self.liquidity, 0.15),
            (self.mtf_alignment, 0.15),
            (self.market_regime, 0.10),
        )
        return _clamp(sum(value * weight for value, weight in weights))


@dataclass(frozen=True, slots=True)
class RankedOpportunity:
    opportunity: Opportunity
    raw_score: float
    context_score: float
    composite_score: float
    relative_rank: int | None
    percentile: float | None
    peer_count: int
    context: OpportunityContext


class OpportunityRelativeRanker:
    """Contextual ranking inside same-timeframe, same-direction cohorts."""

    RAW_WEIGHT = 0.70
    CONTEXT_WEIGHT = 0.30

    def rank(self, inputs: Sequence[OpportunityRankingInput]) -> tuple[RankedOpportunity, ...]:
        prepared = [self._prepare(item) for item in inputs]
        cohorts: dict[tuple[str, OpportunityDirection], list[dict]] = {}
        for item in prepared:
            key = (item["opportunity"].timeframe, item["opportunity"].direction)
            cohorts.setdefault(key, []).append(item)

        ranked: list[RankedOpportunity] = []
        for cohort in cohorts.values():
            raw_values = [item["raw_score"] for item in cohort]
            volume_values = [item["volume_expansion"] for item in cohort]
            volatility_values = [item["volatility"] for item in cohort]
            liquidity_values = [item["liquidity"] for item in cohort]

            scored: list[dict] = []
            for item in cohort:
                context = OpportunityContext(
                    volume_expansion=_saturating_volume(item["volume_expansion"]),
                    relative_volume=_percentile(item["volume_expansion"], volume_values),
                    volatility=item["volatility"],
                    relative_volatility=_percentile(item["volatility"], volatility_values),
                    volatility_fit=_volatility_fit(item["volatility"], volatility_values),
                    momentum=item["momentum"],
                    liquidity=_percentile(item["liquidity"], liquidity_values),
                    mtf_alignment=item["mtf_alignment"],
                    market_regime=item["market_regime"],
                )
                raw = item["raw_score"]
                composite = self.RAW_WEIGHT * raw + self.CONTEXT_WEIGHT * context.score
                scored.append({**item, "context": context, "context_score": context.score, "composite": _clamp(composite)})

            composites = [item["composite"] for item in scored]
            for item in scored:
                if len(scored) < 2:
                    rank = None
                    percentile = None
                else:
                    rank = 1 + sum(value > item["composite"] for value in composites)
                    percentile = _percentile(item["composite"], composites)
                ranked.append(
                    RankedOpportunity(
                        opportunity=item["opportunity"],
                        raw_score=item["raw_score"],
                        context_score=item["context_score"],
                        composite_score=item["composite"],
                        relative_rank=rank,
                        percentile=percentile,
                        peer_count=len(scored),
                        context=item["context"],
                    )
                )

        return tuple(
            sorted(
                ranked,
                key=lambda item: (
                    item.percentile is not None,
                    item.percentile if item.percentile is not None else -1.0,
                    item.composite_score,
                    item.opportunity.symbol,
                ),
                reverse=True,
            )
        )

    def _prepare(self, item: OpportunityRankingInput) -> dict:
        timeframe = _normalize_timeframe(item.opportunity.timeframe)
        timeframe_profile = _matching_timeframe_profile(item.profile, timeframe)
        if timeframe_profile is None:
            raise ValueError("ranking requires exactly one matching Profile timeframe")

        timeframe_data = item.dataset.get_timeframe(timeframe)
        if timeframe_data is None or timeframe_data.dataframe.empty:
            raise ValueError("ranking requires market data for the requested timeframe")

        volume_expansion = _volume_expansion(timeframe_data.dataframe)
        volatility = _finite_float(timeframe_profile.characteristics.volatility, "volatility")
        liquidity = _finite_float(item.profile.market.liquidity, "liquidity")
        momentum = _directional_momentum(timeframe_profile.characteristics.momentum, item.opportunity.direction)
        mtf_alignment = _mtf_alignment(item.profile, item.opportunity.direction)
        market_regime = _market_regime(item.profile, item.opportunity.direction)

        return {
            "opportunity": item.opportunity,
            "raw_score": _clamp(_finite_float(item.score.score, "raw score")),
            "volume_expansion": volume_expansion,
            "volatility": volatility,
            "liquidity": liquidity,
            "momentum": momentum,
            "mtf_alignment": mtf_alignment,
            "market_regime": market_regime,
        }


def _normalize_timeframe(value: str) -> Timeframe:
    try:
        return Timeframe(value)
    except ValueError as exc:
        raise ValueError(f"unsupported canonical timeframe: {value!r}") from exc


def _matching_timeframe_profile(profile: ProfileResult, timeframe: Timeframe):
    matches = tuple(item for item in profile.timeframes if item.timeframe == timeframe.value)
    return matches[0] if len(matches) == 1 else None


def _volume_expansion(frame: pd.DataFrame) -> float:
    if "volume" not in frame.columns or len(frame) < 2:
        raise ValueError("ranking requires volume history")
    current = _finite_float(frame["volume"].iloc[-1], "latest volume")
    history = frame["volume"].iloc[:-1].tail(20).astype(float)
    if history.empty or not history.map(isfinite).all():
        raise ValueError("ranking requires finite historical volume")
    baseline = float(median(history.tolist()))
    if baseline <= 0:
        raise ValueError("ranking requires a positive historical volume baseline")
    return current / baseline


def _directional_momentum(momentum: str, direction: OpportunityDirection) -> float:
    mapping = {"Strong Buy": 100.0, "Buy": 75.0, "Neutral": 50.0, "Sell": 25.0, "Strong Sell": 0.0}
    if momentum not in mapping:
        raise ValueError(f"unsupported canonical momentum: {momentum!r}")
    value = mapping[momentum]
    return value if direction is OpportunityDirection.LONG else 100.0 - value


def _mtf_alignment(profile: ProfileResult, direction: OpportunityDirection) -> float:
    expected = "Bullish" if direction is OpportunityDirection.LONG else "Bearish"
    if not profile.timeframes:
        return 0.0
    checks = 2 * len(profile.timeframes)
    matches = sum(
        int(timeframe.trend == expected) + int(timeframe.characteristics.ema_alignment == expected)
        for timeframe in profile.timeframes
    )
    return 100.0 * matches / checks


def _market_regime(profile: ProfileResult, direction: OpportunityDirection) -> float:
    expected = "Bullish" if direction is OpportunityDirection.LONG else "Bearish"
    trend = profile.market.trend
    phase = profile.market.market_phase
    if trend == expected:
        return 100.0
    if trend == "Sideways":
        return 50.0
    if (direction is OpportunityDirection.LONG and phase == "Markup") or (
        direction is OpportunityDirection.SHORT and phase == "Markdown"
    ):
        return 100.0
    if phase == "Range":
        return 50.0
    return 0.0


def _saturating_volume(value: float) -> float:
    return _clamp((min(max(value, 0.0), 2.0) / 2.0) * 100.0)


def _volatility_fit(value: float, peers: Sequence[float]) -> float:
    if not peers:
        return 0.0
    midpoint = median(peers)
    spread = max(max(peers) - min(peers), 1e-12)
    return _clamp(100.0 - 100.0 * abs(value - midpoint) / spread)


def _percentile(value: float, peers: Sequence[float]) -> float:
    if len(peers) <= 1:
        return 50.0
    less = sum(peer < value for peer in peers)
    equal = sum(peer == value for peer in peers)
    return 100.0 * (less + 0.5 * equal) / len(peers)


def _finite_float(value: float, label: str) -> float:
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return min(max(float(value), low), high)


__all__ = [
    "OpportunityContext",
    "OpportunityRankingInput",
    "OpportunityRelativeRanker",
    "RankedOpportunity",
]
