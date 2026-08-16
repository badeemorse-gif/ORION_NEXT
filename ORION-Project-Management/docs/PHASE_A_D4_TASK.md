# PHASE A — D4 TASK

Role: Materialization / Runtime Operations

Baseline: `c54dc67792776da905a3efb1f667c1869c15db3d`

Objective: define a reproducible, clean operational observation workflow for Phase A without redesigning synchronization or restore tooling.

Scope:
- define run configuration and snapshot identity
- define startup/shutdown and observation session boundaries
- define where experiment artifacts are stored and how a run is identified
- ensure a run can be reproduced from the same accepted baseline and configuration
- preserve the existing Sync/Restore freeze and do not revive legacy tools

Forbidden:
- no changes to legacy synchronization tools
- no live trading
- no modification of accepted Integration branch
- no destructive Local operations as part of the task

Definition of Done:
- Phase A runtime/observation workflow documented
- reproducibility requirements explicit
- artifact/session identity defined
- operational safety checks documented
- no Sync/Restore collateral
- final GitHub report only