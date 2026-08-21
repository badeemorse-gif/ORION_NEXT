"""Deterministic market-universe discovery, eligibility, scoring and ranking."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Protocol

from models.opportunity import (
    EligibilityResult,
    MarketMetrics,
    OpportunityCandidate,
    OpportunityCandidateSet,
    UniverseCandidate,
)


class UniverseSource(Protocol):
    """Venue boundary capable of returning exchange symbol metadata."""

    def exchange_info(self) -> Mapping[str, Any]:
        ...


class MetricsSource(Protocol):
    """Source of normalized market metrics for a symbol."""

    def metrics(self, symbol: str) -> MarketMetrics:
        ...


@dataclass(frozen=True, slots=True)
class OpportunityConfig:
    """Deterministic eligibility and scoring parameters."""

    quote_assets: tuple[str, ...] = ("USDT",)
    excluded_base_assets: tuple[str, ...] = (
        "USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD", "USDP", "EUR",
    )
    min_quote_volume_24h: float = 1_000_000.0
    min_volatility: float = 0.001
    max_volatility: float = 0.20
    max_spread_bps: float = 50.0
    volume_reference_24h: float = 100_000_000.0
    target_volatility: float = 0.03
    volume_weight: float = 0.50
    volatility_weight: float = 0.30
    liquidity_weight: float = 0.20
    default_top_n: int = 10

    def __post_init__(self) -> None:
        if not self.quote_assets:
            raise ValueError("At least one quote asset is required")
        if self.min_quote_volume_24h < 0:
            raise ValueError("min_quote_volume_24h must be non-negative")
        if not 0 <= self.min_volatility <= self.max_volatility:
            raise ValueError("volatility bounds are invalid")
        if self.max_spread_bps <= 0:
            raise ValueError("max_spread_bps must be positive")
        if self.volume_reference_24h <= 0:
            raise ValueError("volume_reference_24h must be positive")
        if not self.min_volatility <= self.target_volatility <= self.max_volatility:
            raise ValueError("target_volatility must be within eligibility bounds")
        weights = (
            self.volume_weight,
            self.volatility_weight,
            self.liquidity_weight,
        )
        if any(weight < 0 for weight in weights) or not math.isclose(sum(weights), 1.0, abs_tol=1e-12):
            raise ValueError("opportunity weights must be non-negative and sum to 1")
        if self.default_top_n <= 0:
            raise ValueError("default_top_n must be positive")


class MarketUniverseDiscovery:
    """Discover deterministic, venue-trading universe candidates."""

    def __init__(self, source: UniverseSource, config: OpportunityConfig | None = None) -> None:
        self._source = source
        self._config = config or OpportunityConfig()

    def discover(self) -> tuple[UniverseCandidate, ...]:
        payload = self._source.exchange_info()
        symbols = payload.get("symbols", [])
        by_symbol: dict[str, UniverseCandidate] = {}

        for item in symbols:
            if not isinstance(item, Mapping):
                continue
            symbol = str(item.get("symbol", "")).upper()
            base = str(item.get("baseAsset", "")).upper()
            quote = str(item.get("quoteAsset", "")).upper()
            status = str(item.get("status", "")).upper()
            if not symbol or not base or not quote:
                continue
            if status != "TRADING":
                continue
            if quote not in self._config.quote_assets:
                continue
            if base in self._config.excluded_base_assets:
                continue
            if item.get("isSpotTradingAllowed") is False:
                continue
            by_symbol[symbol] = UniverseCandidate(
                symbol=symbol,
                base_asset=base,
                quote_asset=quote,
            )

        return tuple(sorted(by_symbol.values(), key=lambda candidate: candidate.symbol))


class MarketEligibilityFilter:
    """Fail-closed eligibility checks for liquidity, volume, volatility and spread."""

    def __init__(self, config: OpportunityConfig | None = None) -> None:
        self._config = config or OpportunityConfig()

    def evaluate(self, candidate: UniverseCandidate, metrics: MarketMetrics) -> EligibilityResult:
        reasons: list[str] = []
        if candidate.symbol != metrics.symbol:
            reasons.append("SYMBOL_MISMATCH")
        if not metrics.tradable:
            reasons.append("NOT_TRADABLE")
        if not math.isfinite(metrics.quote_volume_24h):
            reasons.append("INVALID_VOLUME")
        elif metrics.quote_volume_24h < self._config.min_quote_volume_24h:
            reasons.append("LOW_VOLUME")
        if not math.isfinite(metrics.volatility):
            reasons.append("INVALID_VOLATILITY")
        elif metrics.volatility < self._config.min_volatility:
            reasons.append("LOW_VOLATILITY")
        elif metrics.volatility > self._config.max_volatility:
            reasons.append("HIGH_VOLATILITY")
        if metrics.spread_bps is not None:
            if not math.isfinite(metrics.spread_bps):
                reasons.append("INVALID_SPREAD")
            elif metrics.spread_bps > self._config.max_spread_bps:
                reasons.append("WIDE_SPREAD")
            elif metrics.spread_bps < 0:
                reasons.append("INVALID_SPREAD")
        return EligibilityResult(
            symbol=candidate.symbol,
            eligible=not reasons,
            reasons=tuple(reasons),
        )


class OpportunityScorer:
    """Produce a deterministic [0, 100] opportunity score from normalized metrics."""

    def __init__(self, config: OpportunityConfig | None = None) -> None:
        self._config = config or OpportunityConfig()

    def score(self, metrics: MarketMetrics) -> float:
        volume = max(metrics.quote_volume_24h, 0.0)
        volume_component = min(
            math.log1p(volume) / math.log1p(self._config.volume_reference_24h),
            1.0,
        )
        distance = abs(metrics.volatility - self._config.target_volatility)
        span = max(
            self._config.target_volatility - self._config.min_volatility,
            self._config.max_volatility - self._config.target_volatility,
            1e-12,
        )
        volatility_component = max(0.0, 1.0 - (distance / span))
        if metrics.spread_bps is None:
            liquidity_component = 0.5
        elif not math.isfinite(metrics.spread_bps) or metrics.spread_bps < 0:
            liquidity_component = 0.0
        else:
            liquidity_component = max(
                0.0,
                1.0 - min(metrics.spread_bps / self._config.max_spread_bps, 1.0),
            )
        total = (
            self._config.volume_weight * volume_component
            + self._config.volatility_weight * volatility_component
            + self._config.liquidity_weight * liquidity_component
        )
        return round(100.0 * max(0.0, min(total, 1.0)), 8)


class OpportunityRanker:
    """Stable deterministic ranking with symbol tie-breaks and top-N selection."""

    def __init__(self, scorer: OpportunityScorer | None = None, config: OpportunityConfig | None = None) -> None:
        self._config = config or OpportunityConfig()
        self._scorer = scorer or OpportunityScorer(self._config)

    def rank(
        self,
        candidates: tuple[UniverseCandidate, ...],
        metrics: Mapping[str, MarketMetrics],
        top_n: int | None = None,
    ) -> OpportunityCandidateSet:
        requested_top_n = top_n if top_n is not None else self._config.default_top_n
        if requested_top_n <= 0:
            raise ValueError("top_n must be positive")
        eligibility = MarketEligibilityFilter(self._config)
        ranked: list[OpportunityCandidate] = []
        for candidate in candidates:
            metric = metrics.get(candidate.symbol)
            if metric is None:
                continue
            decision = eligibility.evaluate(candidate, metric)
            if not decision.eligible:
                continue
            ranked.append(
                OpportunityCandidate(
                    symbol=candidate.symbol,
                    opportunity_score=self._scorer.score(metric),
                    rank=0,
                    metrics=metric,
                    eligibility_reasons=decision.reasons,
                )
            )

        ranked.sort(key=lambda item: (-item.opportunity_score, item.symbol))
        ranked = [
            OpportunityCandidate(
                symbol=item.symbol,
                opportunity_score=item.opportunity_score,
                rank=index,
                metrics=item.metrics,
                eligibility_reasons=item.eligibility_reasons,
            )
            for index, item in enumerate(ranked[:requested_top_n], start=1)
        ]
        return OpportunityCandidateSet(candidates=tuple(ranked), top_n=requested_top_n)


class OpportunityDiscovery:
    """Complete Universe -> Filter -> Score -> Rank -> Top-N orchestration boundary."""

    def __init__(
        self,
        universe: MarketUniverseDiscovery,
        metrics_source: MetricsSource,
        config: OpportunityConfig | None = None,
    ) -> None:
        self._universe = universe
        self._metrics_source = metrics_source
        self._config = config or OpportunityConfig()
        self._ranker = OpportunityRanker(config=self._config)

    def discover(self, top_n: int | None = None) -> OpportunityCandidateSet:
        candidates = self._universe.discover()
        metrics = {
            candidate.symbol: self._metrics_source.metrics(candidate.symbol)
            for candidate in candidates
        }
        return self._ranker.rank(candidates, metrics, top_n=top_n)
