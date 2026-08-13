import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import orion_sync_guard as guard


class TestSyncGuardContract(unittest.TestCase):
    def test_repository_root_is_checkout_root(self):
        self.assertEqual(guard.REPO_ROOT, Path(guard.__file__).resolve().parents[1])

    def test_canonical_remote_is_required(self):
        with patch.object(guard, "run_git", return_value="https://github.com/other/repo.git"):
            with self.assertRaises(RuntimeError):
                guard.canonical_remote()

    def test_detached_head_is_refused(self):
        with patch.object(guard, "run_git", return_value=""):
            with self.assertRaises(RuntimeError):
                guard.current_branch()

    def test_invalid_mode_is_refused(self):
        with self.assertRaises(RuntimeError):
            guard.validate_mode("unknown")

    def test_delegate_pins_project_root_and_remote(self):
        completed = subprocess.CompletedProcess([], 0)
        with patch.object(guard.subprocess, "run", return_value=completed) as run:
            result = guard.delegate("main", "https://github.com/badeemorse-gif/ORION_NEXT.git")
        self.assertEqual(result, 0)
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["env"]["ORION_PROJECT_ROOT"], str(guard.REPO_ROOT))
        self.assertEqual(kwargs["env"]["ORION_REMOTE"], "origin")
        self.assertEqual(run.call_args.args[0][-1], "main")

    def test_audit_rejects_forbidden_command_in_entrypoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad = root / "bad.bat"
            bad.write_text(" ".join(("git", "reset", "--hard", "origin/main")) + "\n", encoding="utf-8")
            with patch.object(guard, "MIRROR_ENTRYPOINTS", (bad,)), patch.object(guard, "REPO_ROOT", root):
                self.assertEqual(guard.audit_entrypoints(), 1)

    def test_audit_accepts_guarded_launchers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / "tools"
            tools.mkdir()
            entries = []
            for name in ("orion_sync.bat", "orion_main_sync.bat", "orion_all_sync.bat", "orion_sync_safe.py"):
                path = tools / name
                path.write_text("python tools\\orion_sync_guard.py main\n", encoding="utf-8")
                entries.append(path)
            with patch.object(guard, "MIRROR_ENTRYPOINTS", tuple(entries)), patch.object(guard, "REPO_ROOT", root):
                self.assertEqual(guard.audit_entrypoints(), 0)


if __name__ == "__main__":
    unittest.main()
