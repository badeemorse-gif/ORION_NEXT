# ORION — Final Materialization Contract

الإصدار: 1.0  
الحالة: ACTIVE  
المالك: Developer 4 — Sync / Restore / Final Materialization

## Contract

Final Materialization is a one-way, commit-pinned handoff from GitHub into an isolated local target.

```text
GitHub exact commit
→ fetch exact commit object
→ archive exact commit
→ clean isolated staging
→ manifest + SHA-256 parity
→ atomic install
→ target parity
```

## Source authority

The source is a full 40-character commit SHA fetched from the configured `origin`, which must resolve to the official `badeemorse-gif/ORION_NEXT` GitHub repository.

A branch name, local working-tree state, copied snapshot, or untracked local directory is not a final source authority.

## Target isolation

The target:

- must be outside `ORION_NEXT`;
- must not be the repository parent;
- must not be inside a Git checkout;
- must not traverse a symlink/reparse-point boundary;
- must never be a branch's sibling target belonging to another branch.

During development, `ORION_NEXT` is never a mirror destination.

## Atomic install

The implementation creates a unique staging directory first. The archive is extracted and verified there. Only after staging parity succeeds may an existing target be moved to a temporary backup and the staging directory be promoted.

A second parity check is mandatory after promotion. Failure restores the previous target.

## Parity

The source and target manifests must match exactly by:

- relative path;
- object type (`dir`, `file`, `link`);
- file size;
- SHA-256 content digest;
- symlink target where applicable.

Missing, extra, or different entries are failures.

## Safety boundaries

The implementation does not perform:

- `checkout`;
- `switch`;
- `reset --hard`;
- `clean -fdx`;
- merge/rebase;
- writes to the development working tree;
- cross-branch target reuse;
- partial target updates before staging parity.

## Legacy compatibility

Existing sync/restore tools remain available as `LEGACY / FROZEN` unless leadership explicitly changes their status. They are not an authorization to use the old daily synchronization model.

## Acceptance output

A successful finalization must report:

```text
SOURCE: GitHub exact commit <SHA>
PARITY: EXACT MATCH
RESULT: FINAL MATERIALIZATION SUCCESS
```

No success state is inferred from file counts, timestamps, or a branch label alone.
