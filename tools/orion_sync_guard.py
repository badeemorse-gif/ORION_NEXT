"""Fail-closed entrypoint for every ORION synchronization operation.

This module is intentionally small and policy-oriented. It does not implement
materialization itself; it validates the execution boundary and then delegates
to ``orion_sync_safe.py``.

Safety contract:
* the repository root is the directory containing this ``tools`` directory;
* the configured remote must be the official ORION_NEXT repository;
* an operation mode is always explicit (no implicit DEV fallback);
* MAIN and ALL are mirror operations and are never allowed to target the
  development checkout;
* the safe controller receives a fixed repository root and remote, so ambient
  environment variables cannot redirect the operation;
* ``audit`` is read-only and checks the synchronization entrypoints for
  forbidden destructive Git commands.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SAFE_CONTROLLER = REPO_ROOT / "tools" / "orion_sync_safe.py"
CANONICAL_REMOTE_MARKER = "github.com/badeemorse-gif/ORION_NEXT"
MODES = {"dev", "main", "all", "audit"}

# These operations are forbidden in mirror entrypoints.  A mirror is allowed
# to materialize/delete files inside its own isolated destination, but it must
# never use Git operations that can mutate PROJECT_ROOT's checkout state.
FORBIDDEN_GIT_PATTERNS = (
    "git reset --hard",
    "git clean -fd",
    "git clean -fdx",
    "git checkout",
    "git switch",
    "git worktree add",
    "git worktree remove",
)

MIRROR_ENTRYPOINTS = (
    REPO_ROOT / "tools" / "orion_sync.bat",
    REPO_ROOT / "tools" / "orion_main_sync.bat",
    REPO_ROOT / "tools" / "orion_all_sync.bat",
    REPO_ROOT / "tools" / "orion_sync_safe.py",
)


def fail(message: str) -> "NoReturn":
    raise RuntimeError(message)


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    output = result.stdout.strip()
    if result.returncode:
        fail(output or f"git {' '.join(args)} failed ({result.returncode})")
    return output


def canonical_remote() -> str:
    value = run_git("remote", "get-url", "origin").replace("\\", "/").rstrip("/")
    # Accept HTTPS and SSH forms, but require the exact repository identity.
    if CANONICAL_REMOTE_MARKER not in value:
        fail(f"REFUSED: unexpected origin remote: {value}")
    return value


def validate_checkout() -> str:
    top = Path(run_git("rev-parse", "--show-toplevel")).resolve()
    if top != REPO_ROOT.resolve():
        fail(f"REFUSED: Git top-level is {top}, expected {REPO_ROOT.resolve()}")
    # A normal checkout has either a .git directory or a .git file (worktree).
    git_marker = REPO_ROOT / ".git"
    if not git_marker.exists():
        fail(f"REFUSED: not a Git checkout: {REPO_ROOT}")
    return canonical_remote()


def current_branch() -> str:
    branch = run_git("branch", "--show-current")
    if not branch or branch == "HEAD":
        fail("REFUSED: detached HEAD; synchronization requires a named branch.")
    return branch


def validate_mode(mode: str) -> None:
    if mode not in MODES:
        fail("Usage: python tools\\orion_sync_guard.py {dev|main|all|audit}")


def audit_entrypoints() -> int:
    failures: list[str] = []
    for path in MIRROR_ENTRYPOINTS:
        if not path.exists():
            failures.append(f"missing entrypoint: {path.relative_to(REPO_ROOT)}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        for pattern in FORBIDDEN_GIT_PATTERNS:
            if pattern in text:
                failures.append(f"forbidden Git command in {path.relative_to(REPO_ROOT)}: {pattern}")
    # Every public launcher must delegate to the policy guard, not directly to
    # the implementation.  This prevents an old launcher from bypassing the
    # boundary after a future tool update.
    for launcher in (
        REPO_ROOT / "tools" / "orion_sync.bat",
        REPO_ROOT / "tools" / "orion_main_sync.bat",
        REPO_ROOT / "tools" / "orion_all_sync.bat",
    ):
        if launcher.exists():
            text = launcher.read_text(encoding="utf-8", errors="replace").lower()
            if "orion_sync_guard.py" not in text:
                failures.append(f"launcher bypasses guard: {launcher.relative_to(REPO_ROOT)}")
    if failures:
        for failure in failures:
            print(f"AUDIT FAIL: {failure}", file=sys.stderr)
        return 1
    print("SYNC ARCHITECTURE AUDIT: PASS")
    print(f"Repository root: {REPO_ROOT}")
    print("Mirror invariant: MAIN/ALL are delegated through the fail-closed controller.")
    print("Forbidden Git state-changing commands: none in synchronization entrypoints.")
    return 0


def delegate(mode: str, remote: str) -> int:
    if not SAFE_CONTROLLER.is_file():
        fail(f"REFUSED: safe synchronization controller is missing: {SAFE_CONTROLLER}")
    env = os.environ.copy()
    # Pin these values so an ambient environment variable cannot redirect the
    # implementation to another checkout or remote.
    env["ORION_PROJECT_ROOT"] = str(REPO_ROOT)
    env["ORION_REMOTE"] = "origin"
    result = subprocess.run(
        [sys.executable, str(SAFE_CONTROLLER), mode],
        cwd=str(REPO_ROOT),
        env=env,
    )
    return result.returncode


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python tools\\orion_sync_guard.py {dev|main|all|audit}")
        return 2
    mode = argv[1].lower()
    try:
        validate_mode(mode)
        if mode == "audit":
            return audit_entrypoints()
        remote = validate_checkout()
        branch = current_branch()
        if mode == "dev":
            print(f"SYNC GUARD: DEV -> current branch '{branch}'")
        elif mode == "main":
            print(f"SYNC GUARD: MAIN -> isolated ORION_NEXT_MAIN; current branch '{branch}' is not changed")
        else:
            print(f"SYNC GUARD: ALL -> isolated ORION_NEXT_ALL_BRANCHES; current branch '{branch}' is not changed")
        return delegate(mode, remote)
    except Exception as exc:
        print(f"SYNC REFUSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
