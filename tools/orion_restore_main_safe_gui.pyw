"""ORION MAIN Restore safety wrapper.

Keeps the existing MAIN+ALL GUI and ALL implementation unchanged, but replaces
MAIN materialization with an isolated exact mirror at ORION_NEXT_MAIN so the
official development checkout is never overwritten or cleaned by MAIN sync.
"""
from __future__ import annotations

import hashlib
import io
import os
import runpy
import sys
import tarfile
from pathlib import Path

MAIN_GUI = Path(__file__).with_name("orion_restore_main_gui.pyw")
MOD = runpy.run_path(str(MAIN_GUI))
CORE = MOD["CORE"]
PROJECT_ROOT = os.path.abspath(MOD["PROJECT_ROOT"])
REMOTE = MOD["REMOTE"]
MAIN_ROOT = str(Path(PROJECT_ROOT).parent / "ORION_NEXT_MAIN")

Manifest = MOD["Manifest"]
BranchStats = MOD["BranchStats"]
RestoreError = MOD["RestoreError"]
run_git = MOD["run_git"]
safe_target = MOD["safe_target"]
remove_any = MOD["remove_any"]
archive_manifest = MOD["archive_manifest"]
assert_no_gitlinks = MOD["assert_no_gitlinks"]


def _manifest(root: str) -> Manifest:
    local = CORE["local_manifest"](root)
    return {k: v for k, v in local.items() if k != ".git" and not k.startswith(".git/")}


def _ensure_parent(path: str, root: str) -> None:
    root_abs = os.path.abspath(root)
    parent = os.path.abspath(os.path.dirname(path))
    while parent != root_abs:
        if os.path.commonpath([root_abs, parent]) != root_abs:
            raise RestoreError(f"Unsafe MAIN destination parent: {path}")
        if os.path.lexists(parent) and (os.path.islink(parent) or not os.path.isdir(parent)):
            remove_any(parent)
        os.makedirs(parent, exist_ok=True)
        parent = os.path.dirname(parent)


def _write_atomic(path: str, data: bytes) -> None:
    temp = f"{path}.orion_tmp"
    with open(temp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temp, path)
    except OSError as exc:
        if os.path.lexists(temp):
            remove_any(temp)
        raise RestoreError(f"Unable to atomically replace {path}: {exc}") from exc


def _verify(root: str, target: Manifest) -> None:
    actual = _manifest(root)
    if actual == target:
        return
    missing = sorted(set(target) - set(actual))
    extra = sorted(set(actual) - set(target))
    different = sorted(k for k in set(actual) & set(target) if actual[k] != target[k])
    details = []
    if missing:
        details.append("missing: " + ", ".join(missing[:10]))
    if extra:
        details.append("extra: " + ", ".join(extra[:10]))
    if different:
        details.append("different: " + ", ".join(different[:10]))
    raise RestoreError("MAIN mirror verification failed: " + "; ".join(details))


def _materialize(archive: bytes, target: Manifest, report=None) -> BranchStats:
    root = os.path.abspath(MAIN_ROOT)
    if root == PROJECT_ROOT:
        raise RestoreError("Safety violation: MAIN mirror equals development checkout.")
    os.makedirs(root, exist_ok=True)
    old = _manifest(root)
    target_paths = set(target)
    removed = 0
    added = 0
    updated = 0

    stale = sorted((p for p in old if p not in target_paths), key=lambda p: p.count("/"), reverse=True)
    for rel in stale:
        full = safe_target(root, rel)
        if os.path.lexists(full):
            removed += remove_any(full)

    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        for member in tar.getmembers():
            rel = CORE["archive_relpath"](member.name)
            if not rel:
                continue
            full = safe_target(root, rel)
            if member.isdir():
                if os.path.lexists(full) and (os.path.islink(full) or not os.path.isdir(full)):
                    removed += remove_any(full)
                os.makedirs(full, exist_ok=True)
                continue
            if member.issym():
                expected = ("link", member.linkname)
                if old.get(rel) == expected and os.path.islink(full) and os.readlink(full) == member.linkname:
                    continue
                if os.path.lexists(full):
                    removed += remove_any(full)
                _ensure_parent(full, root)
                os.symlink(member.linkname, full)
                updated += 1 if rel in old else 0
                added += 0 if rel in old else 1
                continue
            if not member.isfile():
                continue
            src = tar.extractfile(member)
            if src is None:
                raise RestoreError(f"Archive entry could not be read: {rel}")
            data = src.read()
            signature = ("file", len(data), hashlib.sha256(data).hexdigest())
            if old.get(rel) == signature and os.path.isfile(full) and not os.path.islink(full):
                continue
            existed = os.path.lexists(full)
            if existed and (os.path.islink(full) or os.path.isdir(full)):
                removed += remove_any(full)
            _ensure_parent(full, root)
            _write_atomic(full, data)
            updated += 1 if existed else 0
            added += 0 if existed else 1

    _verify(root, target)
    stats = BranchStats(
        files=sum(1 for sig in target.values() if sig[0] in ("file", "link")),
        added=added,
        updated=updated,
        removed=removed,
    )
    if report:
        report(f"MAIN MIRROR: {MAIN_ROOT}")
        report(f"Files: {stats.files} | Added: {stats.added} | Updated: {stats.updated} | Removed: {stats.removed} | EXACT MATCH")
    return stats


def sync_main_safe(project_root: str, remote: str = REMOTE, report=None) -> BranchStats:
    source = os.path.abspath(project_root)
    if source != PROJECT_ROOT:
        raise RestoreError("MAIN source must be the official ORION_NEXT checkout.")
    if not os.path.isdir(os.path.join(source, ".git")):
        raise RestoreError(f"Project is not a Git checkout: {source}")
    code, lines = run_git(["fetch", "--prune", remote, "main"], source)
    if code:
        raise RestoreError("\n".join(lines) or "git fetch origin main failed.")
    ref = f"{remote}/main"
    assert_no_gitlinks(source, ref)
    archive, target = archive_manifest(source, ref)
    return _materialize(archive, target, report)


# Patch only the MAIN path. The existing GUI and ALL path remain unchanged.
MOD["MAIN_ROOT"] = MAIN_ROOT
MOD["sync_main"] = sync_main_safe

if __name__ == "__main__":
    if "--launch-smoke-test" in sys.argv:
        raise SystemExit(MOD["_launch_smoke_test"]())
    root = MOD["tk"].Tk()
    MOD["OrionRestore"](root)
    root.mainloop()
