"""Independent exact-parity verifier for ORION MAIN.

This command is intentionally read-only: it fetches origin/main, builds the
same Git archive snapshot used by the MAIN restore path, computes a local
manifest excluding only .git, and refuses success on any missing, extra, or
content-different path.

Usage:
    python tools/orion_main_sync_verify.py
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "origin"
REF = "origin/main"


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


def archive_manifest() -> dict[str, tuple]:
    archive = run_git("archive", "--format=tar", REF)
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
    # git archive may omit explicit parent directory entries; add them so the
    # comparison is structural as well as byte-for-byte.
    for rel in list(result):
        parent = Path(rel).parent
        while parent != Path("."):
            result.setdefault(parent.as_posix(), ("dir",))
            parent = parent.parent
    return result


def main() -> int:
    try:
        if not (ROOT / ".git").is_dir():
            raise RuntimeError(f"Not a Git checkout: {ROOT}")
        run_git("fetch", "--prune", REMOTE, "main")
        remote_commit = run_git("rev-parse", REF).decode().strip()
        expected = archive_manifest()
        actual = local_manifest()
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        different = sorted(
            rel for rel in set(expected) & set(actual) if expected[rel] != actual[rel]
        )
        print("ORION MAIN EXACT PARITY VERIFICATION")
        print(f"Target: {REF}")
        print(f"Commit: {remote_commit}")
        print(f"Expected paths: {len(expected)}")
        print(f"Local paths:    {len(actual)}")
        if missing or extra or different:
            print("RESULT: FAILED")
            if missing:
                print("Missing:")
                for rel in missing[:20]:
                    print(f"  {rel}")
            if extra:
                print("Extra:")
                for rel in extra[:20]:
                    print(f"  {rel}")
            if different:
                print("Different:")
                for rel in different[:20]:
                    print(f"  {rel}")
            return 1
        print("RESULT: EXACT MATCH")
        print(".git is intentionally excluded from the parity contract.")
        return 0
    except Exception as exc:
        print(f"RESULT: ERROR — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
