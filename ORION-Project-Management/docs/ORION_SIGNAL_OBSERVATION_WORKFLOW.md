# ORION — Signal Observation Workflow

**Version:** 1.0  
**Status:** ACTIVE — PHASE A / SIGNAL ACCURACY & SCORE CALIBRATION  
**Baseline under experiment:** `c54dc67792776da905a3efb1f667c1869c15db3d`

## Purpose

Provide a reproducible, non-trading observation session that binds every observed Signal to:

```text
Baseline X
Configuration Y
Universe Z
Timestamp T
Experiment Session ID
Artifact Set
Configuration Fingerprint
```

This workflow observes already-approved behavior. It does not change Signal, Score, Decision, Execution, Sync, Restore, or Integration semantics.

## 1. Run Configuration

A run configuration is a canonical JSON object supplied by the operator. It MUST contain only explicit experiment parameters; hidden defaults are prohibited.

The session controller records:

- `baseline_commit`: full 40-character Git commit SHA.
- `configuration`: explicit experiment parameters.
- `universe_id`: explicit or deterministically derived identity.
- `universe_sha256`: SHA-256 of the exact universe input bytes.
- `observer_version`: workflow/tool version.

The original `configuration_input.json` and `universe_input.json` bytes are preserved in the session artifact for replay.

## 2. Snapshot Identity

Snapshot identity is the exact baseline commit SHA plus the explicit universe identity. A branch name, mutable tag, local snapshot, or untracked local directory is not an acceptable substitute.

The session records:

```text
baseline_commit
universe_id
universe_sha256
```

## 3. Start / Stop Boundaries

`START` is the moment the session manifest is created and persisted. The session receives `started_at_utc`.

`STOP` is an explicit command that records `stopped_at_utc` and changes the session state from `RUNNING` to `STOPPED`.

Observations are accepted only while the session is `RUNNING`. An observation recorded after `STOP` is refused.

## 4. Experiment Session ID

Session IDs are generated once at start and remain immutable.

Format:

```text
EXP-YYYYMMDDTHHMMSSZ-<12 hex chars>
```

The ID is the primary artifact key and appears in every observation record.

## 5. Artifact Location

Artifacts are isolated from source development trees. Default layout:

```text
ORION_OBSERVATION_ARTIFACTS/
└── signal-observations/
    └── <experiment-session-id>/
        ├── session.json
        ├── run_config.json
        ├── configuration_input.json
        ├── universe_input.json
        ├── snapshot_identity.json
        ├── configuration_fingerprint.json
        └── observations.jsonl
```

The workflow refuses an artifact root located inside `ORION_NEXT` or another Git checkout boundary. It never writes these artifacts into production source directories.

## 6. Configuration Fingerprint

`configuration_fingerprint` is SHA-256 over canonical JSON serialization of the configuration object only.

Canonicalization rules:

- UTF-8 JSON.
- Objects sorted by key.
- No insignificant whitespace.
- Arrays retain declared order.

Identical configuration content therefore produces the same fingerprint, independent of insignificant source formatting.

## 7. Observation Record

Every recorded Signal observation MUST contain:

```json
{
  "session_id": "EXP-...",
  "baseline_commit": "<40-char SHA>",
  "configuration_fingerprint": "<sha256>",
  "universe_id": "<id>",
  "observed_at_utc": "<ISO-8601 UTC>",
  "signal": "<observed signal identifier/value>"
}
```

Additional fields are permitted only as experiment payload; the identity fields above are mandatory and immutable.

## 8. Operational Commands

Create a session:

```text
python tools/orion_signal_observe.py start \
  --baseline <40-char-commit-sha> \
  --config <configuration.json> \
  --universe-file <universe.json>
```

Record a Signal:

```text
python tools/orion_signal_observe.py record \
  --session-id <EXP-...> \
  --signal BUY \
  --observed-at 2026-08-17T00:05:00Z
```

Close the session:

```text
python tools/orion_signal_observe.py stop \
  --session-id <EXP-...>
```

## 9. Replaying the Same Experiment

A stopped session can be replayed without reusing its Session ID:

```text
python tools/orion_signal_observe.py replay \
  --session-id <stopped-EXP-...>
```

Replay behavior is deterministic with respect to identity inputs:

1. Reuse the recorded `baseline_commit`.
2. Reuse the preserved `configuration_input.json` byte-for-byte.
3. Reuse the preserved `universe_input.json` byte-for-byte.
4. Preserve the same `universe_id` and configuration fingerprint.
5. Generate a new Session ID and new UTC boundaries.
6. Compare the new observations with the historical session using the two session IDs and timestamps.

A replay is a new experiment session, never an overwrite of historical artifacts.

## 10. Operational Safety Checklist

Before START:

- Confirm baseline is the intended full commit SHA.
- Confirm the universe is explicit and immutable for the run.
- Confirm configuration has no hidden defaults.
- Confirm output target is outside production source trees and outside Git checkout boundaries.
- Confirm live-trading credentials and order endpoints are disabled or unavailable.
- Confirm all timestamps are UTC.

During RUNNING:

- Do not modify run configuration or baseline identity.
- Do not write artifacts into production source directories.
- Do not submit live orders.
- Append observations only to the active session artifact.

At STOP:

- Record the stop timestamp.
- Verify required identity artifacts remain readable.
- Do not mutate historical observations.

## Non-goals

This workflow does not:

- redesign Sync or Restore;
- use legacy synchronization tools;
- change accepted Integration;
- perform live trading;
- calibrate or alter production thresholds, formulas, mappings, or scoring semantics.
