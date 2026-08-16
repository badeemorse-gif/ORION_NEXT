# ORION Opportunity Relative Ranking — Phase A

**Scope:** Future Opportunity Intelligence only.

**Baseline reviewed:** `c54dc67792776da905a3efb1f667c1869c15db3d`

**Design/implementation branch:** `developer3/opportunity-relative-ranking-phase-a`

## Purpose

`ScoreResult.score` remains the canonical **Raw Score**. It is not recalibrated and is not changed by the ranking layer.

Relative ranking adds a bounded **Context Score** and a cross-sectional **Composite Score** for ordering only, so two candidates with equal Raw Scores can still be separated when their market context differs.

## Formula

```text
Composite Score = 0.70 × Raw Score + 0.30 × Context Score
```

The Context Score contains eight components:

| Component | Weight |
|---|---:|
| Volume expansion | 10% |
| Relative Volume percentile | 15% |
| Volatility fit | 10% |
| Relative Volatility percentile | 10% |
| Momentum | 15% |
| Liquidity percentile | 15% |
| Multi-timeframe alignment | 15% |
| Market-regime alignment | 10% |

Weights sum to 100%. Raw Score remains dominant.

## Cohort

Relative ranking compares only candidates sharing `(timeframe, direction)`. Market regime remains a context factor rather than a cohort partition.

`relative_rank` is descending Composite Score. `relative_percentile` uses mid-rank percentile semantics so exact ties receive equal percentile. Single-member cohorts report no relative rank/percentile instead of false precision.

## Context derivation

- **Volume expansion:** latest volume / median of the previous up to 20 candles. `1.0x` is neutral and the contribution saturates at `2.0x`.
- **Relative Volume:** percentile of volume expansion within the peer cohort.
- **Volatility:** canonical requested-timeframe `TimeframeProfile.characteristics.volatility`.
- **Relative Volatility:** cohort percentile of volatility.
- **Volatility fit:** proximity to the cohort median; extremes are not automatically rewarded.
- **Momentum:** `Strong Buy=100`, `Buy=75`, `Neutral=50`, `Sell=25`, `Strong Sell=0`; inverted for SHORT so directionally supportive momentum remains high.
- **Liquidity:** cohort percentile plus descriptive classes `ELITE / STRONG / STANDARD / THIN / LIMITED` at 80/60/40/20 percentile bands. These are ranking descriptors only.
- **Multi-timeframe alignment:** percentage of trend and EMA-alignment checks matching the opportunity direction across available timeframe profiles.
- **Market regime:** aggregate directional trend/phase context; Markup supports LONG, Markdown supports SHORT, Sideways is neutral, Range caps the contribution at neutral.

## Contract safety

This layer does not change Opportunity eligibility, SelectionPolicy, TradingReadiness, Execution, or accepted Integration. It never writes ranking values back into `Opportunity.confidence` or `ScoreResult.score`.

`setup_quality` remains `None`; `UNKNOWN/STALE` freshness remains fail-closed; existing ambiguity and risk semantics remain unchanged.

## Test coverage

`tests/test_opportunity_relative_ranking.py` proves tied Raw Scores can separate by context, percentiles are cohort-based, timeframe/direction cohorts are isolated, SHORT momentum is direction-aware, Opportunity state is not mutated, and missing volume history fails deterministically.
