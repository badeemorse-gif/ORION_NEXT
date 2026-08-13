"""Fail-closed guard for ORION synchronization operations.

This module is deliberately small: it validates repository identity, current
branch state, operation mode, and mirror destination boundaries. The sync
controller remains responsible for the actual Git/archive/materialization
logic.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

EXPECTED_REMOTE = "github.com/badeemorse-gif/ORION_NEXT"
VALID_MODES = {"dev", "main", "all"}


def _git(project_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(project_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = result.stdout.strip()
    if result.returncode:
        raise RuntimeError(output or f"git {' '.join(args)} failed")
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


def require_repository(project_root: Path) -> None:
    project_root = project_root.resolve()
    if not project_root.is_dir():
        raise RuntimeError(f"PROJECT_ROOT is not a directory: {project_root}")
    if not (project_root / ".git").is_dir():
        raise RuntimeError(f"PROJECT_ROOT is not a Git checkout: {project_root}")
    actual_root = Path(_git(project_root, "rev-parse", "--show-toplevel")).resolve()
    if actual_root != project_root:
        raise RuntimeError(
            f"Repository root mismatch: expected {project_root}, git reports {actual_root}"
        )
    remotes = {item.strip() for item in _git(project_root, "remote").splitlines()}
    if "origin" not in remotes:
        raise RuntimeError("Required remote 'origin' is missing")
    origin = _git(project_root, "remote", "get-url", "origin")
    if normalize_remote(origin) != EXPECTED_REMOTE.lower():
        raise RuntimeError(f"Unexpected origin remote: {origin}")


def current_branch(project_root: Path) -> str:
    branch = _git(project_root, "branch", "--show-current").strip()
    if not branch:
        raise RuntimeError("Detached HEAD is refused")
    return branch


def _is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return bool(getattr(path.stat(), "st_file_attributes", 0) & 0x400)
    except OSError:
        return False


def require_mirror_destination(project_root: Path, destination: Path) -> None:
    project = project_root.resolve()
    target = destination.resolve()
    if target == project or project in target.parents:
        raise RuntimeError(f"Mirror destination is inside PROJECT_ROOT: {target}")
    if target == project.parent:
        raise RuntimeError(f"Mirror destination cannot be the ORION parent: {target}")
    if _is_reparse(target) or _is_reparse(target.parent):
        raise RuntimeError(f"Reparse-point/symlink destination is refused: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if (target.parent / ".git").is_dir():
        raise RuntimeError(f"Mirror parent is a Git checkout: {target.parent}")


def validate_mode(project_root: Path, mode: str, main_root: Path, all_root: Path) -> str:
    mode = mode.strip().lower()
    if mode not in VALID_MODES:
        raise RuntimeError("Mode must be one of: dev, main, all")
    require_repository(project_root)
    branch = current_branch(project_root)
    if mode == "main":
        require_mirror_destination(project_root, main_root)
    elif mode == "all":
        require_mirror_destination(project_root, all_root)
    return branch


__all__ = [
    "current_branch",
    "normalize_remote",
    "require_mirror_destination",
    "require_repository",
    "validate_mode",
]
