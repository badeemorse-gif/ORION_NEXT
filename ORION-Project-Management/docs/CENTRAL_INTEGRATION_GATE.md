# ORION_NEXT — Central Integration Gate

## Leadership Integration Base

- Base: `main`
- Integration branch: `integration/final-current-20260814`
- Core package: `phase2/core-intelligence-hardening` @ `3b37ad94d3440463f4e440c7e46ca0380d7ce900`
- Execution package: `ops/execution-fail-closed` @ `1ae3cca91f7b58e221e7e005f7949aceb1e96b02`
- Opportunity package: `future/opportunity-intelligence-complete` @ `4975292572a8446a178a5d1afe708792082767a1`

## Integration Policy

Approved package snapshots are integrated selectively from their documented package scope. Diverged branch history is not merged blindly. `main` remains untouched until leadership approves the fully integrated result.

Local materialization is forbidden during this gate. Full verification, E2E, and parity are deferred until an integrated HEAD is established.

## Package Ownership

### Core Intelligence
Indicator → Analysis → Profile → Score → Decision. Domain result contracts remain owned by `models.*`; `core.intelligence_contract` is the single cross-layer semantic guard.

### Execution
Decision → ExecutionPlan → ExecutionRequest → Adapter → ExecutionResult → Report. Invalid numeric input, invalid quantity overrides, decision/side mismatches, and failed execution are fail-closed.

### Opportunity
MarketDataset + AnalysisResult + ProfileResult + ScoreResult → Opportunity Intelligence. Timeframe evidence is matched explicitly; unknown freshness, unavailable setup quality, ambiguity, and unsupported risk fail closed. No ranking thresholds or fabricated forecast data.

## Current Status

Package approvals are complete. Central integration is in progress and must be reviewed file-by-file before acceptance. No package is considered integrated solely because its branch exists.
