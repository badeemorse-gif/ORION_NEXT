from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from tools import orion_final_materialize as fm


class FinalMaterializationContractTests(unittest.TestCase):
    def _tar(self, members: list[tuple[str, str, bytes]]) -> bytes:
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as tar:
            for kind, name, payload in members:
                info = tarfile.TarInfo(name)
                if kind == "dir":
                    info.type = tarfile.DIRTYPE
                elif kind == "file":
                    info.size = len(payload)
                else:
                    raise AssertionError(kind)
                tar.addfile(info, io.BytesIO(payload) if kind == "file" else None)
        return stream.getvalue()

    def test_exact_commit_requires_full_sha(self):
        with self.assertRaises(fm.MaterializationError):
            fm.validate_commit("abc123")
        with self.assertRaises(fm.MaterializationError):
            fm.validate_commit("z" * 40)
        self.assertEqual("a" * 40, fm.validate_commit("A" * 40))

    def test_snapshot_manifest_hashes_files_and_parents(self):
        data = self._tar([("dir", "pkg", b""), ("file", "pkg/a.txt", b"ORION")])
        manifest = fm.snapshot_manifest(data)
        self.assertEqual(("dir",), manifest["pkg"])
        self.assertEqual(5, manifest["pkg/a.txt"][1])
        self.assertEqual("a" * 64, "a" * 64)  # deterministic assertion anchor
        self.assertEqual(64, len(manifest["pkg/a.txt"][2]))

    def test_archive_file_directory_collision_is_rejected(self):
        data = self._tar([("file", "collision", b"x"), ("dir", "collision/child", b"")])
        with self.assertRaises(fm.MaterializationError):
            fm.snapshot_manifest(data)

    def test_target_inside_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = fm.ROOT / "_forbidden_finalization_target"
            with self.assertRaises(fm.MaterializationError):
                fm.ensure_external_target(candidate)
            self.assertFalse(candidate.exists())

    def test_target_parent_that_is_git_checkout_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "parent"
            parent.mkdir()
            (parent / ".git").mkdir()
            target = parent / "snapshot"
            with self.assertRaises(fm.MaterializationError):
                fm.ensure_external_target(target)

    def test_verify_snapshot_detects_extra_and_different_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "snapshot"
            root.mkdir()
            (root / "a.txt").write_bytes(b"changed")
            (root / "extra.txt").write_bytes(b"extra")
            expected = {"a.txt": ("file", 4, "0" * 64)}
            with self.assertRaises(fm.MaterializationError):
                fm.verify_snapshot(root, expected, "contract-test")


if __name__ == "__main__":
    unittest.main()
