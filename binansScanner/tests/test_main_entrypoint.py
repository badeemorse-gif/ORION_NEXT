from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from bootstrap.bootstrap_result import BootstrapResult


class TestMainEntrypoint(unittest.TestCase):
    def test_main_builds_runtime_from_bootstrap_container(self) -> None:
        from core.dependency_container import DependencyContainer
        import main

        container = Mock(spec=DependencyContainer)
        runner = Mock()
        runner.run.return_value = BootstrapResult(
            success=True,
            initialized_components={"dependency_container": container},
        )
        runtime = Mock()

        with patch.object(main, "BootstrapRunner", return_value=runner), patch.object(
            main, "ApplicationRuntime", return_value=runtime
        ):
            result = main.main()

        self.assertEqual(result, 0)
        runner.run.assert_called_once()
        main.ApplicationRuntime.assert_called_once_with(container)
        runtime.run.assert_called_once_with()

    def test_main_fails_when_bootstrap_fails(self) -> None:
        import main

        runner = Mock()
        runner.run.return_value = BootstrapResult(
            success=False,
            initialized_components={},
            message="bootstrap failure",
        )

        with patch.object(main, "BootstrapRunner", return_value=runner):
            result = main.main()

        self.assertEqual(result, 1)

    def test_main_fails_when_bootstrap_does_not_expose_container(self) -> None:
        import main

        runner = Mock()
        runner.run.return_value = BootstrapResult(
            success=True,
            initialized_components={},
        )

        with patch.object(main, "BootstrapRunner", return_value=runner):
            result = main.main()

        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
