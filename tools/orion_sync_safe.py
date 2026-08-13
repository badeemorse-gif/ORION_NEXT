"""Safe ORION synchronization controller.

Hard invariants:
* PROJECT_ROOT is the only development checkout.
* DEV sync commits/pushes only the branch currently checked out there.
* MAIN mirror writes only to ORION_NEXT_MAIN.
* ALL mirrors write only to ORION_NEXT_ALL_BRANCHES/__branches__/<branch>.
* No mirror mode may run reset, clean, checkout, switch, or write any file
  under PROJECT_ROOT.
* Every mirror is verified against a Git archive before it is installed.
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import uuid
from pathlib import Path
from typing import NoReturn

PROJECT_ROOT = Path(os.environ.get("ORION_PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()
MAIN_ROOT = PROJECT_ROOT.parent / "ORION_NEXT_MAIN"
ALL_ROOT = PROJECT_ROOT.parent / "ORION_NEXT_ALL_BRANCHES"
REMOTE = os.environ.get("ORION_REMOTE", "origin")


def fail(message: str) -> NoReturn:
    raise RuntimeError(message)


def run_git(*args: str, cwd: Path = PROJECT_ROOT, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        encoding="utf-8", errors="replace",
    )
    output = result.stdout.strip()
    if check and result.returncode:
        fail(output or f"git {' '.join(args)} failed ({result.returncode})")
    return output


def require_checkout() -> None:
    if not (PROJECT_ROOT / ".git").is_dir():
        fail(f"PROJECT_ROOT is not a Git checkout: {PROJECT_ROOT}")
    remote = run_git("remote", "get-url", REMOTE)
    normalized = remote.replace("\\", "/").rstrip("/")
    if "github.com/badeemorse-gif/ORION_NEXT" not in normalized:
        fail(f"Unexpected Git remote: {remote}")


def current_branch() -> str:
    branch = run_git("branch", "--show-current")
    if not branch or branch == "HEAD":
        fail("Development sync requires a named branch; detached HEAD is refused.")
    return branch


def ensure_external_destination(destination: Path) -> None:
    destination = destination.resolve()
    project = PROJECT_ROOT.resolve()
    if destination == project or project in destination.parents:
        fail(f"REFUSED: mirror destination is inside PROJECT_ROOT: {destination}")
    if destination == project.parent:
        fail(f"REFUSED: mirror destination cannot be the ORION parent: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if (destination.parent / ".git").exists():
        fail(f"REFUSED: mirror parent is a Git checkout: {destination.parent}")


def safe_branch_path(branch: str) -> Path:
    if not branch or branch.startswith("/") or "\\" in branch:
        fail(f"Unsafe branch name: {branch!r}")
    parts = branch.split("/")
    if any(p in ("", ".", "..") for p in parts):
        fail(f"Unsafe branch name: {branch!r}")
    target = (ALL_ROOT / "__branches__" / Path(*parts)).resolve()
    base = (ALL_ROOT / "__branches__").resolve()
    if os.path.commonpath([str(base), str(target)]) != str(base):
        fail(f"Unsafe branch destination: {target}")
    return target


def archive(branch_ref: str) -> bytes:
    try:
        return subprocess.check_output(
            ["git", "archive", "--format=tar", branch_ref],
            cwd=str(PROJECT_ROOT), stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        fail(exc.output.decode("utf-8", "replace").strip() or f"Unable to archive {branch_ref}")


def snapshot_manifest(data: bytes) -> dict[str, tuple]:
    result: dict[str, tuple] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
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
                    fail(f"Cannot read archive member: {rel}")
                payload = source.read()
                result[rel] = ("file", len(payload), hashlib.sha256(payload).hexdigest())
            else:
                fail(f"Unsupported archive member type: {rel}")
    for rel in list(result):
        parent = Path(rel).parent
        while parent != Path("."):
            result.setdefault(parent.as_posix(), ("dir",))
            parent = parent.parent
    return result


def local_manifest(root: Path) -> dict[str, tuple]:
    result: dict[str, tuple] = {}
    if not root.is_dir():
        return result
    for base, dirs, files in os.walk(root, topdown=True, followlinks=False):
        base_path = Path(base)
        dirs[:] = [d for d in dirs if d != ".git"]
        rel_base = base_path.relative_to(root)
        if rel_base != Path("."):
            result[rel_base.as_posix()] = ("dir",)
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


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def verify_snapshot(root: Path, expected: dict[str, tuple], branch: str) -> None:
    actual = local_manifest(root)
    if actual == expected:
        return
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    different = sorted(k for k in set(actual) & set(expected) if actual[k] != expected[k])
    details = []
    if missing:
        details.append("missing=" + ",".join(missing[:8]))
    if extra:
        details.append("extra=" + ",".join(extra[:8]))
    if different:
        details.append("different=" + ",".join(different[:8]))
    fail(f"Snapshot verification failed for {branch}: {'; '.join(details)}")


def materialize(branch: str, destination: Path) -> None:
    """Install a verified branch snapshot outside PROJECT_ROOT.

    The old mirror remains untouched until the complete staged snapshot passes
    verification. A backup directory is retained until the new snapshot has
    been installed and verified, then removed.
    """
    destination = destination.resolve()
    ensure_external_destination(destination)
    data = archive(f"{REMOTE}/{branch}")
    expected = snapshot_manifest(data)
    staging = destination.parent / f".{destination.name}.orion-staging-{uuid.uuid4().hex}"
    backup = destination.parent / f".{destination.name}.orion-backup-{uuid.uuid4().hex}"
    try:
        staging.mkdir(parents=False)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
            tar.extractall(staging, filter="data")
        verify_snapshot(staging, expected, branch)
        if destination.exists():
            destination.rename(backup)
        staging.rename(destination)
        try:
            verify_snapshot(destination, expected, branch)
        except Exception:
            if destination.exists():
                remove_path(destination)
            if backup.exists():
                backup.rename(destination)
            raise
        if backup.exists():
            remove_path(backup)
    except Exception:
        if staging.exists():
            remove_path(staging)
        if backup.exists() and not destination.exists():
            backup.rename(destination)
        raise


def sync_development() -> int:
    """Commit and push only the branch currently checked out in PROJECT_ROOT."""
    require_checkout()
    branch = current_branch()
    status = run_git("status", "--short")
    if not status:
        print(f"DEV SYNC: clean; branch={branch}")
        return 0
    run_git("add", "-A")
    staged_check = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=str(PROJECT_ROOT)
    )
    if staged_check.returncode == 0:
        print("DEV SYNC: nothing staged")
        return 0
    run_git("commit", "-m", f"sync: update ORION ({branch})")
    run_git("push", "-u", REMOTE, branch)
    print(f"DEV SYNC SUCCESS: {branch}")
    return 0


def sync_main() -> int:
    require_checkout()
    run_git("fetch", "--prune", REMOTE, "main")
    materialize("main", MAIN_ROOT)
    print(f"MAIN MIRROR SUCCESS: {MAIN_ROOT}")
    return 0


def sync_all() -> int:
    require_checkout()
    run_git("fetch", "--prune", REMOTE)
    branches = sorted(
        b.strip() for b in run_git(
            "for-each-ref", "--format=%(refname:strip=3)", f"refs/remotes/{REMOTE}"
        ).splitlines()
        if b.strip() and b.strip() != "HEAD"
    )
    for branch in branches:
        materialize(branch, safe_branch_path(branch))
    print(f"ALL MIRRORS SUCCESS: {len(branches)} branches -> {ALL_ROOT / '__branches__'}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"dev", "main", "all"}:
        print("Usage: python tools/orion_sync_safe.py {dev|main|all}")
        return 2
    try:
        return {"dev": sync_development, "main": sync_main, "all": sync_all}[argv[1]]()
    except Exception as exc:
        print(f"SYNC REFUSED/FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
