"""
===============================================================================
ORION
Module : tests.test_execution_composition_root
Status : Canonical Paper Execution Boundary Regression Contract
===============================================================================

Verifies that the real DependencyContainer wires the canonical ExecutionPlan
into the real ExecutionEngine and isolated PaperExecutionAdapter for both BUY
and SELL paths.

No network calls and no live exchange execution are permitted.
===============================================================================
"""

from __future__ import annotations

import unittest

from core.dependency_container import DependencyContainer
from engines.execution_engine import ExecutionEngine, PaperExecutionAdapter
from models.execution import ExecutionPlan, ExecutionSide, ExecutionStatus


class TestExecutionCompositionRoot(unittest.TestCase):
    """Validate real composition-root execution without external APIs."""

    def setUp(self) -> None:
        self.container = DependencyContainer()
        self.engine = self.container.build_execution_engine()

    def tearDown(self) -> None:
        self.container.reset()

    def test_real_composition_root_wires_paper_execution(self) -> None:
        """Composition root must expose the canonical PaperExecutionAdapter."""
        self.assertIsInstance(self.engine, ExecutionEngine)
        self.assertIsInstance(self.engine._adapter, PaperExecutionAdapter)
        self.assertIs(self.engine._trade_executor._adapter, self.engine._adapter)

    def test_buy_and_sell_execute_through_real_composition_root(self) -> None:
        """BUY and SELL plans must execute through the real container graph."""
        for side in (ExecutionSide.BUY, ExecutionSide.SELL):
            with self.subTest(side=side):
                result = self.engine.execute(
                    ExecutionPlan(
                        symbol="BTCUSDT",
                        side=side,
                        price=100_000.0,
                        quantity=1.0,
                        confidence=90.0,
                        reason="composition-root execution contract",
                    )
                )

                self.assertEqual(result.status, ExecutionStatus.EXECUTED)
                self.assertTrue(result.executed)
                self.assertTrue(result.has_order_id)
                self.assertTrue(result.order_id.startswith("PAPER-ORD-"))
                self.assertIsNotNone(result.request)
                self.assertEqual(result.request.side, side)
                self.assertEqual(result.request.symbol, "BTCUSDT")
                self.assertEqual(result.request.quantity, 1.0)

        statistics = self.engine.statistics()
        self.assertEqual(statistics.total_processed, 2)
        self.assertEqual(statistics.total_executed, 2)
        self.assertEqual(statistics.total_skipped, 0)
        self.assertEqual(statistics.total_failed, 0)


if __name__ == "__main__":
    unittest.main()
