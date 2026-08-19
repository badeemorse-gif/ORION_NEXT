# ORION Phase 2 — Core Intelligence Hardening

## Scope

`Indicator → Analysis → Profile → Score → Decision`

## Enforced boundaries

- **Indicator:** every indicator consumed by Profile Intelligence is present and finite at the latest bar; invalid derived intelligence fails closed before downstream classification.
- **Analysis:** incomplete or invalid required indicators produce `NEUTRAL` with zero strength and diagnostic warnings; directional output carrying a fail-closed warning is rejected by the cross-layer contract.
- **Profile:** the canonical ProfileResult must be tradeable, warning-free, structurally valid, and contain the required `1d`, `4h`, and `1h` intelligence timeframes before it can be considered actionable.
- **Score:** score values must be finite and bounded, and the category must agree with the numeric score. Neutral analysis cannot acquire direction from magnitude alone.
- **Decision:** actionable decisions require matching Analysis market state and Strong Score category; `WAIT` always exposes zero actionable confidence.

## Fail-closed rule

Any missing, non-finite, malformed, contradictory, incomplete, or unsupported Core Intelligence result blocks downstream actionable intelligence.

This hardening does not redesign the architecture and does not alter Opportunity, Execution, Sync/Restore, MAIN, or ALL layers.
