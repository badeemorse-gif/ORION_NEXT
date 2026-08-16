# PHASE A — D1 TASK

Role: Core Intelligence / Score Semantics

Baseline: `c54dc67792776da905a3efb1f667c1869c15db3d`

Objective: audit Core score/confidence semantics for cross-asset comparability. Identify which values are absolute, which are contextual, and where raw scores can mislead asset-to-asset ranking.

Scope:
- inspect Analysis/Profile/Score contracts and calculations
- document score ranges and semantic meaning
- identify normalization/calibration risks
- propose measurable relative metrics/percentiles where justified
- do not weaken existing contracts

Forbidden:
- no live trading
- no Execution changes
- no Opportunity implementation
- no modification of accepted Integration branch
- no silent redesign of Core production semantics

Definition of Done:
- written Core score/confidence interpretation matrix
- explicit absolute vs relative classification
- identified calibration risks
- proposed acceptance metrics for Phase A
- tests/analysis proving no existing engineering contract is weakened
- final GitHub report only