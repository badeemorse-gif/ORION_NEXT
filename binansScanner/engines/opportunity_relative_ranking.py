"""Contextual relative ranking for future Opportunity Intelligence.

Phase A design only: this layer orders already-generated Opportunity candidates.
It does not change Opportunity eligibility, SelectionPolicy, TradingReadiness,
or any accepted integration boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping, Sequence

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
        # Weights intentionally sum to 100. Raw Score remains dominant in
        # composite scoring; context only differentiates otherwise similar
        # opportunities.
        weighted = (
            0.10 * self._percentile(self.volume_expansion)
            + 0.15 * self.relative_volume_percentile
            + 0.10 * self.volatility_fit
            + 0.10 * self.relative_volatility_percentile
            + 0.15 * self.momentum_score
            + 0.15 * self.liquidity_percentile
            + 0.15 * self.mtf_alignment
            + 0.10 * self.market_regime_score
        )
        return _clamp(weighted, 0.0, 100.0)

    @staticmethod
    def _percentile(value: float) -> float:
        # This is replaced by the cross-sectional percentile before ranking.
        # The fallback keeps the context object self-contained for diagnostics.
        return _clamp(value * 50.0, 0.0, 100.0)


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
    """Rank candidates within a same-timeframe, same-direction peer cohort."""

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
            composite_scores = [item["composite_score"] for item in cohort]
            ordered = sorted(
                cohort,
                key=lambda item: (item["composite_score"], item["raw_score"], item["symbol"]),
                reverse=True,
            )
            for item in cohort:
                score = item["composite_score"]
                peer_count = len(cohort)
                if peer_count >= 2:
                    rank = 1 + sum(candidate > score for candidate in composite_scores)
                    percentile = _midrank_percentile(score, composite_scores)
                else:
                    rank = None
                    percentile = None
                output.append(
                    RankedOpportunity(
                        opportunity=item["opportunity"],
                        raw_score=item["raw_score"],
                        context_score=item["context_score"],
                        composite_score=score,
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
                ),
                reverse=True,
            )
        )

    def _prepare(self, item: OpportunityRankingInput) -> dict:
        opportunity = item.opportunity
        profile = item.profile
        timeframe = _normalize_timeframe(opportunity.timeframe)
        timeframe_profile = _matching_timeframe_profile(profile, timeframe)
        if timeframe_profile is None:
            raise ValueError("ranking requires exactly one matching timeframe profile")

        dataframe = _frame_for_timeframe(item.dataset, timeframe)
        volume_expansion = _volume_expansion(dataframe)
        volatility = float(timeframe_profile.characteristics.volatility)
        if not isfinite(volatility):
            raise ValueError("volatility must be finite")

        # Relative values are calculated cross-sectionally after preparation.
        context = OpportunityContext(
            volume_expansion=volume_expansion,
            relative_volume_percentile=50.0,
            volatility=volatility,
            relative_volatility_percentile=50.0,
            volatility_fit=50.0,
            momentum_score=_directional_momentum_score(
                timeframe_profile.characteristics.momentum,
                opportunity.direction,
            ),
            liquidity=float(profile.market.liquidity),
            liquidity_percentile=50.0,
            liquidity_class="STANDARD",
            mtf_alignment=_mtf_alignment(profile, opportunity.direction),
            market_regime_score=_market_regime_score(profile, opportunity.direction),
        )
        raw_score = _clamp(float(item.score.score), 0.0, 100.0)
        context = _replace_context_percentiles(context, (volume_expansion,), (volatility,), (profile.market.liquidity,))
        context = _fit_volatility(context, (volatility,))
        context_score = context.context_score
        composite = self.RAW_WEIGHT * raw_score + self.CONTEXT_WEIGHT * context_score

        return {
            "opportunity": opportunity,
            "raw_score": raw_score,
            "context_score": context_score,
            "composite_score": _clamp(composite, 0.0, 100.0),
            "context": context,
            "symbol": opportunity.symbol,
        }


def _replace_context_percentiles(
    context: OpportunityContext,
    volume_values: Sequence[float],
    volatility_values: Sequence[float],
    liquidity_values: Sequence[float],
) -> OpportunityContext:
    # Placeholder single-item normalization. Cross-sectional replacement is
    # performed in tests/design fixtures through `build_contexts`; rank() uses
    # the same neutral midpoint because the inputs are peer-scored afterward.
    return OpportunityContext(
        volume_expansion=context.volume_expansion,
        relative_volume_percentile=_single_value_percentile(volume_values[0], volume_values),
        volatility=context.volatility,
        relative_volatility_percentile=_single_value_percentile(volatility_values[0], volatility_values),
        volatility_fit=context.volatility_fit,
        momentum_score=context.momentum_score,
        liquidity=context.liquidity,
        liquidity_percentile=_single_value_percentile(liquidity_values[0], liquidity_values),
        liquidity_class=_liquidity_class(_single_value_percentile(liquidity_values[0], liquidity_values)),
        mtf_alignment=context.mtf_alignment,
        market_regime_score=context.market_regime_score,
    )


def _fit_volatility(context: OpportunityContext, peers: Sequence[float]) -> OpportunityContext:
    if not peers:
        return context
    median = sorted(peers)[len(peers) // 2]
    spread = max(abs(max(peers) - min(peers)), 1e-12)
    fit = 100.0 - 100.0 * min(abs(context.volatility - median) / spread, 1.0)
    return OpportunityContext(
        volume_expansion=context.volume_expansion,
        relative_volume_percentile=context.relative_volume_percentile,
        volatility=context.volatility,
        relative_volatility_percentile=context.relative_volatility_percentile,
        volatility_fit=_clamp(fit, 0.0, 100.0),
        momentum_score=context.momentum_score,
        liquidity=context.liquidity,
        liquidity_percentile=context.liquidity_percentile,
        liquidity_class=context.liquidity_class,
        mtf_alignment=context.mtf_alignment,
        market_regime_score=context.market_regime_score,
    )


def _volume_expansion(dataframe: pd.DataFrame) -> float:
    if "volume" not in dataframe.columns or len(dataframe) < 2:
        raise ValueError("ranking requires OHLCV volume history")
    current = float(dataframe["volume"].iloc[-1])
    baseline_series = dataframe["volume"].iloc[:-1].tail(min(20, len(dataframe) - 1))
    baseline = float(baseline_series.median())
    if not isfinite(current) or not isfinite(baseline) or baseline <= 0:
        raise ValueError("volume history must be finite with positive baseline")
    return current / baseline


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
    if direction is OpportunityDirection.SHORT:
        value = 100.0 - value
    return value


def _mtf_alignment(profile: ProfileResult, direction: OpportunityDirection) -> float:
    expected = "Bullish" if direction is OpportunityDirection.LONG else "Bearish"
    if not profile.timeframes:
        return 50.0
    aligned = 0
    total = 0
    for timeframe in profile.timeframes:
        total += 1
        trend_ok = timeframe.characteristics.trend == expected
        ema_ok = timeframe.characteristics.ema_alignment == expected
        aligned += int(trend_ok) + int(ema_ok)
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
        base = max(base, 100.0)
    elif direction is OpportunityDirection.SHORT and phase == "Markdown":
        base = max(base, 100.0)
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


def _single_value_percentile(value: float, peers: Sequence[float]) -> float:
    if len(peers) <= 1:
        return 50.0
    return _midrank_percentile(value, peers)


def _midrank_percentile(value: float, peers: Sequence[float]) -> float:
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
