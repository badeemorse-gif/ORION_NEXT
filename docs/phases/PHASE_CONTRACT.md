# ORION Phase Contract

> Canonical governance template. Keep architecture and decision records in `ORION-Project-Management/docs/`; this document defines only phase scope and evidence.

## Phase

- Name:
- Status:
- Baseline SHA:
- Approved HEAD:
- Owner:

## Scope

Define exactly what the phase owns, what it may change, and what deliverables it must produce.

## Contracts

List the existing contracts that bind the phase. Do not redefine, weaken, or silently reinterpret them.

## Forbidden Changes

List production layers, files, contracts, integrations, and behaviors that must remain untouched.

## Definition of Done

Use binary, independently verifiable criteria:

- [ ] Required tests pass.
- [ ] E2E gates pass where applicable.
- [ ] Repository parity passes.
- [ ] Exact-source SHA checkout is proven.
- [ ] Working tree is clean.
- [ ] Required evidence artifact is uploaded.
- [ ] No forbidden-scope changes exist.

## Required Evidence

At minimum, record:

- Repository
- Workflow
- Run ID
- Trigger
- Expected SHA
- Actual checkout SHA
- Parent / baseline
- Changed paths
- Test command and result
- Working-tree status
- Artifact name / ID
- Evidence timestamp

## Integration Readiness

Record one state and any explicit dependency:

- Candidate
- Verified
- Approved
- Frozen

Any integration dependency must identify its owning phase; do not resolve cross-scope work inside this phase document.
