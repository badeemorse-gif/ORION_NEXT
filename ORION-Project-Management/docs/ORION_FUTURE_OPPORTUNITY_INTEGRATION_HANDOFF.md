# ORION Future Opportunity Intelligence — Integration Handoff

## Handoff identity

- Repository: `badeemorse-gif/ORION_NEXT`
- Branch: `future/opportunity-intelligence-complete`
- Handoff baseline HEAD: `31ee50e2954fa62c5811730bd33d66a28a9b7f4c`
- PR: `#11`
- Scope: central-integration readiness only; no Core, Execution, GUI, pipeline, Binance, or Watchlist wiring.

## Canonical contract lineage

```text
MarketDataset
  + AnalysisResult
  + ProfileResult
  + ScoreResult
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

`OpportunityCandidateSet` is transport-only. It does not rank, score, filter, or create trading intent.
`OpportunityEvaluation` is an acceptance/rejection boundary. `TradingReadiness` is a consumer-side gate only and has no execution intent.

## Required Core evidence

### MarketDataset

The requested opportunity timeframe must exist as a canonical `MarketDataset.TimeframeData` entry and contain usable market data, including the canonical `close` field used for the entry candidate.

### ProfileResult

The same requested timeframe must resolve to exactly one `ProfileResult.TimeframeProfile`. Opportunity-specific trend, EMA alignment, confidence, and risk are read from this timeframe profile, never from aggregate `ProfileResult.market` characteristics.

Risk semantics are canonical Profile semantics:

- `Low` → `ACCEPTABLE`
- `Medium` → `ACCEPTABLE`
- `High` → `ELEVATED`
- `Extreme` → `UNACCEPTABLE`
- unknown value → `UNKNOWN` and fail-closed

### AnalysisResult

The current Core contract provides `market_state`, `strength`, `signals`, and `warnings`. Directional state is consumed as categorical evidence only. `strength` is not mapped to `setup_quality`.

### ScoreResult

The current Core contract provides `score`, `category`, `factors`, and `warnings`. Opportunity selection accepts only the existing directional categories produced by Core (`BULLISH`, `STRONG_BULLISH`, `BEARISH`, `STRONG_BEARISH`). No new ranking number or threshold is introduced by Opportunity Intelligence.

## Fail-closed rules

- `UNKNOWN` or `STALE` freshness cannot be selected.
- Missing or ambiguous requested timeframe data/profile evidence rejects candidate generation.
- Risk states other than `ACCEPTABLE` reject selection.
- `setup_quality` remains explicitly unavailable (`None`) because Core has no canonical setup-quality evidence. It is never derived from `AnalysisResult.strength`.
- Because the Opportunity contract requires setup quality for completeness, candidates without it remain ineligible and `TradingReadiness` remains false.
- Multiple accepted candidates are rejected as ambiguous when Core provides no evidence-backed tie-breaker. No ranking is invented.
- `expected_move` remains unavailable because Core does not provide canonical forecast/expected-move evidence.

## Integration dependencies

1. **Timeframe provenance for AnalysisResult and ScoreResult** — the current Core contracts do not carry a timeframe field. Opportunity therefore cannot independently prove that aggregate `AnalysisResult` and `ScoreResult` instances were produced for the requested Opportunity timeframe. The central integration layer must provide those results with the same timeframe provenance as the requested Opportunity, or Core must later expose explicit timeframe provenance. Developer 3 does not modify Core here.
2. **Freshness provenance** — current Core contracts do not expose a canonical Opportunity freshness status or an age threshold. The integration boundary must supply `FreshnessStatus` from an authoritative freshness source. No age threshold is fabricated by Opportunity Intelligence.
3. **Setup quality evidence** — no canonical Core field currently represents setup quality. Until Core supplies such evidence, the field remains unavailable and readiness fails closed.
4. **Expected move / forecast** — no canonical Core evidence supplies expected move. It remains `None`; no forecast is synthesized.

## Integration assumptions

- The requested timeframe is a canonical `Timeframe` value.
- `MarketDataset` and the selected `TimeframeProfile` describe the same symbol.
- `AnalysisResult.market_state` and `ScoreResult.category` are canonical Core outputs and are not reinterpreted with new business thresholds inside Opportunity Intelligence.
- `ProfileResult.is_valid` represents the existing Core validity/tradeability boundary.
- Freshness is an external evidence input until Core exposes an authoritative freshness contract.
- Candidate selection does not imply execution readiness, order intent, Binance connectivity, or live trading.

## Known future dependencies

- Explicit timeframe provenance for Analysis/Score if central integration needs runtime verification rather than caller-level provenance.
- Canonical setup-quality evidence from Core before an Opportunity can become structurally complete.
- Canonical freshness evidence from Core or an approved upstream boundary.
- Canonical expected-move evidence only if a future product requirement actually requires that field.

## Future risk / universe policy dependency

The desired future product behavior is documented separately in:

`ORION-Project-Management/docs/ORION_FUTURE_RISK_UNIVERSE_AND_CONTROL_CENTER_POLICY.md`

Key decisions recorded there for later implementation:

- signal existence must remain distinct from trade eligibility;
- `High` and `Extreme` risk should be representable as risk states even when execution is blocked, subject to a future approved policy change;
- new listings should not be permanently hidden merely for being new, but insufficient history must block automatic trading until evidence is sufficient;
- the intended future market universe is Binance Spot `USDT` pairs with explicit eligibility and data-quality gates;
- blocked signals may feed an `Explosive Watchlist` as analytics-only evidence without becoming execution intent;
- the future GUI should expose signal, risk, data status, and trade status separately.

This section is **deferred policy only**. It does not override the current fail-closed Opportunity/Profile contracts.

## Explicit non-scope

- No Core Intelligence modification.
- No Execution modification or wiring.
- No Binance or live trading.
- No GUI or current pipeline wiring.
- No Explosive Watchlist coupling.
- No ranking thresholds or fabricated scores/forecasts.

## Handoff status

`OPPORTUNITY INTEGRATION HANDOFF = COMPLETE`

The package is ready for central integration subject to the dependencies above. Those dependencies are documented rather than invented or silently filled.
