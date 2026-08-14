# Opportunity Integration Handoff

Repository: badeemorse-gif/ORION_NEXT
Branch: future/opportunity-intelligence-complete
Confidence-fix HEAD: e90b3e946223225e4a84b2939d7fcda0c2d5cc77

## Confidence contract

`Opportunity.confidence` is sourced only from the canonical `ProfileResult.TimeframeProfile.confidence` for the requested timeframe.

`AnalysisResult.strength` is a distinct Core signal. It is not treated as Opportunity confidence and is not aggregated with Profile confidence.

No `min()` aggregation, invented formula, or threshold is used. If canonical timeframe Profile confidence is unavailable, confidence remains unavailable and the existing Selection/TradingReadiness gates fail closed.

## Existing integration contract

MarketDataset + AnalysisResult + ProfileResult + ScoreResult
-> CoreOpportunityEvidence
-> CandidateGenerator
-> OpportunityCandidateSet
-> SelectionPolicy
-> OpportunityEvaluation
-> TradingReadiness

The requested timeframe must resolve in both MarketDataset.TimeframeData and ProfileResult.TimeframeProfile. Trend, EMA alignment, confidence, and risk are read from that same timeframe profile.

Profile risk semantics remain canonical: Low/Medium -> ACCEPTABLE, High -> ELEVATED, Extreme -> UNACCEPTABLE, Unknown -> UNKNOWN/fail-closed.

`setup_quality` remains `None` because Core has no canonical evidence for it; it is never derived from AnalysisResult.strength. UNKNOWN/STALE freshness cannot pass, and ambiguous candidates are rejected without invented ranking.

`expected_move` remains unavailable because Core provides no canonical forecast evidence.

## Dependencies

- AnalysisResult and ScoreResult do not expose timeframe provenance; integration must ensure they correspond to the requested timeframe or a future Core contract must expose provenance.
- Core does not expose a canonical freshness-age policy; authoritative FreshnessStatus is supplied at the Opportunity boundary.
- Core has no canonical setup-quality evidence.
- Core has no canonical expected-move evidence.

## Scope exclusions

No Core modification, Execution modification or wiring, live trading, Binance, GUI/pipeline wiring, Explosive Watchlist coupling, fabricated forecast, new ranking logic, or new thresholds.

Status: OPPORTUNITY INTEGRATION HANDOFF = COMPLETE
