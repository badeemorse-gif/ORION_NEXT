# ORION — D3 Phase A Clean Relative Ranking

**Baseline:** `c54dc67792776da905a3efb1f667c1869c15db3d`

**Branch:** `phase-a/d3-relative-ranking-clean`

## Scope

This is an independent analytical ranking layer. It does not modify Opportunity eligibility, TradingReadiness, confidence semantics, SelectionPolicy, Execution, Core, main, or Central Integration.

The layer answers only:

```text
Raw Score + Context -> Relative Ranking
```

Neither Raw Score nor Context Score is a probability.

## Raw Score

`ScoreResult.score` remains the canonical raw input. It is not recalibrated and is not written back into `ScoreResult` or `Opportunity.confidence`.

Before combining it with context, the signed raw score is normalized by opportunity direction into a **Directional Raw Strength** on `0..100`:

```text
LONG:  (raw_score + 100) / 2
SHORT: (100 - raw_score) / 2
```

This normalization changes only the ranking coordinate system. It does not change the canonical Raw Score itself and does not reinterpret Raw Score as probability.

Canonical examples:

| Direction | Raw Score | Directional Raw Strength |
|---|---:|---:|
| LONG | +100 | 100 |
| LONG | 0 | 50 |
| LONG | -100 | 0 |
| SHORT | -100 | 100 |
| SHORT | 0 | 50 |
| SHORT | +100 | 0 |

## Context metrics

The Context Score is a bounded analytical composite built from existing evidence:

| Metric | Weight |
|---|---:|
| Volume Expansion | 10% |
| Relative Volume | 15% |
| Volatility Fit | 10% |
| Relative Volatility | 10% |
| Momentum Context | 15% |
| Liquidity Context | 15% |
| Multi-Timeframe Alignment | 15% |
| Market Regime | 10% |

The weights sum to 100%.

### Volume Expansion

Latest volume divided by the median of the previous up to 20 volume observations. The context contribution saturates at 2x so one extreme candle cannot dominate the ranking.

### Relative Volume

The volume-expansion value is converted to a mid-rank percentile across the same peer cohort.

### Relative Volatility

Requested-timeframe Profile volatility is converted to a mid-rank percentile across the same cohort.

### Volatility Fit

Volatility is compared with the cohort median. The metric rewards proximity to the cohort center rather than assuming that more volatility is always better.

### Momentum Context

Canonical Profile momentum states are direction-aware: supportive momentum scores higher for both LONG and SHORT opportunities.

### Liquidity Context

Canonical aggregate Profile liquidity is converted to a cross-sectional percentile. This is ranking context only and is not an eligibility gate.

### Multi-Timeframe Alignment

Available `TimeframeProfile` trend and EMA-alignment evidence are compared with the Opportunity direction. The result is descriptive ordering context only.

### Market Regime

Aggregate Profile trend/phase is used as directional context. `Sideways` is neutral; `Markup` supports LONG; `Markdown` supports SHORT; `Range` remains neutral.

## Composite and cohort

```text
Composite = 0.70 * Directional Raw Strength + 0.30 * Context Score
```

The peer cohort is:

```text
(timeframe, direction)
```

For each cohort:

- Higher Composite means a stronger opportunity within the same cohort.
- Relative Rank is descending Composite Score.
- Percentile uses mid-rank semantics, so ties share a percentile.
- A single-member cohort returns no relative rank/percentile to avoid false precision.

## Determinism and safety

The ranker is deterministic for identical inputs and does not mutate Opportunity state.

Missing required ranking evidence, such as volume history or a matching timeframe profile, is rejected explicitly rather than inferred.

Existing fail-closed contracts remain untouched: freshness, risk, ambiguity, setup quality, confidence semantics, and TradingReadiness are not changed by this layer.

## Tests

`binansScanner/tests/test_opportunity_relative_ranking_clean.py` verifies:

- LONG raw normalization: `+100 -> 100`, `0 -> 50`, `-100 -> 0`;
- SHORT raw normalization: `-100 -> 100`, `0 -> 50`, `+100 -> 0`;
- directional raw strength drives stronger same-direction ranking correctly;
- equal Raw Scores can be separated by context;
- Composite Score remains bounded to `0..100`;
- percentile is cohort-relative;
- cohort isolation uses timeframe + direction;
- SHORT supportive momentum is ranked correctly;
- singleton cohorts expose no false relative precision;
- missing volume fails deterministically;
- Opportunity contract state is not mutated.
