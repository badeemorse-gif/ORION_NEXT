"""Mandatory fail-closed execution boundary contracts."""
from __future__ import annotations

import math
import unittest

from engines.execution_engine import ExecutionEngine, PaperExecutionAdapter
from engines.report_engine import InvalidReportData, ReportEngine
from models.execution import ExecutionPlan, ExecutionRequest, ExecutionResult, ExecutionSide, ExecutionStatus


class TestExecutionFailClosedBoundary(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = PaperExecutionAdapter()
        self.engine = ExecutionEngine(self.adapter)

    def _plan(self, **overrides: object) -> ExecutionPlan:
        values = {
            "symbol": "BTCUSDT",
            "side": ExecutionSide.BUY,
            "price": 100_000.0,
            "quantity": 1.0,
            "confidence": 90.0,
            "decision": "FAVORABLE",
        }
        values.update(overrides)
        return ExecutionPlan(**values)

    def test_nan_confidence_is_rejected_at_execution_boundary(self) -> None:
        self.assertFalse(self.engine.validate(self._plan(confidence=math.nan)))
        self.assertEqual(self.engine.execute(self._plan(confidence=math.nan)).status, ExecutionStatus.FAILED)

    def test_positive_and_negative_infinity_confidence_are_rejected(self) -> None:
        for value in (math.inf, -math.inf):
            with self.subTest(confidence=value):
                self.assertFalse(self.engine.validate(self._plan(confidence=value)))

    def test_invalid_quantity_override_is_rejected_and_not_fallen_back(self) -> None:
        plan = self._plan(quantity=2.0)
        for override in (math.nan, math.inf, -math.inf, 0.0, -1.0):
            with self.subTest(quantity=override):
                result = self.engine.execute(plan, quantity=override)
                self.assertEqual(result.status, ExecutionStatus.FAILED)

    def test_decision_execution_mismatch_is_rejected(self) -> None:
        result = self.engine.execute(self._plan(decision="FAVORABLE", side=ExecutionSide.SELL))
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertIn("mismatch", result.message.lower())

    def test_wait_cannot_execute_as_buy_or_sell(self) -> None:
        for side in (ExecutionSide.BUY, ExecutionSide.SELL):
            with self.subTest(side=side):
                result = self.engine.execute(self._plan(decision="WAIT", side=side))
                self.assertEqual(result.status, ExecutionStatus.FAILED)

    def test_invalid_decision_state_is_rejected(self) -> None:
        result = self.engine.execute(self._plan(decision="UNKNOWN"))
        self.assertEqual(result.status, ExecutionStatus.FAILED)

    def test_failed_execution_cannot_be_reported(self) -> None:
        failed = ExecutionResult(status=ExecutionStatus.FAILED, message="forced failure")
        with self.assertRaises(InvalidReportData):
            ReportEngine().build_report(symbol="BTCUSDT", analysis=None, profile=None, score=None, decision=None, execution=failed)

    def test_failed_execution_cannot_be_exported(self) -> None:
        failed = ExecutionResult(status=ExecutionStatus.FAILED, message="forced failure")
        report = ReportEngine().build_report(symbol="BTCUSDT", analysis=None, profile=None, score=None, decision=None, execution=None)
        object.__setattr__(report, "execution", failed)
        with self.assertRaises(InvalidReportData):
            ReportEngine().export_dict(report)


if __name__ == "__main__":
    unittest.main()
