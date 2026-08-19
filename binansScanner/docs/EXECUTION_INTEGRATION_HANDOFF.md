# ORION Execution Integration Handoff

## Status

**EXECUTION INTEGRATION HANDOFF = COMPLETE**

This handoff records the Execution boundary for Central Integration.

## Exact lineage

- Repository: `badeemorse-gif/ORION_NEXT`
- Branch: `ops/execution-fail-closed`
- HEAD before handoff commit: `f384f95f84bc4368dac2f031a782fdb5059a5524`
- Scope: Execution / Operational Readiness only

No Core Intelligence, Opportunity Intelligence, Sync/Restore, or `main` changes are part of this handoff.

## Canonical execution path

```text
DecisionResult
    ↓
ExecutionPlanBuilder
    ↓
ExecutionPlan
    ↓
ExecutionEngine
    ↓
ExecutionRequest
    ↓
PaperExecutionAdapter
    ↓
ExecutionResult
    ↓
ReportEngine
```

## Contracts

### Decision → ExecutionPlan

`ExecutionPlanBuilder` translates the canonical decision names as follows:

- `FAVORABLE` → `ExecutionSide.BUY`
- `UNFAVORABLE` → `ExecutionSide.SELL`
- `WAIT` → `ExecutionSide.HOLD`

The plan carries the decision name as metadata. Unknown decision names are not accepted as executable decisions by `ExecutionEngine`.

### ExecutionPlan → ExecutionRequest

`ExecutionEngine` accepts only `ExecutionPlan`. For executable BUY/SELL plans it creates an `ExecutionRequest` using the plan symbol, side, price, effective quantity, and confidence.

A quantity override is validated before the HOLD/NONE shortcut. Any override that is non-finite or `<= 0` is rejected; there is no fallback from an invalid override to `plan.quantity`.

### Adapter boundary

`PaperExecutionAdapter` validates request type/symbol, canonical execution side, finite price/quantity/confidence, confidence range `0..100`, positive price/quantity for BUY/SELL, and zero quantity for HOLD/NONE. Invalid numeric values, including NaN and infinities, therefore fail closed.

### ExecutionResult

Execution failures remain `ExecutionStatus.FAILED` and are not converted to successful execution states. `ExecutionEngine` records failed results and returns them to the caller.

### Execution → Report

`Pipeline` stops at the EXECUTION stage when `ExecutionResult.status == FAILED` and does not invoke the report boundary as a success path.

`ReportEngine.build_report` independently rejects a supplied `ExecutionResult` whose status is `FAILED`. `ReportEngine.export_dict` also rejects failed execution results, providing a second boundary against successful report generation.

## Downstream consumers

- `core.pipeline.Pipeline`: consumes `ExecutionEngine` output and gates the Report stage on execution success/non-failure.
- `engines.report_engine.ReportEngine`: consumes `ExecutionResult` as the execution component of `ReportResult` and enforces failed-execution rejection at report construction/export.
- `core.dependency_container.DependencyContainer`: constructs the canonical `PaperExecutionAdapter`, `ExecutionEngine`, `ReportEngine`, and `Pipeline` wiring.
- `core.orchestrator.Orchestrator`: produces the upstream `ExecutionPlan` consumed by the pipeline.

## Integration assumptions

1. The upstream Decision contract exposes `decision` as a string with the canonical values `FAVORABLE`, `UNFAVORABLE`, or `WAIT`, plus numeric confidence and reasons.
2. Execution receives a canonical `ExecutionPlan`; it does not consume `MarketDataset`, `AnalysisResult`, `ProfileResult`, or `ScoreResult` directly.
3. BUY/SELL plans carry a positive market price and positive plan quantity. Invalid values are rejected rather than normalized into tradable values.
4. HOLD is represented by `ExecutionSide.HOLD` with zero plan quantity and `WAIT` decision metadata.
5. `PaperExecutionAdapter` is the execution adapter currently wired by the composition root.
6. Report generation must treat `ExecutionStatus.FAILED` as a hard failure even when ReportEngine is invoked directly.

## Integration findings / blockers

**Execution blocker: none identified.**

The reviewed Execution boundaries are internally aligned with the current Decision contract and downstream Pipeline/Report contracts.

No defect was identified that requires changing Core Intelligence. Any future mismatch discovered in the upstream Core contract should be treated as a dependency rather than repaired inside Execution.

## Contract-test coverage on this lineage

The branch already contains contract coverage for:

- non-finite execution request values
- invalid execution validation
- HOLD with NaN quantity override
- HOLD with positive/negative infinity quantity override
- HOLD with zero/negative quantity override
- valid HOLD without override preserving SKIPPED behavior
- valid BUY with quantity override preserving execution behavior
- Decision/Execution bridge behavior
- real composition-root execution
- execution failure stopping before Report
- canonical ExecutionPlan boundary

## Handoff boundary

Central Integration may consume this branch as the Execution lineage. This document is the single Execution Integration Handoff record for the branch.
