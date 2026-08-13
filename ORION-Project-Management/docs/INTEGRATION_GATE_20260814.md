# ORION_NEXT — Central Integration Gate — 2026-08-14

## Purpose

This branch is the controlled integration point for the approved Core Intelligence, Execution Fail-Closed, and Future Opportunity Intelligence packages.

## Approved package heads

- Core Intelligence: `phase2/core-intelligence-hardening` → `3b37ad94d3440463f4e440c7e46ca0380d7ce900`
- Execution: `ops/execution-fail-closed` → `1ae3cca91f7b58e221e7e005f7949aceb1e96b02`
- Opportunity Intelligence: `future/opportunity-intelligence-complete` → `4975292572a8446a178a5d1afe708792082767a1`

## Integration rules

1. This branch is created from the current `main`.
2. No local materialization is permitted during package integration.
3. No developer branch may be rewritten merely to simplify integration.
4. Conflicts are resolved centrally and only with evidence from the approved package contracts.
5. Core, Execution, and Opportunity remain separated by their declared contracts.
6. No Live Trading, Binance orders, or local final verification is part of this gate.
7. Final local materialization occurs only after the integrated GitHub state is approved.

## Final gate

Integration is not complete until:

- all approved packages are present in one coherent tree;
- cross-layer contracts are consistent;
- no package loses approved functionality;
- the integrated HEAD is identified exactly;
- Full Verification / E2E / Parity are then executed from a clean local materialization.
