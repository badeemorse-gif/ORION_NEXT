# MAIN Sync Architecture

## Contract

`MAIN` is an exact mirror of `origin/main`, but it is **not** the ORION_NEXT development working tree.

The Git checkout at `PROJECT_ROOT` is used only as the read/source repository for Git operations. MAIN materialization is isolated in the sibling directory:

`ORION_NEXT_MAIN/`

Only the MAIN mirror may be changed by the MAIN synchronization operation. The development working tree, including modified, untracked, and test files, must remain untouched.

## Safety invariant

After a successful MAIN sync:

- `ORION_NEXT_MAIN` matches `origin/main` exactly, excluding `.git` if present.
- `PROJECT_ROOT` is unchanged by the MAIN materialization step.
- No local development file is deleted, replaced, or converted because of MAIN synchronization.
- Missing, extra, and different paths inside the MAIN mirror are reconciled.

## Verification

`tools/orion_main_sync_verify.py` verifies the isolated MAIN mirror against `origin/main` and must reject any missing, extra, or different path.

## Why this boundary exists

The previous implementation materialized the exact MAIN snapshot directly into `PROJECT_ROOT`. That made an otherwise-correct exact mirror destructive to an active development checkout. The exact-mirror contract is retained; only its destination boundary is changed.
