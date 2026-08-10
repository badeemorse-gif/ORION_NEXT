"""Canonical local verification entry point for ORION/binansScanner.

This module intentionally uses only Python's standard library. It gives local
Codex/agents and developers one stable command for the project's current
verification contract.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent


def run(label: str, *args: str) -> None:
    print(f"\n=== {label} ===")
    print("$", " ".join(args))
    completed = subprocess.run(args, cwd=PROJECT_ROOT, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> int:
    run("Python syntax compilation", sys.executable, "-m", "compileall", "-q", ".")
    run(
        "Full unittest suite",
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_*.py",
        "-v",
    )
    print("\nVERIFICATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
