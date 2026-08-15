# ORION_NEXT Final Integration Manifest

**Status:** DRAFT — CENTRAL INTEGRATION IN PROGRESS
**Base:** `main @ 9147ea6bf6812c4afda8e0e3e9596b0460b05419`
**Integration branch:** `integration/final-release-20260815`

## Approved package sources

- Core Intelligence: `phase2/core-intelligence-hardening @ 3b37ad94d3440463f4e440c7e46ca0380d7ce900`
- Execution Fail-Closed: `ops/execution-fail-closed @ 1ae3cca91f7b58e221e7e005f7949aceb1e96b02`
- Opportunity Intelligence: `future/opportunity-intelligence-complete @ 0257a339f5f1725e424cf0cc3f83806d1faf4588`
- Final Materialization: `developer4/sync-restore-final-materialization @ a47d8ff429772debc0285a9b270d408479418977`
- Verification/E2E/Parity: `developer5/verification-e2e-parity-final @ 12d72b2a9303400472b3f13ad7d299e8c842e4f5`
- Reporting/Auditability: `developer6-reporting-auditability @ 1a276a43a9a80b335f764f46efe1abfb438a1476`
- Market Data Quality: `developer7-market-data-quality @ 289f273f6217eea4b002101caf6ef1356dae9161`

## Current integration state

The branch is being assembled by file-level publication only. No historical branch merge is permitted.

### Required ownership rules

- `binansScanner/core/orchestrator.py` — Core owner.
- `binansScanner/core/intelligence_contract.py` — Core owner.
- Execution semantics — Execution owner.
- Reporting semantics — Developer 6 owner.
- Verification logic — Developer 5 owner; it must not redefine Production semantics.
- Data Quality — Developer 7 owner; it must not redefine Indicator/Profile/Score/Decision semantics.
- Opportunity — Opportunity owner; confidence remains `TimeframeProfile.confidence` only.

## Explicit exclusions

The following are excluded unless separately approved as final integration scope:

- Legacy Sync/Restore implementation collateral.
- MAIN/ALL mirrors as development sources.
- Backups, probes, temporary handoff markers, and integration probes.
- Explosive Watchlist coupling.
- Binance/live trading behavior.
- Unapproved GUI or pipeline changes.
- Historical branch-only artifacts that are not part of an approved package.

## Current blockers

- D1 has not yet published the complete approved package set.
- Shared files such as `pipeline.py`, `test_pipeline_execution_e2e.py`, `ORION_CONTROL_INDEX.md`, and `ORION_PROJECT_STATE.md` still require final ownership/source resolution.
- Final tree parity against this manifest is not yet established.

**This document must not be changed to `APPROVED` or `BLOCKERS = 0` until the final integration tree is complete and independently reviewed by GPT.**
