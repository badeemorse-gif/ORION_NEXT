# ORION Future Opportunity Intelligence

## Phase 3 Foundation → Scalping Opportunity Intelligence

The Future Opportunity layer consumes existing Core Intelligence evidence and remains isolated from the current execution pipeline.

### Data flow

```text
AnalysisResult + ProfileResult + ScoreResult + MarketDataset
                         ↓
             CoreOpportunityEvidence
                         ↓
             OpportunityCandidateGenerator
                         ↓
              OpportunityCandidateSet
                         ↓
             OpportunitySelectionPolicy
                         ↓
              OpportunityEvaluation
                         ↓
               TradingReadiness
```

## Evidence rules

The implementation uses only fields already produced by Core:

- `AnalysisResult.market_state`, `strength`, `signals`, and warnings.
- `ProfileResult.market` characteristics, validity/tradeability, and blocks.
- `ScoreResult.category` and factors.
- `MarketDataset` latest canonical `close` for the requested timeframe.

No future indicator, forecast, liquidity feed, ranking metric, or trading signal is fabricated.

`expected_move` remains `None` because Core does not currently provide a forecast/evidence field for it.

## Candidate generation

Directional candidates are generated only when Analysis reports `BULLISH` or `BEARISH`. `NEUTRAL` fails closed rather than becoming a synthetic candidate.

The generated candidate contains the real latest close as an entry candidate, Core confidence/strength evidence, risk state derived from the existing Profile risk level, and the original Core signal/factor evidence.

Freshness is intentionally an explicit dependency. Core currently exposes no canonical freshness-age policy, so the Opportunity layer accepts `FreshnessStatus` as evidence and rejects `UNKNOWN`/`STALE`; it does not invent a time threshold.

## Selection policy

Selection is evidence consistency, not numerical ranking. A candidate must agree with:

1. Analysis directional state.
2. Profile trend.
3. Profile EMA alignment.
4. Score directional category.
5. Profile validity/tradeability.
6. Acceptable risk state.
7. Freshness.
8. Complete candidate contract.

If multiple candidates satisfy all gates and Core supplies no tie-breaker, the policy rejects the selection as ambiguous. It never invents a ranking number.

## Trading readiness

`TradingReadiness` remains a future consumer-side gate. It does not create execution intent, orders, exchange requests, or Binance coupling.

## Explicit non-scope

- No Core Intelligence modifications.
- No Execution implementation.
- No Binance/live trading.
- No Explosive Watchlist dependency.
- No GUI/pipeline wiring.
- No arbitrary thresholds or invented ranking scores.
