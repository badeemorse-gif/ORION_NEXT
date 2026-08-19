"""Fail-closed final materialization from an exact GitHub commit.

This is the only non-legacy path intended for the final local handoff:

    GitHub exact commit -> isolated staging -> parity verification -> atomic install

Hard invariants:
* the development checkout is never a materialization destination;
* the target must be outside PROJECT_ROOT and any Git checkout ancestor;
* the source is an exact commit object fetched from origin;
* no checkout, reset, clean, pull, merge, or working-tree write is performed;
* the destination is replaced only after a complete staged snapshot passes parity;
* file/directory/symlink collisions are rejected or safely replaced in staging;
* the final verification compares every path and SHA-256 content digest.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn
from urllib.parse import urlparse

EXPECTED_REMOTE = "github.com/badeemorse-gif/ORION_NEXT"
DEFAULT_REMOTE = "origin"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT.parent / "ORION_NEXT_FINAL"

class MaterializationError(RuntimeError):
    """Raised for any refused or failed finalization operation."""

@dataclass(frozen=True)
class MaterializationResult:
    commit: str
    target: Path
    paths: int

def fail(message: str) -> NoReturn:
    raise MaterializationError(message)

def run_git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace", check=False)
    output = result.stdout.strip()
    if result.returncode:
        fail(output or f"git {' '.join(args)} failed ({result.returncode})")
    return output

def normalize_remote(url: str) -> str:
    value = url.strip().replace("\\", "/")
    if value.startswith("git@") and ":" in value:
        host, path = value.split(":", 1)
        value = f"ssh://{host[4:]}/{path}"
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return f"{host}{path}".lower().strip("/")

def require_source_repository(remote: str) -> None:
    if not ROOT.is_dir() or not (ROOT / ".git").is_dir():
        fail(f"Source checkout is not a Git repository: {ROOT}")
    actual_root = Path(run_git("rev-parse", "--show-toplevel")).resolve()
    if actual_root != ROOT.resolve():
        fail(f"Repository root mismatch: {actual_root}")
    origin = run_git("remote", "get-url", remote)
    if normalize_remote(origin) != EXPECTED_REMOTE.lower():
        fail(f"Unexpected {remote} remote: {origin}")

def validate_commit(commit: str) -> str:
    value = commit.strip().lower()
    if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
        fail("Exact materialization requires a 40-character commit SHA.")
    return value

def fetch_exact_commit(remote: str, commit: str) -> str:
    commit = validate_commit(commit)
    run_git("fetch", "--no-tags", remote, commit)
    try:
        resolved = run_git("rev-parse", f"{commit}^{{commit}}")
    except MaterializationError:
        fail(f"Commit is not available from {remote}: {commit}")
    if resolved != commit:
        fail(f"Commit resolution mismatch: requested={commit}, resolved={resolved}")
    return resolved

def _is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return bool(getattr(path.stat(), "st_file_attributes", 0) & 0x400)
    except OSError:
        return False

def _existing_ancestors(path: Path):
    current = path
    while current != current.parent:
        if current.exists() or current.is_symlink():
            yield current
        current = current.parent

def ensure_external_target(target: Path) -> Path:
    raw = target.expanduser().absolute()
    for ancestor in _existing_ancestors(raw):
        if _is_reparse(ancestor):
            fail(f"REFUSED: reparse-point/symlink target boundary: {ancestor}")
        if (ancestor / ".git").is_dir():
            fail(f"REFUSED: target is inside a Git checkout: {ancestor}")
    target = raw.resolve()
    project = ROOT.resolve()
    if target == project or project in target.parents:
        fail(f"REFUSED: target is inside PROJECT_ROOT: {target}")
    if target == project.parent:
        fail(f"REFUSED: target cannot be the ORION parent: {target}")
    if target.name == ".git" or ".git" in target.parts:
        fail(f"REFUSED: target path contains .git: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if (target.parent / ".git").is_dir():
        fail(f"REFUSED: target parent is a Git checkout: {target.parent}")
    return target

def reject_reparse_boundary(target: Path) -> None:
    for ancestor in _existing_ancestors(target):
        if _is_reparse(ancestor):
            fail(f"REFUSED: reparse-point/symlink target boundary: {ancestor}")

def snapshot_manifest(data: bytes) -> dict[str, tuple]:
    result: dict[str, tuple] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
        for member in tar.getmembers():
            rel = member.name.replace("\\", "/").strip("/")
            if not rel or rel == ".git" or rel.startswith(".git/"):
                fail(f"Unsupported archive path: {member.name!r}")
            if rel.startswith("../") or "/../" in rel or rel == ".." or "/./" in rel:
                fail(f"Unsafe archive path: {member.name!r}")
            if member.isdir():
                result[rel] = ("dir",)
            elif member.issym():
                result[rel] = ("link", member.linkname)
            elif member.isfile():
                source = tar.extractfile(member)
                if source is None:
                    fail(f"Cannot read archive member: {rel}")
                payload = source.read()
                result[rel] = ("file", len(payload), hashlib.sha256(payload).hexdigest())
            else:
                fail(f"Unsupported archive member type: {rel}")
    for rel in list(result):
        parent = Path(rel).parent
        while parent != Path("."):
            existing = result.get(parent.as_posix())
            if existing is not None and existing != ("dir",):
                fail(f"Archive file/directory collision at {parent.as_posix()}")
            result.setdefault(parent.as_posix(), ("dir",))
            parent = parent.parent
    return result

def archive_manifest(commit: str) -> tuple[bytes, dict[str, tuple]]:
    result = subprocess.run(["git", "archive", "--format=tar", commit], cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        fail(result.stderr.decode("utf-8", "replace").strip() or "git archive failed")
    data = result.stdout
    return data, snapshot_manifest(data)

def local_manifest(root: Path) -> dict[str, tuple]:
    result: dict[str, tuple] = {}
    if not root.is_dir() or root.is_symlink():
        return result
    for base, dirs, files in os.walk(root, topdown=True, followlinks=False):
        base_path = Path(base)
        dirs[:] = [name for name in dirs if name != ".git"]
        rel_base = base_path.relative_to(root)
        if rel_base != Path("."):
            result[rel_base.as_posix()] = ("dir",)
        for name in list(dirs):
            path = base_path / name
            if path.is_symlink():
                rel = path.relative_to(root).as_posix()
                result[rel] = ("link", os.readlink(path))
                dirs.remove(name)
        for name in files:
            path = base_path / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                result[rel] = ("link", os.readlink(path))
            else:
                digest = hashlib.sha256()
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                result[rel] = ("file", path.stat().st_size, digest.hexdigest())
    return result

def verify_snapshot(root: Path, expected: dict[str, tuple], label: str) -> None:
    actual = local_manifest(root)
    if actual == expected:
        return
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    different = sorted(k for k in set(expected) & set(actual) if expected[k] != actual[k])
    details = []
    if missing: details.append("missing=" + ",".join(missing[:12]))
    if extra: details.append("extra=" + ",".join(extra[:12]))
    if different: details.append("different=" + ",".join(different[:12]))
    fail(f"Parity verification failed for {label}: {'; '.join(details)}")

def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file(): path.unlink()
    elif path.is_dir(): shutil.rmtree(path)

def extract_clean(data: bytes, destination: Path) -> None:
    destination.mkdir(parents=False)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
        for member in tar.getmembers():
            rel = member.name.replace("\\", "/").strip("/")
            if not rel or rel == ".git" or rel.startswith(".git/"): continue
            target = (destination / Path(rel)).resolve()
            if target != destination.resolve() and destination.resolve() not in target.parents: fail(f"Archive extraction escaped staging directory: {rel}")
            if member.isdir():
                if target.exists() and not target.is_dir(): remove_path(target)
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() or target.is_symlink(): remove_path(target)
                source = tar.extractfile(member)
                if source is None: fail(f"Cannot extract archive member: {rel}")
                with target.open("wb") as handle: shutil.copyfileobj(source, handle)
                os.chmod(target, member.mode & 0o7777)
            elif member.issym():
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() or target.is_symlink(): remove_path(target)
                os.symlink(member.linkname, target)
            else: fail(f"Unsupported archive member type during extraction: {rel}")

def materialize(commit: str, target: Path, remote: str = DEFAULT_REMOTE) -> MaterializationResult:
    require_source_repository(remote)
    target = ensure_external_target(target)
    reject_reparse_boundary(target)
    commit = fetch_exact_commit(remote, commit)
    data, expected = archive_manifest(commit)
    staging = target.parent / f".{target.name}.orion-final-staging-{uuid.uuid4().hex}"
    backup = target.parent / f".{target.name}.orion-final-backup-{uuid.uuid4().hex}"
    try:
        extract_clean(data, staging)
        verify_snapshot(staging, expected, f"staging/{commit}")
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_dir(): fail(f"REFUSED: target is not a directory: {target}")
            target.rename(backup)
        staging.rename(target)
        try:
            verify_snapshot(target, expected, f"target/{commit}")
        except Exception:
            if target.exists(): remove_path(target)
            if backup.exists(): backup.rename(target)
            raise
        if backup.exists(): remove_path(backup)
    except Exception:
        if staging.exists(): remove_path(staging)
        if backup.exists() and not target.exists(): backup.rename(target)
        raise
    return MaterializationResult(commit=commit, target=target, paths=len(expected))

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize an exact GitHub commit into an isolated target.")
    parser.add_argument("--commit", required=True, help="Full 40-character Git commit SHA from GitHub.")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET, help="External final materialization directory.")
    parser.add_argument("--remote", default=DEFAULT_REMOTE, help="Git remote; must resolve to the ORION_NEXT GitHub repository.")
    return parser

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = materialize(args.commit, args.target, args.remote)
        print("ORION FINAL MATERIALIZATION")
        print(f"SOURCE: GitHub exact commit {result.commit}")
        print(f"TARGET: {result.target}")
        print(f"PATHS:  {result.paths}")
        print("PARITY: EXACT MATCH")
        print("RESULT: FINAL MATERIALIZATION SUCCESS")
        return 0
    except MaterializationError as exc:
        print(f"RESULT: REFUSED/FAILED — {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"RESULT: ERROR — {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__": raise SystemExit(main())
