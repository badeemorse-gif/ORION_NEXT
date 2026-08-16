# PHASE A — D7 TASK

Role: Market Data Quality / Normalization

Baseline: `c54dc67792776da905a3efb1f667c1869c15db3d`

Objective: audit the market-data quality and comparability of the asset universe used by Phase A so misleading scores are not caused by stale, incomplete, illiquid or incomparable inputs.

Scope:
- audit freshness, completeness and timestamp consistency
- classify liquidity quality and low-liquidity cases
- define data-quality filters for the Phase A asset universe
- identify scale/normalization risks across assets
- validate required timeframes `1d + 4h + 1h`
- define explicit rejection/exclusion reasons for unusable observations

Forbidden:
- no weakening of fail-closed data contracts
- no live trading
- no modification of accepted Integration branch
- no silent changes to exchange/provider semantics

Definition of Done:
- Phase A data-quality checklist defined
- asset inclusion/exclusion criteria explicit
- comparability risks documented
- bad/stale/incomplete observations cannot contaminate calibration results
- final GitHub report only