import subprocess
import unittest
from unittest.mock import patch

import orion_sync_safe as sync


class TestSafeSyncContract(unittest.TestCase):
    def test_main_destination_is_outside_project_root(self):
        self.assertNotEqual(sync.MAIN_ROOT.resolve(), sync.PROJECT_ROOT.resolve())
        self.assertNotIn(sync.PROJECT_ROOT.resolve(), sync.MAIN_ROOT.resolve().parents)

    def test_all_destination_is_outside_project_root(self):
        target = sync.safe_branch_path("future/opportunity-candidate-set")
        self.assertNotIn(sync.PROJECT_ROOT.resolve(), target.parents)
        self.assertEqual(target.name, "candidate-set")

    def test_path_traversal_is_rejected(self):
        for value in ("future/../main", "/absolute", "future\\escape"):
            with self.assertRaises(RuntimeError):
                sync.safe_branch_path(value)

    def test_development_sync_pushes_current_branch_not_main(self):
        calls = []
        diff_result = subprocess.CompletedProcess([], 1)
        with patch.object(sync, "require_checkout"), \
             patch.object(sync, "current_branch", return_value="future/example"), \
             patch.object(sync, "run_git", side_effect=lambda *args, **kwargs: calls.append(args) or "changed"), \
             patch.object(sync.subprocess, "run", return_value=diff_result):
            sync.sync_development()
        push_calls = [call for call in calls if call and call[0] == "push"]
        self.assertEqual(len(push_calls), 1)
        self.assertIn("future/example", push_calls[0])
        self.assertNotIn("main", push_calls[0])

    def test_main_mode_uses_main_root(self):
        with patch.object(sync, "require_checkout"), \
             patch.object(sync, "run_git"), \
             patch.object(sync, "materialize") as materialize:
            sync.sync_main()
        materialize.assert_called_once_with("main", sync.MAIN_ROOT)
        self.assertNotEqual(materialize.call_args.args[1].resolve(), sync.PROJECT_ROOT.resolve())

    def test_all_mode_never_targets_project_root(self):
        branches = "main\nfuture/example\n"
        with patch.object(sync, "require_checkout"), \
             patch.object(sync, "run_git", side_effect=["", branches]), \
             patch.object(sync, "materialize") as materialize:
            sync.sync_all()
        for _, destination in materialize.call_args_list:
            self.assertNotEqual(destination.resolve(), sync.PROJECT_ROOT.resolve())
            self.assertNotIn(sync.PROJECT_ROOT.resolve(), destination.resolve().parents)


if __name__ == "__main__":
    unittest.main()
