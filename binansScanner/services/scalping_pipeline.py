"""D1 scalping pipeline orchestration over the existing dynamic universe boundary."""
from __future__ import annotations

from typing import Mapping, Sequence

from models.opportunity import OpportunityCandidateSet
from models.scalping_opportunity import Candle, ScalpingCandidateSet
from services.opportunity_discovery import OpportunityDiscovery
from services.scalping_opportunity import ScalpingCandidatePoolManager, ScalpingDecisionEngine


class ScalpingOpportunityPipeline:
    """Universe -> broad opportunity pool -> evaluation -> stable active set."""

    def __init__(
        self,
        discovery: OpportunityDiscovery,
        candle_source,
        *,
        decision_engine: ScalpingDecisionEngine | None = None,
        pool_manager: ScalpingCandidatePoolManager | None = None,
    ) -> None:
        self.discovery = discovery
        self.candle_source = candle_source
        self.decision_engine = decision_engine or ScalpingDecisionEngine()
        self.pool_manager = pool_manager or ScalpingCandidatePoolManager(self.decision_engine.config)

    def _candles_for(self, symbol: str) -> Mapping[str, Sequence[Candle]]:
        return {
            timeframe: tuple(self.candle_source.candles(symbol, timeframe, self.decision_engine.config.min_candles))
            for timeframe in ("1d", "4h", "1h", "15m")
        }

    def discover(self, top_n: int | None = None, **decision_kwargs) -> ScalpingCandidateSet:
        """Evaluate the broad pool before selecting the smaller stable active set.

        ``top_n`` is an explicit broad-discovery override. The default uses the
        dedicated ``broad_pool_top_n``; ``active_top_n`` is never used as the
        discovery limit.
        """
        broad_top_n = top_n if top_n is not None else self.pool_manager.config.broad_pool_top_n
        if broad_top_n <= self.pool_manager.config.active_top_n:
            raise ValueError("broad discovery pool must be larger than active_top_n")
        broad = self.discovery.discover(top_n=broad_top_n)
        enriched = []
        for candidate in broad.candidates:
            try:
                candle_map = self._candles_for(candidate.symbol)
            except Exception:
                candle_map = {}
            enriched.append(self.decision_engine.decide(candidate, candle_map, **decision_kwargs))
        return self.pool_manager.select(broad, enriched)
