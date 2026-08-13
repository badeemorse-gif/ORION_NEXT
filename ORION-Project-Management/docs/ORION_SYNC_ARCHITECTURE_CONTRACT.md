# ORION Synchronization Architecture Contract

## Status

**SYNC-ARCH-001 — Synchronization Safety & Branch Isolation**

This document defines the only supported boundaries for synchronization and
restore operations. It exists to prevent a mirror operation from ever becoming
an accidental development-checkout mutation.

## Canonical topology

```text
GitHub / origin
   |
   +-- main ------------------> ORION_NEXT_MAIN
   |
   +-- <branch> ---------------> ORION_NEXT_ALL_BRANCHES/__branches__/<branch>
   |
   +-- current checked-out ----> PROJECT_ROOT (development checkout)
```

`PROJECT_ROOT` is the Git repository checkout used by developers. It is a Git
source for mirror reads, and it is the only location used by DEV sync to commit
and push the **currently checked-out branch**.

`ORION_NEXT_MAIN` and `ORION_NEXT_ALL_BRANCHES` are isolated mirror
Destinations. Mirror operations must never materialize files into
`PROJECT_ROOT`.

## Four explicit operations

| Operation | Source | Writable destination | Changes checkout state? |
|---|---|---|---|
| `dev` | current `PROJECT_ROOT` | current Git repository | Yes, only by commit/push |
| `main` | `origin/main` archive | `ORION_NEXT_MAIN` | No |
| `all` | `origin/<branch>` archives | `ORION_NEXT_ALL_BRANCHES/__branches__/<branch>` | No |
| `audit` | repository/tooling metadata | none | No |

### DEV

`dev` is the only synchronization operation that is allowed to commit and
push. It must discover a named current branch and push that exact branch. It
must never infer `main` as a fallback branch.

### MAIN

`main` means **exact mirror of `origin/main` into `ORION_NEXT_MAIN`**. The
active development checkout remains untouched, including modified, untracked,
and test files.

### ALL

`all` means **exact isolated mirrors of every fetched remote branch**. Every
branch gets its own destination under `ORION_NEXT_ALL_BRANCHES/__branches__`.
A branch mirror may delete or replace paths only inside its own destination.

### AUDIT

`audit` is read-only. It checks that public launchers delegate through the
fail-closed guard and that synchronization entrypoints do not contain checkout-
state-changing Git commands.

## Hard safety invariants

1. A mirror destination must not equal `PROJECT_ROOT`.
2. A mirror destination must not be inside `PROJECT_ROOT`.
3. A mirror operation must not call `checkout`, `switch`, `reset`, `clean`, or
   `worktree add/remove`.
4. The repository root is derived from the synchronization tool itself and is
   verified with `git rev-parse --show-toplevel`.
5. The official `origin` remote must identify `badeemorse-gif/ORION_NEXT`.
6. Ambient `ORION_PROJECT_ROOT` and `ORION_REMOTE` environment variables are
   pinned by the public guard before the implementation is invoked.
7. No launcher has an implicit default operation.
8. A mirror is not successful until its complete physical manifest matches the
   Git archive manifest: `Missing = 0`, `Extra = 0`, `Different = 0`.
9. A failed or interrupted materialization must not be reported as success.
10. No future developer may add a second synchronization implementation
    without adding it to the audit contract and contract tests.

## Why this is the fix

The historical failure was not that Git branches were intrinsically unsafe. It
was that multiple synchronization concepts shared similar names while having
different write permissions. An exact mirror can be perfectly correct and
still be destructive if its destination is the active development checkout.

The architecture therefore separates **source**, **operation**, and
**destination**. The fail-closed guard is the single public entry boundary;
the safe controller is the single implementation boundary.

## Required verification

From the repository root:

```text
python tools\orion_sync_guard.py audit
python -m unittest tools.test_orion_sync_guard_contract -v
python -m unittest tools.test_orion_sync_safe -v
```

The first command is read-only. The tests are also read-only with respect to
the repository; temporary fixtures are created under the operating system's
temporary directory only.

## Explicit non-goals

This contract does **not** redesign Core Intelligence, Pipeline, Opportunity,
Execution, Profile, Indicator, Score, Decision, or Trading logic. It also does
not require Git worktrees. Worktrees remain an implementation option for a
future isolated workspace design, but they are not necessary for the current
mirror safety contract.
