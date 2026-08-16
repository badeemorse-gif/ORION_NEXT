from __future__ import annotations

import unittest

from core.dependency_container import ContainerConfiguration, ContainerError, DependencyContainer
from engines.execution_engine import ExecutionEngine, PaperExecutionAdapter
from models.execution import ExecutionPlan, ExecutionSide, ExecutionStatus


class TestExecutionCompositionRoot(unittest.TestCase):
    def setUp(self) -> None:
        self.container = DependencyContainer()
        self.engine = self.container.build_execution_engine()

    def tearDown(self) -> None:
        self.container.reset()

    def test_default_composition_root_is_paper_only(self) -> None:
        self.assertTrue(self.container._config.paper_trading_enabled)
        self.assertIsInstance(self.engine, ExecutionEngine)
        self.assertIsInstance(self.engine._adapter, PaperExecutionAdapter)
        self.assertIs(self.engine._trade_executor._adapter, self.engine._adapter)

    def test_buy_and_sell_execute_through_real_composition_root(self) -> None:
        for side, decision in ((ExecutionSide.BUY, "FAVORABLE"), (ExecutionSide.SELL, "UNFAVORABLE")):
            with self.subTest(side=side):
                result = self.engine.execute(
                    ExecutionPlan(
                        symbol="BTCUSDT",
                        side=side,
                        price=100_000.0,
                        quantity=1.0,
                        confidence=90.0,
                        reason="composition-root execution contract",
                        decision=decision,
                    )
                )
                self.assertEqual(result.status, ExecutionStatus.EXECUTED)
                self.assertTrue(result.executed)
                self.assertTrue(result.has_order_id)
                self.assertEqual(result.request.side, side)
                self.assertEqual(result.request.symbol, "BTCUSDT")
                self.assertEqual(result.request.quantity, 1.0)

        statistics = self.engine.statistics()
        self.assertEqual(statistics.total_processed, 2)
        self.assertEqual(statistics.total_executed, 2)
        self.assertEqual(statistics.total_skipped, 0)
        self.assertEqual(statistics.total_failed, 0)

    def test_disabled_paper_trading_fails_closed_without_live_fallback(self) -> None:
        container = DependencyContainer(ContainerConfiguration(paper_trading_enabled=False))
        try:
            with self.assertRaises(ContainerError):
                container.build_execution_engine()
            self.assertIsNone(container._execution_adapter_instance)
            self.assertIsNone(container._execution_engine_instance)
        finally:
            container.reset()


if __name__ == "__main__":
    unittest.main()
