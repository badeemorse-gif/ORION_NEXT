# Opportunity Integration Handoff

Repository: badeemorse-gif/ORION_NEXT
Branch: future/opportunity-intelligence-complete
Baseline HEAD reviewed: 31ee50e2954fa62c5811730bd33d66a28a9b7f4c

## Contract lineage

MarketDataset + AnalysisResult + ProfileResult + ScoreResult
-> CoreOpportunityEvidence
-> CandidateGenerator
-> OpportunityCandidateSet
-> SelectionPolicy
-> OpportunityEvaluation
-> TradingReadiness

## Required Core evidence

- MarketDataset: requested canonical timeframe must exist and contain usable close data.
- ProfileResult: exactly one TimeframeProfile must match the requested timeframe. Trend, EMA alignment, confidence and risk are read from that same timeframe profile, not from aggregate market characteristics.
- AnalysisResult: market_state, signals and warnings are consumed as canonical categorical evidence. strength is never mapped to setup_quality.
- ScoreResult: existing directional categories and factors are consumed as provided by Core. No new ranking values or thresholds are introduced.

## Risk contract

Profile risk values are interpreted canonically:
Low and Medium -> ACCEPTABLE
High -> ELEVATED
Extreme -> UNACCEPTABLE
Unknown -> UNKNOWN and fail-closed

## Timeframe contract

The requested timeframe must resolve in both MarketDataset.TimeframeData and ProfileResult.TimeframeProfile. Missing or ambiguous matches reject generation. Different timeframes for the same symbol are not mixed.

## Fail-closed rules

- UNKNOWN and STALE freshness cannot pass selection.
- Non-acceptable risk cannot pass selection.
- setup_quality is explicitly unavailable because Core has no canonical evidence for it. It remains None and is never derived from AnalysisResult.strength.
- An incomplete Opportunity cannot be accepted by OpportunityEvaluation; readiness therefore remains ineligible while setup_quality is unavailable.
- More than one accepted candidate is rejected as ambiguous when Core supplies no tie-breaker. No ranking is invented.
- expected_move remains unavailable because Core supplies no canonical forecast evidence.

## Dependencies

1. AnalysisResult and ScoreResult currently do not expose timeframe provenance. Central integration must guarantee that supplied results correspond to the requested timeframe, or a future Core contract must expose explicit provenance. No Core change is made here.
2. Core currently does not expose a canonical freshness/age contract. The integration boundary must supply authoritative FreshnessStatus. No age threshold is invented here.
3. Core currently has no canonical setup-quality evidence. Until such evidence exists, the boundary remains fail-closed.
4. Core currently has no canonical expected-move evidence. No forecast is fabricated.

## Integration assumptions

- Requested timeframe is a canonical Timeframe.
- Dataset and matching TimeframeProfile describe the same symbol.
- Core categorical semantics are consumed without new business thresholds.
- TradingReadiness is a consumer-side gate only and does not create execution intent.

## Scope exclusions

No Core modification, Execution modification or wiring, live market integration, GUI wiring, pipeline wiring, Watchlist coupling, fabricated forecast, new ranking logic, or new thresholds.

Status: OPPORTUNITY INTEGRATION HANDOFF = COMPLETE
