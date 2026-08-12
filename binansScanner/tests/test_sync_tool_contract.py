from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYNC_BAT = PROJECT_ROOT / "tools" / "orion_sync.bat"
SYNC_GUI = PROJECT_ROOT / "tools" / "orion_sync_gui.pyw"


class TestSyncToolContract(unittest.TestCase):
    def test_sync_batch_is_github_to_local_only(self):
        content = SYNC_BAT.read_text(encoding="utf-8")

        self.assertIn("ORION GITHUB -> LOCAL SYNC", content)
        self.assertIn("git fetch %ORIGIN% %BRANCH%", content)
        self.assertIn("git reset --hard %ORIGIN%/%BRANCH%", content)
        self.assertIn("git clean -fdx", content)
        self.assertIn("The .git directory itself is NOT deleted.", content)
        self.assertIn("No local commit created.", content)
        self.assertIn("No GitHub push performed.", content)

        self.assertNotIn("git add -A", content)
        self.assertNotIn("git commit", content)
        self.assertNotIn("git push", content)
        self.assertNotIn("Local -> Git -> GitHub", content)

    def test_sync_batch_defaults_to_active_phase2_branch(self):
        content = SYNC_BAT.read_text(encoding="utf-8")
        self.assertIn(
            'if "%BRANCH%"=="" set "BRANCH=phase2/core-intelligence-hardening"',
            content,
        )

    def test_sync_gui_exposes_github_to_local_direction(self):
        content = SYNC_GUI.read_text(encoding="utf-8")
        self.assertIn("GitHub → Git → Local", content)
        self.assertIn("GitHub is the source of truth.", content)
        self.assertIn("orion_sync.bat", content)
        self.assertIn("branch", content)
        self.assertIn("SYNC_SCRIPT, branch", content)


if __name__ == "__main__":
    unittest.main()
