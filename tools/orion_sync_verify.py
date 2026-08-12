"""Exact GitHub -> Local parity verifier for ORION.

This verifier is intentionally project-read-only: it refreshes Git refs, then
compares the local checkout (excluding .git) byte-for-byte with the selected
GitHub branch archive. It never resets, cleans, commits, or pushes.

Usage:
    python tools/orion_sync_verify.py
    python tools/orion_sync_verify.py --branch phase2/core-intelligence-hardening
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tarfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "origin"
DEFAULT_BRANCH = "phase2/core-intelligence-hardening"


def run_git(*args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(detail or f"git {' '.join(args)} failed")
    return result.stdout


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_manifest() -> dict[str, tuple]:
    result: dict[str, tuple] = {}
    for base, dirs, files in os.walk(ROOT, topdown=True, followlinks=False):
        base_path = Path(base)
        dirs[:] = [name for name in dirs if name != ".git"]
        rel_base = base_path.relative_to(ROOT)
        if rel_base != Path("."):
            result[rel_base.as_posix()] = ("dir",)
        for name in files:
            path = base_path / name
            rel = path.relative_to(ROOT).as_posix()
            if rel == ".git" or rel.startswith(".git/"):
                continue
            if path.is_symlink():
                result[rel] = ("link", os.readlink(path))
            else:
                result[rel] = ("file", path.stat().st_size, sha256_file(path))
    return result


def remote_manifest(ref: str) -> dict[str, tuple]:
    archive = run_git("archive", "--format=tar", ref)
    result: dict[str, tuple] = {}
    with tarfile.open(fileobj=BytesIO(archive), mode="r:") as tar:
        for member in tar.getmembers():
            rel = member.name.replace("\\", "/").strip("/")
            if not rel:
                continue
            if member.isdir():
                result[rel] = ("dir",)
            elif member.issym():
                result[rel] = ("link", member.linkname)
            elif member.isfile():
                source = tar.extractfile(member)
                if source is None:
                    raise RuntimeError(f"Unable to read archive member: {rel}")
                data = source.read()
                result[rel] = ("file", len(data), hashlib.sha256(data).hexdigest())

    for rel in list(result):
        parent = Path(rel).parent
        while parent != Path("."):
            result.setdefault(parent.as_posix(), ("dir",))
            parent = parent.parent
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify exact ORION GitHub -> Local parity.")
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    branch = args.branch.strip()
    if not branch or branch.upper() == "ALL":
        print("RESULT: ERROR — a specific branch is required", file=sys.stderr)
        return 2

    try:
        if not (ROOT / ".git").is_dir():
            raise RuntimeError(f"Not a Git checkout: {ROOT}")

        remote_url = run_git("remote", "get-url", REMOTE).decode("utf-8", "replace").strip()
        if "github.com/badeemorse-gif/ORION_NEXT" not in remote_url.lower():
            raise RuntimeError(f"Unexpected origin remote: {remote_url}")

        run_git("fetch", "--prune", REMOTE, branch)
        ref = f"{REMOTE}/{branch}"
        remote_commit = run_git("rev-parse", "--verify", ref).decode().strip()
        local_commit = run_git("rev-parse", "HEAD").decode().strip()
        current_branch = run_git("branch", "--show-current").decode().strip()

        expected = remote_manifest(ref)
        actual = local_manifest()
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        different = sorted(
            rel for rel in set(expected) & set(actual) if expected[rel] != actual[rel]
        )
        status = run_git("status", "--porcelain", "--ignored").decode("utf-8", "replace").strip()

        print("ORION GITHUB -> LOCAL EXACT PARITY VERIFICATION")
        print(f"Root:            {ROOT}")
        print(f"Origin:          {remote_url}")
        print(f"Target:          {ref}")
        print(f"Current branch:  {current_branch or '<detached>'}")
        print(f"Local commit:    {local_commit}")
        print(f"GitHub commit:   {remote_commit}")
        print(f"Expected paths:  {len(expected)}")
        print(f"Local paths:     {len(actual)}")

        if local_commit != remote_commit or missing or extra or different or status:
            print("RESULT: FAILED")
            if local_commit != remote_commit:
                print("Commit mismatch: local checkout is not at the GitHub target commit.")
            if missing:
                print("Missing:")
                for rel in missing[:30]:
                    print(f"  {rel}")
            if extra:
                print("Extra:")
                for rel in extra[:30]:
                    print(f"  {rel}")
            if different:
                print("Different:")
                for rel in different[:30]:
                    print(f"  {rel}")
            if status:
                print("Git status (including ignored):")
                print(status)
            return 1

        print("RESULT: EXACT MATCH")
        print(".git is intentionally excluded from the parity contract.")
        return 0
    except Exception as exc:
        print(f"RESULT: ERROR — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
