from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import orion_signal_observe as observe


class TestSignalObservationWorkflow(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "artifacts"
        self.config = Path(self.tmp.name) / "config.json"
        self.universe = Path(self.tmp.name) / "universe.json"
        self.config.write_text(json.dumps({"score_threshold": 0.7, "timeframe": "1h"}), encoding="utf-8")
        self.universe.write_text(json.dumps(["BTCUSDT", "ETHUSDT"]), encoding="utf-8")
        self.baseline = "c54dc67792776da905a3efb1f667c1869c15db3d"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _start(self) -> Path:
        args = mock.Mock(
            artifact_root=str(self.root),
            config=str(self.config),
            universe_file=str(self.universe),
            universe_id=None,
            baseline=self.baseline,
        )
        with mock.patch.object(observe, "utc_now", return_value="2026-08-17T00:00:00Z"), mock.patch.object(
            observe.secrets, "token_hex", return_value="0123456789ab"
        ):
            rc = observe.command_start(args)
        self.assertEqual(rc, 0)
        return self.root / "signal-observations" / "EXP-20260817T000000Z-0123456789ab"

    def test_start_creates_immutable_identity_artifacts(self) -> None:
        directory = self._start()
        session = json.loads((directory / "session.json").read_text(encoding="utf-8"))
        self.assertEqual(session["status"], "RUNNING")
        self.assertEqual(session["baseline_commit"], self.baseline)
        self.assertTrue(session["configuration_fingerprint"])
        self.assertTrue(session["universe_id"].startswith("UNIV-"))
        self.assertTrue((directory / "configuration_input.json").is_file())
        self.assertTrue((directory / "universe_input.json").is_file())
        self.assertTrue((directory / "observations.jsonl").is_file())

    def test_record_binds_signal_to_session_identity(self) -> None:
        directory = self._start()
        sid = json.loads((directory / "session.json").read_text(encoding="utf-8"))["session_id"]
        args = mock.Mock(
            artifact_root=str(self.root),
            session_id=sid,
            signal="BUY",
            signal_json=None,
            observed_at="2026-08-17T00:05:00Z",
            payload_json='{"score": 0.81}',
        )
        self.assertEqual(observe.command_record(args), 0)
        row = json.loads((directory / "observations.jsonl").read_text(encoding="utf-8").strip())
        self.assertEqual(row["session_id"], sid)
        self.assertEqual(row["baseline_commit"], self.baseline)
        self.assertEqual(row["signal"], "BUY")
        self.assertEqual(row["score"], 0.81)

    def test_stop_closes_session_and_prevents_late_record(self) -> None:
        directory = self._start()
        sid = json.loads((directory / "session.json").read_text(encoding="utf-8"))["session_id"]
        stop_args = mock.Mock(artifact_root=str(self.root), session_id=sid)
        with mock.patch.object(observe, "utc_now", return_value="2026-08-17T00:10:00Z"):
            self.assertEqual(observe.command_stop(stop_args), 0)
        session = json.loads((directory / "session.json").read_text(encoding="utf-8"))
        self.assertEqual(session["status"], "STOPPED")
        record_args = mock.Mock(
            artifact_root=str(self.root),
            session_id=sid,
            signal="BUY",
            signal_json=None,
            observed_at="2026-08-17T00:11:00Z",
            payload_json=None,
        )
        with self.assertRaises(RuntimeError):
            observe.command_record(record_args)

    def test_replay_reuses_immutable_inputs_but_creates_new_session(self) -> None:
        directory = self._start()
        sid = json.loads((directory / "session.json").read_text(encoding="utf-8"))["session_id"]
        with mock.patch.object(observe, "utc_now", return_value="2026-08-17T00:10:00Z"):
            self.assertEqual(observe.command_stop(mock.Mock(artifact_root=str(self.root), session_id=sid)), 0)
        with mock.patch.object(observe, "utc_now", return_value="2026-08-17T00:20:00Z"), mock.patch.object(
            observe.secrets, "token_hex", return_value="fedcba987654"
        ):
            self.assertEqual(observe.command_replay(mock.Mock(artifact_root=str(self.root), session_id=sid)), 0)
        replay_dir = self.root / "signal-observations" / "EXP-20260817T002000Z-fedcba987654"
        self.assertTrue(replay_dir.is_dir())
        replay_session = json.loads((replay_dir / "session.json").read_text(encoding="utf-8"))
        self.assertNotEqual(sid, replay_session["session_id"])
        self.assertEqual(replay_session["baseline_commit"], self.baseline)
        self.assertEqual(replay_session["configuration_fingerprint"], json.loads((directory / "configuration_fingerprint.json").read_text(encoding="utf-8"))["configuration_fingerprint"])
        self.assertEqual(
            (directory / "configuration_input.json").read_bytes(),
            (replay_dir / "configuration_input.json").read_bytes(),
        )
        self.assertEqual(
            (directory / "universe_input.json").read_bytes(),
            (replay_dir / "universe_input.json").read_bytes(),
        )

    def test_artifact_root_inside_repository_is_refused(self) -> None:
        with mock.patch.object(observe, "REPO_ROOT", Path(self.tmp.name) / "repo"):
            repo = observe.REPO_ROOT
            (repo / ".git").mkdir(parents=True)
            args = mock.Mock(
                artifact_root=str(repo / "artifacts"),
                config=str(self.config),
                universe_file=str(self.universe),
                universe_id=None,
                baseline=self.baseline,
            )
            with self.assertRaises(RuntimeError):
                observe.command_start(args)


if __name__ == "__main__":
    unittest.main()
