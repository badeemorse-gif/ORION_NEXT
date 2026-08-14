# ORION — Verification Architecture

Version: 1.1
Status: ACTIVE — Verification Layer
Owner: Developer 5 — Verification / E2E / Parity

## 1. Purpose

This document defines the verification layer for ORION_NEXT. Verification proves that existing contracts compose correctly and that failures remain observable across downstream boundaries without being converted into success.

Verification is observational: it may assert contracts, inject deterministic fixtures, and fail a gate, but it must not change production semantics to make a test pass.

## 2. Gate model

A verification gate has exactly one of these outcomes:

- PASS — the contract is proven by an executable assertion.
- FAIL — the current implementation violates an executable assertion.
- BLOCKED — the contract is not yet implemented or has no authoritative contract from which a safe assertion can be derived.

BLOCKED is never treated as PASS. A gate must never invent a threshold, formula, mapping, eligibility rule, or intelligence result.

## 3. Contract gates

### 3.1 Cross-layer compatibility

Prove the actual public/domain types at each boundary:

`MarketDataset → Validation → Indicator → Analysis → Profile → Score → Decision → ExecutionPlan → ExecutionResult → ReportResult`

Assertions verify type identity, required fields, and absence of prohibited upstream state at the boundary. In particular, `ExecutionPlan` must not carry `MarketDataset`, `AnalysisResult`, `ScoreResult`, `DecisionResult`, or `OrchestratorResult`.

### 3.2 Fail-closed propagation

An execution failure must remain observable at the pipeline boundary:

`ExecutionStatus.FAILED → PipelineItemResult.success == False → failed_stage == EXECUTION`

Failure evidence is allowed to exist downstream. Therefore verification does **not** require `ReportEngine.build_report()` to be absent or uncalled after an execution failure.

When a `ReportResult` exists for failed execution, verification requires:

- the exact failed `ExecutionResult` is retained;
- its status remains `FAILED`;
- the report carries no execution-success implication;
- report existence is never interpreted as pipeline or execution success.

The verification gate therefore distinguishes **failure propagation** from **failure-evidence reporting**. Suppressing evidence is not itself a verification requirement.

### 3.3 Decision → Execution consistency

Use the canonical Decision → ExecutionPlan bridge and the real `ExecutionEngine`.

Authoritative current mapping:

- `FAVORABLE → BUY`
- `UNFAVORABLE → SELL`
- `WAIT → HOLD`
- unknown decision → `NONE` (fail-closed execution side)

The verifier proves that BUY/SELL produce executable paper results only when the execution request is valid, while HOLD/NONE produce `SKIPPED` with no order id.

### 3.4 Opportunity eligibility

No authoritative Opportunity domain contract exists in the current production slice. Therefore this gate is **BLOCKED**, not PASS.

Until an authoritative Opportunity contract and eligibility semantics are introduced, verification must not infer eligibility from score, confidence, decision, or execution state. The first implementation of that contract must add positive and negative eligibility fixtures and a fail-closed propagation test.

### 3.5 Report integrity and failure evidence

`ReportResult` is an aggregate of canonical upstream result contracts. Its `is_complete` property is structural completeness only; it is not a success flag.

Verification must prove:

- the exact objects supplied to `ReportEngine` are retained in `ReportResult`;
- structural completeness is false when any required upstream result is absent;
- a failure-evidence report can retain `ExecutionStatus.FAILED` explicitly;
- failure evidence is never reclassified as successful execution;
- `MarketDataset` is not required by the report domain contract;
- JSON export is a serialization boundary only and does not replace the domain contract;
- the mere existence of `ReportResult` never establishes pipeline success.

### 3.6 Failure-report success rule

There is no independent `ReportResult.success` field in the canonical domain contract. Verification derives the relevant fact from the contained execution outcome:

`ReportResult.execution.status == EXECUTED` means the contained execution succeeded.

For a failure-evidence report, the authoritative state must remain:

`ReportResult.execution.status == FAILED`

A failure report may be structurally complete while still representing a failed pipeline outcome. Structural completeness and operational success are separate dimensions.

## 4. E2E gate

The E2E gate exercises the real composition graph through the canonical boundary without contacting a live exchange.

The deterministic fixture strategy is:

`fixture MarketDataset → real validation/indicator/analysis/profile/score/decision engines → ExecutionPlan → real ExecutionEngine/PaperExecutionAdapter → real ReportEngine`

External market I/O is replaced at the provider boundary only. The real downstream stages remain under test.

Required E2E cases:

1. non-executable decision reaches `HOLD/NONE → SKIPPED → report`;
2. executable decision reaches `BUY/SELL → EXECUTED → report`;
3. invalid input fails closed;
4. execution failure produces `PipelineItemResult.success == False` and `failed_stage == EXECUTION`;
5. if failure evidence is produced, the report must explicitly retain `FAILED` and must not imply success.

No E2E assertion may require that failure evidence be suppressed merely because the upstream execution failed.

## 5. Parity gate

Parity is a repository-state assertion, not a synchronization mechanism.

The CI verifier must prove:

- the checked-out commit equals `GITHUB_SHA`;
- the working tree is clean;
- there are no untracked or modified files after checkout/test execution;
- the test suite is executed from the checked-out repository only.

No verifier may silently repair, reset, pull, push, copy, or synchronize files. A parity mismatch is a hard gate failure and is owned by the synchronization/materialization layer.

## 6. Regression gate

All existing `unittest` contract tests remain part of the gate. New verification tests are additive and must not replace or weaken existing assertions.

A regression suite passes only when the process exit status is zero. Test-count totals are informational and are never used as a substitute for exit status.

## 7. Final verification policy

The final verification result is PASS only when every applicable gate is PASS and no gate is FAIL. BLOCKED gates remain explicit and prevent a claim of complete verification for that capability.

The verification layer owns evidence and gate semantics only. Production owners remain responsible for correcting production defects identified by these gates.
