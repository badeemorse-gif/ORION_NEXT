"""ORION repository parity gate.

This verifier is intentionally read-only. It never pulls, resets, copies, or
synchronizes repository state. It proves that the checked-out tree is exactly
the commit the verification job was asked to test and that verification did not
mutate the checkout.
"""

from __future__ import annotations

import os
import subprocess
import sys


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> int:
    expected = os.environ.get("GITHUB_SHA", "").strip()
    actual = _git("rev-parse", "HEAD")

    if expected and actual != expected:
        print(f"PARITY FAIL: HEAD={actual} expected={expected}")
        return 1

    status = _git("status", "--porcelain")
    if status:
        print("PARITY FAIL: working tree is not clean")
        print(status)
        return 1

    tracked = _git("ls-files", "--error-unmatch", ".")
    if not tracked:
        print("PARITY FAIL: repository has no tracked files")
        return 1

    print(f"PARITY PASS: commit={actual}; working_tree=clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
