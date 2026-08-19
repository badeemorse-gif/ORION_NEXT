# ORION Market Data Quality Contract

## Scope

This contract owns only `MarketDataset` integrity and provenance. It does not define indicator semantics, profile semantics, score, decision, opportunity, or execution behavior.

## Canonical guarantees

A dataset is valid only when all of the following hold:

1. **Structure**
   - The value is a `MarketDataset`.
   - Each timeframe contains a non-empty OHLCV `DataFrame`.
   - Required columns are `open`, `high`, `low`, `close`, and `volume`.
   - Timestamps are timezone-aware, unique, and chronologically ordered.
   - Candle count and first/last timestamps agree with the actual frame.

2. **Finite numeric data**
   - Every OHLCV column must already have a numeric dtype; numeric-looking strings are not coerced into numbers.
   - OHLCV values must be finite.
   - `NaN`, positive infinity, and negative infinity are rejected.
   - Numeric validation completes before any OHLC or volume comparisons are evaluated.
   - A non-numeric or non-finite OHLCV condition records an integrity issue and exits timeframe validation before unsafe comparisons.
   - Volume cannot be negative.
   - OHLC relationships must be internally coherent.

3. **Timeframe integrity**
   - The `TimeframeData.timeframe` must match the `MarketDataset.timeframes` key.
   - Candle spacing must exactly match the canonical interval for that timeframe.
   - A missing candle/gap is an integrity failure; no interpolation, forward-fill, or synthetic candle is permitted.

4. **Provenance**
   - Symbol, exchange, source, and cache version are mandatory non-empty provenance fields.
   - `downloaded_at` and `last_updated_at` must be timezone-aware.
   - `last_updated_at` cannot precede `downloaded_at`.
   - A dataset explicitly marked invalid cannot pass the contract.

5. **Missing / stale / invalid states**
   - `MISSING` means a caller-required timeframe is absent.
   - `INVALID` means structural, numeric, provenance, or cadence integrity failed.
   - `STALE` is emitted only when the caller explicitly supplies `max_age` and the latest candle exceeds that threshold.
   - No default freshness threshold is invented by this layer.

## Fail-closed rule

`MarketDatasetQualityValidator.assert_valid()` raises `DataQualityError` for every non-valid state. It never repairs data and never fabricates a trading-ready substitute.

The Binance mapper invokes this assertion before returning a `MarketDataset`, so invalid cadence, gaps, non-numeric values, non-finite values, and invalid provenance cannot cross the canonical market-data boundary.

For non-numeric OHLCV input, the validator records `INVALID` and returns before executing negative-volume or OHLC relationship comparisons on the invalid data. This guarantees a controlled quality result or `DataQualityError`, rather than an incidental Python/pandas comparison exception.

## Provenance lineage

The canonical `MarketMetadata` fields remain the source-of-truth provenance attached to every dataset:

- `symbol`
- `exchange`
- `source`
- `cache_version`
- `downloaded_at`
- `last_updated_at`
- `is_valid`
- `validation_message`

Freshness is evaluated separately because a freshness threshold is policy supplied by the caller rather than a market-data semantic invented here.

## Future universe / new-listing policy dependency

The long-term product target is a dynamic **Binance Spot / USDT** universe rather than a permanent hard-coded five-symbol list.

The intended discovery sequence is:

```text
Binance Spot
→ quoteAsset = USDT
→ status = TRADING
→ approved eligibility policy
→ Market Data Quality Gate
→ ORION Intelligence
```

A newly listed asset is **not** intended to be permanently excluded merely because it is new. Instead, the data-quality layer should distinguish:

```text
NEW LISTING + INSUFFICIENT HISTORY
→ insufficient evidence / no automatic trade
```

from:

```text
NEW LISTING + SUFFICIENT VALID HISTORY
→ normal analysis subject to the approved risk policy
```

No missing history may be fabricated. Interpolation, forward-fill, synthetic candles, or invented calibration evidence remain forbidden.

Any future risk policy may mark a signal as high or extreme risk, but this data-quality contract must continue to report data integrity separately from trade-risk semantics. Risk-driven trade blocking must not be confused with invalid market data.

The complete deferred product policy is recorded in:

`ORION-Project-Management/docs/ORION_FUTURE_RISK_UNIVERSE_AND_CONTROL_CENTER_POLICY.md`

## Explicit non-goals

This contract does not determine whether a market is bullish, bearish, tradable, attractive, high-score, or executable. Such semantics remain dependencies of their respective owners.
