# ORION Phase 2 — Core Intelligence Hardening

## Scope
`Indicator → Analysis → Profile → Score → Decision`

## Enforced boundaries
- Indicator: required/profile-critical indicators are validated and invalid derived intelligence fails closed.
- Analysis: incomplete required indicators produce `NEUTRAL` with zero strength and diagnostics; directional output with fail-closed warnings is rejected.
- Profile: canonical ProfileResult must be structurally valid, tradeable, warning-free and complete before actionable use.
- Score: score is finite/bounded and category-consistent; NEUTRAL analysis does not gain direction from magnitude alone.
- Decision: actionable decisions require semantically matching Analysis and Strong Score; WAIT exposes zero actionable confidence.

## Fail-closed rule
Any missing, non-finite, malformed, contradictory, incomplete, or unsupported Core Intelligence result blocks downstream actionable intelligence.

This hardening does not redesign the architecture and does not alter Opportunity, Execution, Sync/Restore, MAIN, or ALL layers.
