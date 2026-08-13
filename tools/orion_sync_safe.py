"""Safe ORION synchronization controller.

Hard invariant: no mirror operation may materialize into the development
checkout (ORION_NEXT). Development sync only commits/pushes the CURRENT Git
branch. MAIN and ALL are read-only snapshots written outside PROJECT_ROOT.
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("ORION_PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()
MAIN_ROOT = PROJECT_ROOT.parent / "ORION_NEXT_MAIN"
ALL_ROOT = PROJECT_ROOT.parent / "ORION_NEXT_ALL_BRANCHES"
REMOTE = os.environ.get("ORION_REMOTE", "origin")


def fail(message: str) -> "NoReturn":
    raise RuntimeError(message)


def run_git(*args: str, cwd: Path = PROJECT_ROOT, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            encoding="utf-8", errors="replace")
    output = result.stdout.strip()
    if check and result.returncode:
        fail(output or f"git {' '.join(args)} failed ({result.returncode})")
    return output


def require_checkout() -> None:
    if not (PROJECT_ROOT / ".git").is_dir():
        fail(f"PROJECT_ROOT is not a Git checkout: {PROJECT_ROOT}")
    remote = run_git("remote", "get-url", REMOTE)
    if "badeemorse-gif/ORION_NEXT" not in remote.replace("\\", "/"):
        fail(f"Unexpected Git remote: {remote}")


def current_branch() -> str:
    branch = run_git("branch", "--show-current")
    if not branch or branch == "HEAD":
        fail("Development sync requires a named branch; detached HEAD is refused.")
    return branch


def safe_branch_path(root: Path, branch: str) -> Path:
    if not branch or branch.startswith("/") or "\\" in branch:
        fail(f"Unsafe branch name: {branch!r}")
    parts = [p for p in branch.split("/") if p not in ("", ".", "..")]
    if not parts or any(p == ".." for p in branch.split("/")):
        fail(f"Unsafe branch name: {branch!r}")
    target = (root / "__branches__" / Path(*parts)).resolve()
    base = (root / "__branches__").resolve()
    if os.path.commonpath([str(base), str(target)]) != str(base):
        fail(f"Unsafe branch destination: {target}")
    return target


def ensure_empty_or_snapshot_dir(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if (root / ".git").exists():
        fail(f"Refusing to use a Git checkout as mirror root: {root}")


def archive(branch_ref: str) -> bytes:
    return subprocess.check_output(["git", "archive", "--format=tar", branch_ref], cwd=str(PROJECT_ROOT))


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
                h = hashlib.sha256(path.read_bytes()).hexdigest()
                result[rel] = ("file", path.stat().st_size, h)
    return result


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def materialize(branch: str, destination: Path) -> None:
    """Atomically replace an external snapshot directory with a Git archive."""
    destination = destination.resolve()
    if destination == PROJECT_ROOT or PROJECT_ROOT in destination.parents:
        fail(f"Mirror destination is inside development checkout: {destination}")
    ensure_empty_or_snapshot_dir(destination.parent)
    data = archive(f"{REMOTE}/{branch}")
    expected = snapshot_manifest(data)
    temp = destination.parent / f".{destination.name}.orion-staging"
    if temp.exists():
        remove_path(temp)
    temp.mkdir(parents=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
            tar.extractall(temp, filter="data")
        actual = local_manifest(temp)
        if actual != expected:
            fail(f"Snapshot verification failed for {branch}")
        if destination.exists():
            remove_path(destination)
        temp.replace(destination)
        if local_manifest(destination) != expected:
            fail(f"Post-install parity verification failed for {branch}")
    except Exception:
        if temp.exists():
            remove_path(temp)
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
    if not run_git("diff", "--cached", "--quiet", check=False) == "":
        pass
    # diff --cached --quiet returns code 1 when changes exist; run_git(check=False)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(PROJECT_ROOT)).returncode == 0:
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
    branches = [b.strip() for b in run_git("for-each-ref", "--format=%(refname:strip=3)", f"refs/remotes/{REMOTE}").splitlines()]
    branches = sorted(b for b in branches if b and b != "HEAD")
    for branch in branches:
        target = safe_branch_path(ALL_ROOT, branch)
        materialize(branch, target)
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
