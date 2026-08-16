# PHASE A — D3 TASK

Role: Opportunity Intelligence / Ranking

Baseline: `c54dc67792776da905a3efb1f667c1869c15db3d`

Objective: design an asset-relative ranking method so identical raw scores are not assumed to represent identical opportunity quality.

Scope:
- audit Opportunity inputs and eligibility context
- define relative ranking dimensions: volume expansion, volatility context, momentum, liquidity class, multi-timeframe alignment and market regime
- define percentile/rank outputs where appropriate
- specify how two assets with the same raw score can receive different contextual rankings
- keep Opportunity eligibility contracts fail-closed

Forbidden:
- no live trading
- no execution changes
- no weakening of eligibility gates
- no modification of accepted Integration branch

Definition of Done:
- contextual ranking design documented
- raw vs relative scoring relationship explicitly defined
- testable ranking/ordering criteria provided
- no existing opportunity contract weakened
- final GitHub report only