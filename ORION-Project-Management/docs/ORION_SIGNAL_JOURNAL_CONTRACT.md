# ORION_NEXT — Signal Journal Contract

Version: 1.0  
Status: ACTIVE — Phase A / Signal Accuracy / Score Calibration  
Owner: Developer 6 — Reporting / Auditability  
Engineering baseline: `c54dc67792776da905a3efb1f667c1869c15db3d`

## 1. Purpose

The Signal Journal is an independent observational record for later calibration and audit.

It answers three separate questions:

1. What did ORION observe at signal time?
2. What did ORION say at signal time?
3. What happened later?

The journal does not modify `ReportResult`, `ReportEngine`, `Pipeline`, API, renderer, execution, Core, Opportunity, or synchronization contracts.

## 2. Canonical boundary

```text
SignalObservation
    = signal-time observed evidence only

SignalOutcome
    = retrospective labels only

SignalJournalEntry
    = immutable pairing of the two
```

The governing rule is:

```text
Observed Evidence
≠
Retrospective Label
```

## 3. SignalObservation

`SignalObservation` is immutable and contains only data available at the signal timestamp:

- `timestamp`
- `symbol`
- `timeframe`
- `raw_score`
- `confidence`
- `decision`
- `market_regime`
- `volume`
- `relative_volume`
- `volatility`
- `relative_volatility`
- `liquidity`
- `momentum`
- `multi_timeframe_alignment`
- `reasons`

Every field is explicitly classified as `SIGNAL_TIME_OBSERVED`.

No outcome, MFE, MAE, or future price/result field belongs to `SignalObservation`.

The timestamp must be timezone-aware. This prevents an apparently identical local time from being interpreted differently across environments.

## 4. SignalOutcome

`SignalOutcome` is a separate immutable retrospective record containing only data computed after signal time:

- `outcome_1h`
- `outcome_4h`
- `outcome_24h`
- `mfe`
- `mae`
- `outcome_timestamp`
- `metric_unit`

Every outcome field is classified as `RETROSPECTIVE_LABEL`.

`MFE` and `MAE` require an explicit `metric_unit`. The journal does not invent whether a metric is percent, absolute price, quote currency, or another unit.

`outcome_timestamp`, when present, must be timezone-aware.

## 5. No future leakage

`SignalJournalEntry` may pair an observation with a retrospective outcome, but the outcome timestamp may not precede the observation timestamp.

The observation serialization contains no outcome fields. Future data therefore cannot enter the signal-time record through the canonical model.

The journal intentionally does not infer labels, calculate profitability, invent thresholds, or transform an observed signal into a retrospective judgment.

## 6. Provenance

The canonical provenance markers are:

- `SIGNAL_TIME_OBSERVED` — evidence available at signal time.
- `RETROSPECTIVE_LABEL` — data created from subsequent market evolution.

`SignalObservation.field_provenance()`, `SignalOutcome.field_provenance()`, and `SignalJournalEntry.field_provenance()` expose these classifications for audit tooling and tests.

## 7. Immutability

`SignalObservation`, `SignalOutcome`, and `SignalJournalEntry` are frozen dataclasses. A previously recorded signal observation cannot be edited after the fact to incorporate later knowledge.

Any retrospective information belongs in `SignalOutcome` and is never copied back into the observation.

## 8. Non-goals

This contract does not define:

- live trading;
- signal generation logic;
- score calibration formulas;
- ranking or threshold policy;
- prediction algorithms;
- outcome classification formulas;
- ReportResult semantics;
- Pipeline semantics;
- API/export semantics.

## 9. Audit invariant

A compliant journal record must preserve this lineage:

```text
SIGNAL TIME
    ↓
SignalObservation
    ↓
[market evolves]
    ↓
SignalOutcome
```

No reverse flow from `SignalOutcome` into `SignalObservation` is permitted.

END
