import io
import os
import runpy
import tarfile
import tempfile
import unittest
from pathlib import Path


class MainSyncIsolationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = runpy.run_path(
            str(Path(__file__).resolve().parents[1] / "tools" / "orion_restore_main_gui.pyw")
        )

    @staticmethod
    def empty_tar() -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w"):
            pass
        return buffer.getvalue()

    def test_main_destination_is_not_project_root(self):
        self.assertNotEqual(
            os.path.abspath(self.module["MAIN_ROOT"]),
            os.path.abspath(self.module["PROJECT_ROOT"]),
        )

    def test_project_root_is_rejected_as_main_destination(self):
        with self.assertRaises(self.module["RestoreError"]):
            self.module["materialize_main"](
                self.empty_tar(), self.module["PROJECT_ROOT"], {}
            )

    def test_materialization_changes_only_isolated_main_mirror(self):
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as mirror:
            project = os.path.abspath(project)
            mirror = os.path.abspath(mirror)
            self.module["PROJECT_ROOT"] = project
            self.module["MAIN_ROOT"] = mirror

            protected = Path(project) / "local_test_change.txt"
            protected.write_text("must remain untouched", encoding="utf-8")

            stale = Path(mirror) / "stale.txt"
            stale.write_text("stale", encoding="utf-8")

            stats = self.module["materialize_main"](
                self.empty_tar(), mirror, {}
            )

            self.assertEqual(stats.files, 0)
            self.assertFalse(stale.exists())
            self.assertEqual(
                protected.read_text(encoding="utf-8"),
                "must remain untouched",
            )


if __name__ == "__main__":
    unittest.main()
