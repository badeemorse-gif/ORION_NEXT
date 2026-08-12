from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYNC_BAT = PROJECT_ROOT / "tools" / "orion_sync.bat"
SYNC_GUI = PROJECT_ROOT / "tools" / "orion_sync_gui.pyw"
SYNC_VERIFY = PROJECT_ROOT / "tools" / "orion_sync_verify.py"


class TestSyncToolContract(unittest.TestCase):
    def test_sync_batch_is_github_to_local_only(self):
        content = SYNC_BAT.read_text(encoding="utf-8")

        self.assertIn("ORION_SYNC_VERSION=3.0.0", content)
        self.assertIn("ORION GITHUB -> LOCAL SYNC", content)
        self.assertIn("git fetch %ORIGIN% %BRANCH%", content)
        self.assertIn("git reset --hard %ORIGIN%/%BRANCH%", content)
        self.assertIn("git clean -fdx", content)
        self.assertIn("The .git directory is preserved.", content)
        self.assertIn("No local commit or push is ever created by this tool.", content)
        self.assertIn("ORION_SYNC_BACKUP_PATH", content)
        self.assertIn("git show %ORIGIN%/%BRANCH%:tools/orion_sync.bat", content)
        self.assertIn("ORION_SYNC_BOOTSTRAP", content)

        self.assertNotIn("git add -A", content)
        self.assertNotIn("git commit", content)
        self.assertNotIn("git push", content)
        self.assertNotIn("Local -> Git -> GitHub", content)
        self.assertNotIn("C:\\Users\\badee\\Desktop\\ORION_NEXT", content)

    def test_sync_batch_defaults_to_active_phase2_branch(self):
        content = SYNC_BAT.read_text(encoding="utf-8")
        self.assertIn(
            'if "%BRANCH%"=="" set "BRANCH=phase2/core-intelligence-hardening"',
            content,
        )

    def test_sync_batch_resolves_root_from_tool_location(self):
        content = SYNC_BAT.read_text(encoding="utf-8")
        self.assertIn('set "ORION_TOOLS_DIR=%~dp0"', content)
        self.assertIn('set "ORION_ROOT=%%~fI"', content)

    def test_sync_gui_is_path_aware_and_branch_aware(self):
        content = SYNC_GUI.read_text(encoding="utf-8")
        self.assertIn("GitHub → Git → Local", content)
        self.assertIn("PROJECT_ROOT = Path(__file__).resolve().parents[1]", content)
        self.assertIn("VERIFY_SCRIPT", content)
        self.assertIn("refresh_branches", content)
        self.assertIn("state=\"normal\"", content)
        self.assertNotIn("C:\\Users\\badee\\Desktop\\ORION_NEXT", content)

    def test_exact_parity_verifier_is_read_only(self):
        content = SYNC_VERIFY.read_text(encoding="utf-8")
        self.assertIn("Exact GitHub -> Local parity verifier", content)
        self.assertIn('run_git("fetch", "--prune", REMOTE, branch)', content)
        self.assertIn('run_git("archive", "--format=tar", ref)', content)
        self.assertIn("RESULT: EXACT MATCH", content)
        self.assertNotIn("reset --hard", content)
        self.assertNotIn("clean -fdx", content)
        self.assertNotIn("git commit", content)
        self.assertNotIn("git push", content)


if __name__ == "__main__":
    unittest.main()
