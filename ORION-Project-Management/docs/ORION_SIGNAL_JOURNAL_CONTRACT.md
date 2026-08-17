# ORION_NEXT — Signal Journal Contract

Version: 1.1  
Status: ACTIVE — Phase A / Signal Accuracy / Score Calibration  
Owner: Developer 6 — Reporting / Auditability  
Engineering baseline: `c54dc67792776da905a3efb1f667c1869c15db3d`

## 1. Purpose

The Signal Journal is the independent official audit trail for experimental signals.

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

SignalJournal
    = immutable append-only collection of official entries
```

The governing rule is:

```text
Observed Evidence
≠
Retrospective Label
```

## 3. SignalObservation — official signal-time record

`SignalObservation` is immutable and contains only evidence available at the signal timestamp:

- `timestamp`
- `symbol`
- `timeframe`
- `raw_score`
- `directional_raw_strength`
- `context_score`
- `composite`
- `relative_rank`
- `relative_percentile`
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

Every observation field is explicitly classified as `SIGNAL_TIME_OBSERVED`.

`relative_rank` and `relative_percentile` are signal-time evidence only when derived from the contemporaneous experimental comparison universe at the same signal timestamp. They must not be recomputed from later observations or outcomes.

No outcome, MFE, MAE, or future result field belongs to `SignalObservation`.

The timestamp must be timezone-aware.

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

`outcome_timestamp`, when present, must be timezone-aware and must not precede the observation timestamp.

## 5. No future leakage

`SignalObservation` is structurally incapable of containing outcome fields.

`SignalJournalEntry` may pair an observation with a retrospective outcome, but the outcome timestamp cannot precede the observation timestamp.

No retrospective field is copied back into the observation. No outcome is inferred from the observation model.

## 6. Provenance

The canonical provenance markers are:

- `SIGNAL_TIME_OBSERVED` — evidence available at signal time.
- `RETROSPECTIVE_LABEL` — data created from subsequent market evolution.

`SignalObservation.field_provenance()`, `SignalOutcome.field_provenance()`, and `SignalJournalEntry.field_provenance()` expose these classifications for audit tooling and contract tests.

Observation and outcome provenance are disjoint; a field must never be classified as both.

## 7. Official journal behavior

`SignalJournal` is immutable and append-only.

Calling `record(entry)` returns a new journal containing the prior entries plus the new entry. Existing journal instances and their entries are never mutated.

This provides the canonical in-process representation of the official experimental signal trail without introducing Pipeline, Report, Execution, or live-trading integration.

## 8. Immutability

`SignalObservation`, `SignalOutcome`, `SignalJournalEntry`, and `SignalJournal` are frozen dataclasses.

A previously recorded signal observation cannot be edited after the fact to incorporate later knowledge.

## 9. Non-goals

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

## 10. Audit invariant

A compliant journal record preserves this lineage:

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
