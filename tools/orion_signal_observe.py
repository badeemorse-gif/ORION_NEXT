"""Reproducible, non-trading Signal observation session controller.

The controller binds observations to an exact Git commit, explicit run
configuration, explicit universe content, a configuration SHA-256 fingerprint,
and an immutable experiment session ID. It never changes production sources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_ROOT = REPO_ROOT.parent / "ORION_OBSERVATION_ARTIFACTS"
OBSERVER_VERSION = "1.0"
SESSION_PREFIX = "EXP-"


def fail(message: str) -> NoReturn:
    raise RuntimeError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_commit(value: str) -> str:
    value = value.strip().lower()
    if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
        fail("baseline_commit must be a full 40-character hexadecimal Git commit SHA")
    return value


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Unable to read JSON input {path}: {exc}")


def resolve_artifact_root(path: Path) -> Path:
    raw = path.expanduser().absolute()
    repo = REPO_ROOT.resolve()
    resolved = raw.resolve(strict=False)
    if resolved == repo or repo in resolved.parents:
        fail(f"Artifact root must be outside the repository: {resolved}")
    for ancestor in [raw, *raw.parents]:
        if ancestor == ancestor.parent:
            break
        if (ancestor / ".git").is_dir():
            fail(f"Artifact root cannot be inside a Git checkout: {ancestor}")
    return resolved


def session_id(started_at: str) -> str:
    stamp = started_at.removesuffix("Z").replace("-", "").replace(":", "")
    return f"{SESSION_PREFIX}{stamp}Z-{secrets.token_hex(6)}"


def session_dir(root: Path, sid: str) -> Path:
    if not sid.startswith(SESSION_PREFIX):
        fail("Invalid session ID")
    if any(ch in sid for ch in ("/", "\\", "..")):
        fail("Invalid session ID path")
    return root / sid


def write_json(path: Path, value: Any, *, pretty: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2 if pretty else None, sort_keys=pretty)
    path.write_text(data + "\n", encoding="utf-8")


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
        tmp = Path(handle.name)
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def load_session(root: Path, sid: str) -> tuple[Path, dict[str, Any]]:
    directory = session_dir(root, sid)
    manifest = directory / "session.json"
    if not manifest.is_file():
        fail(f"Unknown observation session: {sid}")
    session = load_json(manifest)
    if session.get("session_id") != sid:
        fail("Session identity mismatch")
    return directory, session


def command_start(args: argparse.Namespace) -> int:
    artifact_root = resolve_artifact_root(Path(args.artifact_root or DEFAULT_ARTIFACT_ROOT))
    config_path = Path(args.config).expanduser().resolve()
    universe_path = Path(args.universe_file).expanduser().resolve()
    configuration = load_json(config_path)
    if not isinstance(configuration, dict):
        fail("configuration JSON must be an object")
    universe_raw = universe_path.read_bytes()
    universe = load_json(universe_path)
    baseline = validate_commit(args.baseline)

    config_bytes = canonical_json(configuration)
    config_fingerprint = sha256_bytes(config_bytes)
    universe_hash = sha256_bytes(universe_raw)
    universe_id = args.universe_id.strip() if args.universe_id else f"UNIV-{universe_hash[:12]}"
    if not universe_id:
        fail("universe_id must not be empty")

    started_at = utc_now()
    sid = session_id(started_at)
    directory = session_dir(artifact_root / "signal-observations", sid)
    if directory.exists():
        fail(f"Session directory already exists: {directory}")
    directory.mkdir(parents=True)

    # The original input is preserved as an immutable artifact for replay.
    (directory / "configuration_input.json").write_bytes(config_path.read_bytes())
    (directory / "universe_input.json").write_bytes(universe_raw)

    run_config = {
        "baseline_commit": baseline,
        "configuration": configuration,
        "universe_id": universe_id,
        "universe_sha256": universe_hash,
        "observer_version": OBSERVER_VERSION,
    }
    snapshot_identity = {
        "baseline_commit": baseline,
        "universe_id": universe_id,
        "universe_sha256": universe_hash,
    }
    fingerprint = {
        "algorithm": "sha256",
        "canonicalization": "json-sort-keys-utf8-no-whitespace",
        "configuration_fingerprint": config_fingerprint,
    }
    session = {
        "session_id": sid,
        "status": "RUNNING",
        "observer_version": OBSERVER_VERSION,
        "started_at_utc": started_at,
        "stopped_at_utc": None,
        "artifact_directory": str(directory),
        "baseline_commit": baseline,
        "universe_id": universe_id,
        "universe_sha256": universe_hash,
        "configuration_fingerprint": config_fingerprint,
    }
    write_json(directory / "run_config.json", run_config)
    write_json(directory / "snapshot_identity.json", snapshot_identity)
    write_json(directory / "configuration_fingerprint.json", fingerprint)
    write_json(directory / "session.json", session)
    (directory / "observations.jsonl").touch()

    print(json.dumps({"session_id": sid, "status": "RUNNING", "artifact_directory": str(directory)}, ensure_ascii=False))
    return 0


def command_record(args: argparse.Namespace) -> int:
    artifact_root = resolve_artifact_root(Path(args.artifact_root or DEFAULT_ARTIFACT_ROOT))
    directory, session = load_session(artifact_root / "signal-observations", args.session_id)
    if session.get("status") != "RUNNING":
        fail("Observation session is not RUNNING")
    observed_at = args.observed_at or utc_now()
    try:
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        fail(f"Invalid observed_at UTC timestamp: {exc}")
    signal_value: Any = args.signal
    if args.signal_json:
        try:
            signal_value = json.loads(args.signal_json)
        except json.JSONDecodeError as exc:
            fail(f"Invalid --signal-json: {exc}")
    payload: Any = {}
    if args.payload_json:
        try:
            payload = json.loads(args.payload_json)
        except json.JSONDecodeError as exc:
            fail(f"Invalid --payload-json: {exc}")
        if not isinstance(payload, dict):
            fail("--payload-json must be a JSON object")

    record = {
        **payload,
        "session_id": session["session_id"],
        "baseline_commit": session["baseline_commit"],
        "configuration_fingerprint": session["configuration_fingerprint"],
        "universe_id": session["universe_id"],
        "observed_at_utc": observed_at,
        "signal": signal_value,
    }
    with (directory / "observations.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"session_id": session["session_id"], "recorded": True, "observed_at_utc": observed_at}, ensure_ascii=False))
    return 0


def command_stop(args: argparse.Namespace) -> int:
    artifact_root = resolve_artifact_root(Path(args.artifact_root or DEFAULT_ARTIFACT_ROOT))
    directory, session = load_session(artifact_root / "signal-observations", args.session_id)
    if session.get("status") != "RUNNING":
        fail("Observation session is not RUNNING")
    required = (
        "run_config.json",
        "snapshot_identity.json",
        "configuration_fingerprint.json",
        "configuration_input.json",
        "universe_input.json",
        "observations.jsonl",
    )
    missing = [name for name in required if not (directory / name).is_file()]
    if missing:
        fail("Session artifact set incomplete: " + ", ".join(missing))
    fingerprint = load_json(directory / "configuration_fingerprint.json")
    if fingerprint.get("configuration_fingerprint") != session.get("configuration_fingerprint"):
        fail("Configuration fingerprint mismatch")
    session["status"] = "STOPPED"
    session["stopped_at_utc"] = utc_now()
    atomic_write_json(directory / "session.json", session)
    print(json.dumps({"session_id": session["session_id"], "status": "STOPPED", "stopped_at_utc": session["stopped_at_utc"]}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ORION reproducible Signal observation workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Create a new immutable observation session")
    start.add_argument("--baseline", required=True)
    start.add_argument("--config", required=True)
    start.add_argument("--universe-file", required=True)
    start.add_argument("--universe-id")
    start.add_argument("--artifact-root")
    start.set_defaults(func=command_start)

    record = sub.add_parser("record", help="Append one Signal observation")
    record.add_argument("--session-id", required=True)
    record.add_argument("--signal", default="")
    record.add_argument("--signal-json")
    record.add_argument("--observed-at")
    record.add_argument("--payload-json")
    record.add_argument("--artifact-root")
    record.set_defaults(func=command_record)

    stop = sub.add_parser("stop", help="Close an observation session")
    stop.add_argument("--session-id", required=True)
    stop.add_argument("--artifact-root")
    stop.set_defaults(func=command_stop)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as exc:
        print(f"OBSERVATION REFUSED/FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
