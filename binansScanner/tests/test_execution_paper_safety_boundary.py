from __future__ import annotations

import unittest

from core.dependency_container import ContainerConfiguration, ContainerError, DependencyContainer
from engines.execution_engine import PaperExecutionAdapter


class TestExecutionPaperSafetyBoundary(unittest.TestCase):
    def test_default_execution_is_paper_only(self) -> None:
        container = DependencyContainer()
        try:
            engine = container.build_execution_engine()
            self.assertIsInstance(engine._adapter, PaperExecutionAdapter)
            self.assertTrue(container._config.paper_trading_enabled)
        finally:
            container.reset()

    def test_disabling_paper_execution_cannot_select_live_executor(self) -> None:
        container = DependencyContainer(
            ContainerConfiguration(
                paper_trading_enabled=False,
                binance_api_key="unused-test-key",
                binance_api_secret="unused-test-secret",
                binance_testnet=False,
            )
        )
        try:
            with self.assertRaisesRegex(ContainerError, "Live execution is not available"):
                container.build_execution_engine()
            self.assertIsNone(container._execution_adapter_instance)
            self.assertIsNone(container._execution_engine_instance)
        finally:
            container.reset()

    def test_live_credentials_do_not_change_paper_adapter_selection(self) -> None:
        container = DependencyContainer(
            ContainerConfiguration(
                paper_trading_enabled=True,
                binance_api_key="unused-test-key",
                binance_api_secret="unused-test-secret",
                binance_testnet=False,
            )
        )
        try:
            engine = container.build_execution_engine()
            self.assertIsInstance(engine._adapter, PaperExecutionAdapter)
        finally:
            container.reset()


if __name__ == "__main__":
    unittest.main()
