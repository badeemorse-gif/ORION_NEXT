"""Dynamic market-universe discovery and deterministic opportunity selection."""
from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any, Callable, Mapping, Protocol, Sequence

from models.opportunity import (
    EligibilityResult, MarketMetrics, OpportunityCandidate,
    OpportunityCandidateSet, UniverseCandidate,
)


class UniverseSource(Protocol):
    def exchange_info(self) -> Mapping[str, Any]: ...


class MetricsSource(Protocol):
    def metrics(self, symbol: str) -> MarketMetrics: ...


class BulkMetricsSource(Protocol):
    def metrics_bulk(self, symbols: Sequence[str]) -> Mapping[str, MarketMetrics]: ...


@dataclass(frozen=True, slots=True)
class OpportunityConfig:
    """Validated, deterministic weights and eligibility thresholds.

    The legacy volume/volatility/liquidity score is preserved as the 60% base
    component. The remaining 40% is reserved for optional analytical features:
    trend, momentum, and market structure. Missing optional features contribute
    a neutral 0.5 rather than inventing a signal.
    """
    quote_assets: tuple[str, ...] = ("USDT",)
    excluded_base_assets: tuple[str, ...] = (
        "USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD", "USDP",
        "USDE", "USDD", "PYUSD", "FRAX", "UST", "USD1", "RLUSD",
        "EURC", "EURS", "EUR",
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
    baseline_score_weight: float = 0.60
    trend_weight: float = 0.15
    momentum_weight: float = 0.15
    structure_weight: float = 0.10
    default_top_n: int = 10
    refresh_interval_seconds: float = 30.0
    hysteresis_score_delta: float = 0.50
    cache_ttl_seconds: float = 30.0
    require_last_price: bool = False

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
        base = (self.volume_weight, self.volatility_weight, self.liquidity_weight)
        analytical = (self.trend_weight, self.momentum_weight, self.structure_weight)
        if any(w < 0 for w in (*base, self.baseline_score_weight, *analytical)):
            raise ValueError("opportunity weights must be non-negative")
        if not math.isclose(sum(base), 1.0, abs_tol=1e-12):
            raise ValueError("legacy opportunity weights must sum to 1")
        if not math.isclose(self.baseline_score_weight + sum(analytical), 1.0, abs_tol=1e-12):
            raise ValueError("V2 opportunity weights must sum to 1")
        if self.default_top_n <= 0:
            raise ValueError("default_top_n must be positive")
        if self.refresh_interval_seconds < 0 or self.cache_ttl_seconds < 0:
            raise ValueError("refresh/cache TTL must be non-negative")
        if self.hysteresis_score_delta < 0:
            raise ValueError("hysteresis_score_delta must be non-negative")


class MarketUniverseDiscovery:
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
            symbol = str(item.get("symbol", "")).strip().upper()
            base = str(item.get("baseAsset", "")).strip().upper()
            quote = str(item.get("quoteAsset", "")).strip().upper()
            status = str(item.get("status", "")).strip().upper()
            if not symbol or not base or not quote or status != "TRADING":
                continue
            if quote not in self._config.quote_assets or base in self._config.excluded_base_assets:
                continue
            if item.get("isSpotTradingAllowed") is False:
                continue
            if item.get("isMarginTradingAllowed") is True and item.get("isSpotTradingAllowed") is None:
                continue
            by_symbol[symbol] = UniverseCandidate(symbol, base, quote)
        return tuple(sorted(by_symbol.values(), key=lambda c: c.symbol))


class MarketEligibilityFilter:
    def __init__(self, config: OpportunityConfig | None = None) -> None:
        self._config = config or OpportunityConfig()

    def evaluate(self, candidate: UniverseCandidate, metrics: MarketMetrics) -> EligibilityResult:
        reasons: list[str] = []
        if candidate.symbol != metrics.symbol:
            reasons.append("SYMBOL_MISMATCH")
        if not metrics.tradable:
            reasons.append("NOT_TRADABLE")
        if self._config.require_last_price and metrics.last_price is None:
            reasons.append("MISSING_PRICE")
        elif metrics.last_price is not None and (not math.isfinite(metrics.last_price) or metrics.last_price <= 0):
            reasons.append("INVALID_PRICE")
        if not math.isfinite(metrics.quote_volume_24h) or metrics.quote_volume_24h < 0:
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
            if not math.isfinite(metrics.spread_bps) or metrics.spread_bps < 0:
                reasons.append("INVALID_SPREAD")
            elif metrics.spread_bps > self._config.max_spread_bps:
                reasons.append("WIDE_SPREAD")
        for label, value in (
            ("VOLUME_QUALITY", metrics.volume_quality),
            ("TREND_QUALITY", metrics.trend_quality),
            ("MOMENTUM_QUALITY", metrics.momentum_quality),
            ("STRUCTURE_QUALITY", metrics.structure_quality),
        ):
            if value is not None and (not math.isfinite(value) or not 0.0 <= value <= 1.0):
                reasons.append(f"INVALID_{label}")
        return EligibilityResult(candidate.symbol, not reasons, tuple(reasons))


class OpportunityScorer:
    def __init__(self, config: OpportunityConfig | None = None) -> None:
        self._config = config or OpportunityConfig()

    @staticmethod
    def _neutral(value: float | None) -> float:
        return 0.5 if value is None else max(0.0, min(value, 1.0))

    def score_components(self, metrics: MarketMetrics) -> tuple[tuple[str, float], ...]:
        volume = max(metrics.quote_volume_24h, 0.0)
        derived_volume_quality = min(math.log1p(volume) / math.log1p(self._config.volume_reference_24h), 1.0)
        volume_component = self._neutral(metrics.volume_quality) if metrics.volume_quality is not None else derived_volume_quality
        distance = abs(metrics.volatility - self._config.target_volatility)
        span = max(self._config.target_volatility - self._config.min_volatility,
                   self._config.max_volatility - self._config.target_volatility, 1e-12)
        volatility_component = max(0.0, 1.0 - distance / span)
        if metrics.spread_bps is None:
            liquidity_component = 0.5
        elif not math.isfinite(metrics.spread_bps) or metrics.spread_bps < 0:
            liquidity_component = 0.0
        else:
            liquidity_component = max(0.0, 1.0 - min(metrics.spread_bps / self._config.max_spread_bps, 1.0))
        baseline = (
            self._config.volume_weight * volume_component
            + self._config.volatility_weight * volatility_component
            + self._config.liquidity_weight * liquidity_component
        )
        return (
            ("legacy_volume", round(volume_component, 8)),
            ("legacy_volatility", round(volatility_component, 8)),
            ("legacy_liquidity", round(liquidity_component, 8)),
            ("baseline", round(baseline, 8)),
            ("trend", round(self._neutral(metrics.trend_quality), 8)),
            ("momentum", round(self._neutral(metrics.momentum_quality), 8)),
            ("structure", round(self._neutral(metrics.structure_quality), 8)),
        )

    def score(self, metrics: MarketMetrics) -> float:
        components = dict(self.score_components(metrics))
        total = (
            self._config.baseline_score_weight * components["baseline"]
            + self._config.trend_weight * components["trend"]
            + self._config.momentum_weight * components["momentum"]
            + self._config.structure_weight * components["structure"]
        )
        return round(100.0 * max(0.0, min(total, 1.0)), 8)


class OpportunityRanker:
    def __init__(self, scorer: OpportunityScorer | None = None, config: OpportunityConfig | None = None) -> None:
        self._config = config or OpportunityConfig()
        self._scorer = scorer or OpportunityScorer(self._config)
        self._previous_rank: dict[str, int] = {}

    def rank(self, candidates: tuple[UniverseCandidate, ...], metrics: Mapping[str, MarketMetrics], top_n: int | None = None) -> OpportunityCandidateSet:
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
            ranked.append(OpportunityCandidate(
                candidate.symbol, self._scorer.score(metric), 0, metric,
                decision.reasons, self._scorer.score_components(metric),
            ))
        ranked.sort(key=lambda item: (-item.opportunity_score, item.symbol))
        if self._previous_rank and self._config.hysteresis_score_delta > 0:
            for i in range(len(ranked) - 1):
                left, right = ranked[i], ranked[i + 1]
                if abs(left.opportunity_score - right.opportunity_score) <= self._config.hysteresis_score_delta:
                    lp, rp = self._previous_rank.get(left.symbol), self._previous_rank.get(right.symbol)
                    if rp is not None and (lp is None or rp < lp):
                        ranked[i], ranked[i + 1] = right, left
        selected = ranked[:requested_top_n]
        result = tuple(OpportunityCandidate(
            item.symbol, item.opportunity_score, index, item.metrics,
            item.eligibility_reasons, item.score_components,
        ) for index, item in enumerate(selected, start=1))
        self._previous_rank = {item.symbol: item.rank for item in result}
        return OpportunityCandidateSet(result, requested_top_n, time.time())


class OpportunityDiscovery:
    """Universe -> bulk feature collection -> eligibility -> score -> rank -> Top-N."""
    def __init__(self, universe: MarketUniverseDiscovery, metrics_source: MetricsSource, config: OpportunityConfig | None = None, clock: Callable[[], float] = time.monotonic) -> None:
        self._universe = universe
        self._metrics_source = metrics_source
        self._config = config or OpportunityConfig()
        self._ranker = OpportunityRanker(config=self._config)
        self._clock = clock
        self._cached_output: OpportunityCandidateSet | None = None
        self._cached_at = -math.inf

    def _collect_metrics(self, candidates: tuple[UniverseCandidate, ...]) -> Mapping[str, MarketMetrics]:
        symbols = tuple(c.symbol for c in candidates)
        bulk = getattr(self._metrics_source, "metrics_bulk", None)
        if callable(bulk):
            raw = bulk(symbols)
            return {symbol: raw[symbol] for symbol in symbols if symbol in raw}
        return {candidate.symbol: self._metrics_source.metrics(candidate.symbol) for candidate in candidates}

    def discover(self, top_n: int | None = None) -> OpportunityCandidateSet:
        candidates = self._universe.discover()
        now = self._clock()
        requested_top_n = top_n if top_n is not None else self._config.default_top_n
        if self._cached_output is not None and now - self._cached_at < self._config.refresh_interval_seconds and self._cached_output.top_n == requested_top_n:
            return self._cached_output
        metrics = self._collect_metrics(candidates)
        output = self._ranker.rank(candidates, metrics, requested_top_n)
        self._cached_output = output
        self._cached_at = now
        return output
