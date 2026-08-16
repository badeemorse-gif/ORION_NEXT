# ORION Opportunity Relative Ranking — Phase A

**Scope:** Future Opportunity Intelligence only.

**Baseline reviewed:** `c54dc67792776da905a3efb1f667c1869c15db3d`

**Implementation branch:** `developer3/opportunity-relative-ranking-phase-a`

## Purpose

`ScoreResult.score` remains the canonical **Raw Score**. It is not recalibrated and is not changed by the ranking layer.

The problem addressed here is cross-sectional comparability: two candidates can both have `Raw Score = 100` while their market context differs materially. Relative ranking therefore adds a bounded **Context Score** and a cross-sectional **Composite Score** for ordering only.

No ranking result changes Opportunity eligibility, `SelectionPolicy`, `TradingReadiness`, execution behavior, or accepted Central Integration contracts.

## Raw vs Context

### Raw Score

```text
Raw Score = existing ScoreResult.score
```

The ranker only clamps the value to the display/ranking range `[0, 100]`; it does not derive a new score from Profile confidence or any other signal.

### Context Score

Context is normalized to `[0, 100]` and uses eight components:

| Component | Weight | Direction |
|---|---:|---|
| Volume expansion | 10% | higher expansion is stronger, with saturation at 2x |
| Relative Volume percentile | 15% | higher within peer cohort is stronger |
| Volatility fit | 10% | proximity to peer-median volatility is stronger; extremes are not automatically rewarded |
| Relative Volatility percentile | 10% | descriptive cross-sectional position |
| Momentum | 15% | direction-aware: supportive momentum scores high for both LONG and SHORT |
| Liquidity percentile | 15% | higher peer-relative liquidity is stronger |
| Multi-timeframe alignment | 15% | matching trend + EMA alignment across available timeframe profiles |
| Market-regime alignment | 10% | directional trend/phase alignment; `Range` is neutral |

The weights sum to 100%.

## Composite Score

```text
Composite Score = 0.70 × Raw Score + 0.30 × Context Score
```

This preserves Raw Score as the dominant signal while allowing materially different context to separate otherwise tied candidates.

Example:

```text
A: Raw=100, Context=40  → Composite=82
B: Raw=100, Context=90  → Composite=97
```

The two candidates are no longer falsely equivalent even though their raw Score is identical.

## Relative cohort

Relative ranking is performed only among candidates sharing:

```text
(timeframe, direction)
```

Market regime is **not** used as a cohort partition; it remains a contextual factor. This avoids artificially shrinking peer groups while still allowing regime quality to affect ordering.

For each cohort:

- `Relative Rank` is ordinal, descending by Composite Score.
- `Relative Percentile` uses mid-rank percentile semantics so exact ties share the same percentile.
- A single-member cohort has `relative_rank=None` and `relative_percentile=None`; no false precision is reported.

## Context derivation

### Volume expansion

```text
volume_expansion = latest_volume / median(previous up to 20 volumes)
```

`1.0x` is neutral. The contribution saturates at `2.0x`; one extreme candle cannot dominate the Context Score.

### Relative Volume

The volume-expansion values are converted to a percentile across the candidate's peer cohort.

### Volatility

The ranker uses the canonical requested-timeframe `TimeframeProfile.characteristics.volatility`.

### Relative Volatility

Volatility is converted to a percentile across the same peer cohort.

### Volatility fit

Absolute volatility is not assumed to be inherently better. Fit is measured against the cohort median and penalizes distance from that median.

### Momentum

The canonical Profile momentum state maps to a normalized score:

```text
Strong Buy  = 100
Buy         = 75
Neutral     = 50
Sell        = 25
Strong Sell = 0
```

For SHORT opportunities the scale is inverted, so directionally supportive momentum remains high-quality context.

### Liquidity class

Liquidity is normalized cross-sectionally and exposed as a descriptive class:

```text
>=80 percentile → ELITE
>=60            → STRONG
>=40            → STANDARD
>=20            → THIN
<20             → LIMITED
```

These classes affect ordering only and are not eligibility gates.

### Multi-timeframe alignment

Each available `TimeframeProfile` contributes two checks:

1. trend matches opportunity direction;
2. EMA alignment matches opportunity direction.

Alignment is the percentage of successful checks across all available timeframes.

### Market regime

The aggregate Profile regime is directional context only:

- directional trend aligned with the opportunity → strong;
- `Sideways` → neutral;
- opposing trend → weak;
- `Markup` supports LONG and `Markdown` supports SHORT;
- `Range` caps regime contribution at neutral.

## Fail-closed preservation

This layer deliberately does **not** alter any existing fail-closed contract:

- `setup_quality` remains `None`.
- `UNKNOWN` / `STALE` freshness remains non-eligible.
- ambiguity remains rejected by existing SelectionPolicy semantics.
- timeframe-specific Profile evidence remains required by existing Opportunity Intelligence.
- existing risk semantics remain unchanged.
- no ranking score is written back into `Opportunity.confidence` or `ScoreResult.score`.

## Testability

`tests/test_opportunity_relative_ranking.py` covers:

- identical Raw Scores separated by contextual quality;
- cross-sectional percentiles;
- cohort isolation by timeframe and direction;
- direction-aware momentum;
- non-mutation of Opportunity contract state;
- deterministic rejection when volume history is unavailable.

Phase A is therefore an isolated ranking/calibration layer, not an eligibility or execution feature.
