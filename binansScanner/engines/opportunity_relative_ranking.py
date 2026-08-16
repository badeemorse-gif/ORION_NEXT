"""Contextual relative ranking for future Opportunity Intelligence.

Phase A design only: this layer orders already-generated Opportunity candidates.
It does not change Opportunity eligibility, SelectionPolicy, TradingReadiness,
or any accepted integration boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

import pandas as pd

from enums import Timeframe
from models.market import MarketDataset
from models.opportunity import Opportunity, OpportunityDirection
from models.profile import ProfileResult
from models.score import ScoreResult


@dataclass(frozen=True, slots=True)
class OpportunityRankingInput:
    """Read-only inputs for one candidate's ranking context."""

    opportunity: Opportunity
    score: ScoreResult
    profile: ProfileResult
    dataset: MarketDataset


@dataclass(frozen=True, slots=True)
class OpportunityContext:
    """Normalized contextual signals used only for relative ordering."""

    volume_expansion: float
    relative_volume_percentile: float
    volatility: float
    relative_volatility_percentile: float
    volatility_fit: float
    momentum_score: float
    liquidity: float
    liquidity_percentile: float
    liquidity_class: str
    mtf_alignment: float
    market_regime_score: float

    @property
    def context_score(self) -> float:
        weighted = (
            0.10 * _expansion_score(self.volume_expansion)
            + 0.15 * self.relative_volume_percentile
            + 0.10 * self.volatility_fit
            + 0.10 * self.relative_volatility_percentile
            + 0.15 * self.momentum_score
            + 0.15 * self.liquidity_percentile
            + 0.15 * self.mtf_alignment
            + 0.10 * self.market_regime_score
        )
        return _clamp(weighted, 0.0, 100.0)


@dataclass(frozen=True, slots=True)
class RankedOpportunity:
    """Ranking result; no eligibility or execution semantics are changed."""

    opportunity: Opportunity
    raw_score: float
    context_score: float
    composite_score: float
    relative_rank: int | None
    relative_percentile: float | None
    peer_count: int
    context: OpportunityContext


class OpportunityRelativeRanker:
    """Rank candidates within same-timeframe, same-direction peer cohorts."""

    RAW_WEIGHT = 0.70
    CONTEXT_WEIGHT = 0.30

    def rank(self, inputs: Sequence[OpportunityRankingInput]) -> tuple[RankedOpportunity, ...]:
        if not inputs:
            return ()

        prepared = [self._prepare(item) for item in inputs]
        cohorts: dict[tuple[str, OpportunityDirection], list[dict]] = {}
        for item in prepared:
            key = (item["opportunity"].timeframe, item["opportunity"].direction)
            cohorts.setdefault(key, []).append(item)

        output: list[RankedOpportunity] = []
        for cohort in cohorts.values():
            volume_values = [item["volume_expansion"] for item in cohort]
            volatility_values = [item["volatility"] for item in cohort]
            liquidity_values = [item["liquidity"] for item in cohort]

            scored: list[dict] = []
            for item in cohort:
                context = OpportunityContext(
                    volume_expansion=item["volume_expansion"],
                    relative_volume_percentile=_midrank_percentile(item["volume_expansion"], volume_values),
                    volatility=item["volatility"],
                    relative_volatility_percentile=_midrank_percentile(item["volatility"], volatility_values),
                    volatility_fit=_median_fit(item["volatility"], volatility_values),
                    momentum_score=item["momentum_score"],
                    liquidity=item["liquidity"],
                    liquidity_percentile=_midrank_percentile(item["liquidity"], liquidity_values),
                    liquidity_class=_liquidity_class(
                        _midrank_percentile(item["liquidity"], liquidity_values)
                    ),
                    mtf_alignment=item["mtf_alignment"],
                    market_regime_score=item["market_regime_score"],
                )
                raw_score = item["raw_score"]
                context_score = context.context_score
                composite = _clamp(
                    self.RAW_WEIGHT * raw_score + self.CONTEXT_WEIGHT * context_score,
                    0.0,
                    100.0,
                )
                scored.append(
                    {
                        "opportunity": item["opportunity"],
                        "raw_score": raw_score,
                        "context_score": context_score,
                        "composite_score": composite,
                        "context": context,
                    }
                )

            composite_scores = [item["composite_score"] for item in scored]
            peer_count = len(scored)
            for item in scored:
                if peer_count >= 2:
                    rank = 1 + sum(other > item["composite_score"] for other in composite_scores)
                    percentile = _midrank_percentile(item["composite_score"], composite_scores)
                else:
                    rank = None
                    percentile = None
                output.append(
                    RankedOpportunity(
                        opportunity=item["opportunity"],
                        raw_score=item["raw_score"],
                        context_score=item["context_score"],
                        composite_score=item["composite_score"],
                        relative_rank=rank,
                        relative_percentile=percentile,
                        peer_count=peer_count,
                        context=item["context"],
                    )
                )

        return tuple(
            sorted(
                output,
                key=lambda item: (
                    item.relative_percentile is not None,
                    item.relative_percentile if item.relative_percentile is not None else -1.0,
                    item.composite_score,
                    item.opportunity.symbol,
                ),
                reverse=True,
            )
        )

    def _prepare(self, item: OpportunityRankingInput) -> dict:
        opportunity = item.opportunity
        timeframe = _normalize_timeframe(opportunity.timeframe)
        timeframe_profile = _matching_timeframe_profile(item.profile, timeframe)
        if timeframe_profile is None:
            raise ValueError("ranking requires exactly one matching timeframe profile")

        dataframe = _frame_for_timeframe(item.dataset, timeframe)
        volume_expansion = _volume_expansion(dataframe)
        volatility = float(timeframe_profile.characteristics.volatility)
        liquidity = float(item.profile.market.liquidity)
        if not isfinite(volatility):
            raise ValueError("volatility must be finite")
        if not isfinite(liquidity):
            raise ValueError("liquidity must be finite")

        return {
            "opportunity": opportunity,
            "raw_score": _clamp(float(item.score.score), 0.0, 100.0),
            "volume_expansion": volume_expansion,
            "volatility": volatility,
            "liquidity": liquidity,
            "momentum_score": _directional_momentum_score(
                timeframe_profile.characteristics.momentum,
                opportunity.direction,
            ),
            "mtf_alignment": _mtf_alignment(item.profile, opportunity.direction),
            "market_regime_score": _market_regime_score(item.profile, opportunity.direction),
        }


def _volume_expansion(dataframe: pd.DataFrame) -> float:
    if "volume" not in dataframe.columns or len(dataframe) < 2:
        raise ValueError("ranking requires OHLCV volume history")
    current = float(dataframe["volume"].iloc[-1])
    baseline_series = dataframe["volume"].iloc[:-1].tail(min(20, len(dataframe) - 1))
    baseline = float(baseline_series.median())
    if not isfinite(current) or not isfinite(baseline) or baseline <= 0:
        raise ValueError("volume history must be finite with positive baseline")
    return current / baseline


def _expansion_score(ratio: float) -> float:
    # 1.0x is neutral; values above 2.0x are saturated so one extraordinary
    # candle cannot dominate the context layer.
    return _clamp(50.0 + 50.0 * (ratio - 1.0), 0.0, 100.0)


def _matching_timeframe_profile(profile: ProfileResult, timeframe: Timeframe):
    matches = tuple(item for item in profile.timeframes if item.timeframe == timeframe.value)
    return matches[0] if len(matches) == 1 else None


def _frame_for_timeframe(dataset: MarketDataset, timeframe: Timeframe) -> pd.DataFrame:
    timeframe_data = dataset.get_timeframe(timeframe)
    if timeframe_data is None or timeframe_data.dataframe.empty:
        raise ValueError("ranking requires market data for the requested timeframe")
    return timeframe_data.dataframe


def _directional_momentum_score(momentum: str, direction: OpportunityDirection) -> float:
    mapping = {"Strong Buy": 100.0, "Buy": 75.0, "Neutral": 50.0, "Sell": 25.0, "Strong Sell": 0.0}
    value = mapping.get(momentum, 50.0)
    return value if direction is OpportunityDirection.LONG else 100.0 - value


def _mtf_alignment(profile: ProfileResult, direction: OpportunityDirection) -> float:
    expected = "Bullish" if direction is OpportunityDirection.LONG else "Bearish"
    if not profile.timeframes:
        return 50.0
    aligned = 0
    total = 0
    for timeframe in profile.timeframes:
        total += 1
        aligned += int(timeframe.characteristics.trend == expected)
        aligned += int(timeframe.characteristics.ema_alignment == expected)
    return 100.0 * aligned / (2.0 * total)


def _market_regime_score(profile: ProfileResult, direction: OpportunityDirection) -> float:
    expected = "Bullish" if direction is OpportunityDirection.LONG else "Bearish"
    trend = profile.market.trend
    phase = profile.market.market_phase
    if trend == expected:
        base = 100.0
    elif trend == "Sideways":
        base = 50.0
    else:
        base = 0.0
    if direction is OpportunityDirection.LONG and phase == "Markup":
        base = 100.0
    elif direction is OpportunityDirection.SHORT and phase == "Markdown":
        base = 100.0
    elif phase == "Range":
        base = min(base, 50.0)
    return base


def _liquidity_class(percentile: float) -> str:
    if percentile >= 80.0:
        return "ELITE"
    if percentile >= 60.0:
        return "STRONG"
    if percentile >= 40.0:
        return "STANDARD"
    if percentile >= 20.0:
        return "THIN"
    return "LIMITED"


def _median_fit(value: float, peers: Sequence[float]) -> float:
    ordered = sorted(peers)
    median = ordered[len(ordered) // 2]
    spread = max(ordered[-1] - ordered[0], 1e-12)
    return _clamp(100.0 - 100.0 * abs(value - median) / spread, 0.0, 100.0)


def _midrank_percentile(value: float, peers: Sequence[float]) -> float:
    if len(peers) <= 1:
        return 50.0
    less = sum(peer < value for peer in peers)
    equal = sum(peer == value for peer in peers)
    return 100.0 * (less + 0.5 * equal) / len(peers)


def _normalize_timeframe(value: str) -> Timeframe:
    try:
        return Timeframe(value)
    except ValueError as exc:
        raise ValueError(f"unsupported canonical timeframe: {value!r}") from exc


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


__all__ = [
    "OpportunityContext",
    "OpportunityRankingInput",
    "OpportunityRelativeRanker",
    "RankedOpportunity",
]
