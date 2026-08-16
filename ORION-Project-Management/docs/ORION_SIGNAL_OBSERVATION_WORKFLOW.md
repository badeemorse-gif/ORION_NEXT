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

A run configuration is a canonical JSON document. It MUST include:

- `baseline_commit`: full 40-character Git commit SHA.
- `configuration`: explicit experiment parameters; no hidden defaults.
- `universe`: explicit list/identity of symbols or instruments under observation.
- `start_at` and `stop_at`: UTC timestamps delimiting the observation window.
- `observer_version`: workflow/tool version.

The configuration file is copied byte-for-byte into the session artifact directory before observation starts.

## 2. Snapshot Identity

Snapshot identity is the exact baseline commit SHA plus the explicit universe identity. A branch name, mutable tag, local snapshot, or untracked local directory is not an acceptable substitute.

The session records:

```text
baseline_commit
universe_id
universe_sha256
```

## 3. Start / Stop Boundaries

`START` is the moment the session manifest is created and persisted.

`STOP` is an explicit command that records `stopped_at_utc` and changes the session state from `RUNNING` to `STOPPED`.

Observations outside the recorded interval are not part of the session.

The workflow refuses to stop an unknown session and refuses to start a second session using an existing session directory.

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
artifacts/
└── signal-observations/
    └── <experiment-session-id>/
        ├── session.json
        ├── run_config.json
        ├── snapshot_identity.json
        ├── configuration_fingerprint.json
        └── observations.jsonl
```

The workflow never writes these artifacts into `binansScanner/` or any production source directory.

## 6. Configuration Fingerprint

`configuration_fingerprint` is SHA-256 over canonical JSON serialization of the immutable run configuration.

Canonicalization rules:

- UTF-8 JSON.
- Objects sorted by key.
- No insignificant whitespace.
- Arrays retain declared order.

Identical configuration input therefore produces the same fingerprint.

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

## 8. Replaying the Same Experiment

To replay an experiment exactly:

1. Use the recorded `baseline_commit`.
2. Use the recorded `run_config.json` unchanged.
3. Verify the recorded `configuration_fingerprint` matches the configuration file.
4. Use the same `universe_id` and universe content.
5. Use a newly generated Session ID for the replay; never reuse the previous Session ID.
6. Compare observations by their recorded UTC timestamps and payloads.

A replay is not considered the same session; it is a new session with the same immutable inputs.

## 9. Operational Safety Checklist

Before START:

- Confirm baseline is the intended full commit SHA.
- Confirm the universe is explicit and immutable for the run.
- Confirm configuration has no hidden defaults.
- Confirm output target is under the observation artifact root and outside production source trees.
- Confirm no live-trading credentials or order endpoints are enabled.
- Confirm start/stop timestamps are UTC.

During RUNNING:

- Do not modify run configuration.
- Do not replace the baseline identity.
- Do not write production-source artifacts.
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
