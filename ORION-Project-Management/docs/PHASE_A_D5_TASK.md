# PHASE A — D5 TASK

Role: Verification / E2E / Experiment Harness

Baseline: `c54dc67792776da905a3efb1f667c1869c15db3d`

Objective: build the repeatable evidence harness for Phase A so signal observations can be collected and evaluated without changing approved production contracts.

Scope:
- define repeatable experiment fixtures and observation runs
- validate observation schema and timestamps
- support replay/comparison of signals across assets and timeframes
- create checks for forward 1h/4h/24h outcomes, MFE and MAE calculations
- verify no live execution is invoked
- verify raw/relative/calibration fields are preserved correctly

Forbidden:
- no Production contract changes
- no live trading
- no changes to accepted Integration branch
- no bypassing safety/quality gates

Definition of Done:
- repeatable Phase A harness exists or its required test contract is documented
- observation integrity verified
- forward-outcome calculations testable
- paper/live separation verified
- final GitHub report only