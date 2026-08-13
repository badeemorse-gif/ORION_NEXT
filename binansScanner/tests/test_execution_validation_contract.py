"""Execution boundary validation contracts."""

from __future__ import annotations

import math
import unittest

from engines.execution_engine import ExecutionEngine, PaperExecutionAdapter
from models.execution import ExecutionPlan, ExecutionRequest, ExecutionSide, ExecutionStatus


class TestExecutionValidationContract(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = PaperExecutionAdapter()
        self.engine = ExecutionEngine(self.adapter)

    def _request(self, **overrides: float) -> ExecutionRequest:
        values = {
            "symbol": "BTCUSDT",
            "side": ExecutionSide.BUY,
            "price": 100_000.0,
            "quantity": 1.0,
            "confidence": 90.0,
        }
        values.update(overrides)
        return ExecutionRequest(**values)

    def _hold_plan(self) -> ExecutionPlan:
        return ExecutionPlan(
            symbol="BTCUSDT",
            side=ExecutionSide.HOLD,
            price=0.0,
            quantity=0.0,
            confidence=90.0,
            decision="WAIT",
        )

    def _buy_plan(self) -> ExecutionPlan:
        return ExecutionPlan(
            symbol="BTCUSDT",
            side=ExecutionSide.BUY,
            price=100_000.0,
            quantity=1.0,
            confidence=90.0,
            decision="FAVORABLE",
        )

    def test_valid_buy_request_is_accepted(self) -> None:
        self.assertTrue(self.adapter.validate(self._request()))

    def test_nan_price_is_rejected(self) -> None:
        self.assertFalse(self.adapter.validate(self._request(price=math.nan)))

    def test_infinite_price_is_rejected(self) -> None:
        self.assertFalse(self.adapter.validate(self._request(price=math.inf)))

    def test_nan_quantity_is_rejected(self) -> None:
        self.assertFalse(self.adapter.validate(self._request(quantity=math.nan)))

    def test_infinite_quantity_is_rejected(self) -> None:
        self.assertFalse(self.adapter.validate(self._request(quantity=math.inf)))

    def test_non_finite_confidence_is_rejected(self) -> None:
        for confidence in (math.nan, math.inf, -math.inf):
            with self.subTest(confidence=confidence):
                request = self._request(confidence=confidence)
                self.assertFalse(self.adapter.validate(request))
                if math.isnan(confidence):
                    self.assertTrue(math.isnan(request.confidence))
                else:
                    self.assertEqual(request.confidence, confidence)

    def test_hold_nan_override_is_rejected(self) -> None:
        result = self.engine.execute(self._hold_plan(), quantity=math.nan)
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertIn("Quantity override", result.message)

    def test_hold_positive_infinity_override_is_rejected(self) -> None:
        result = self.engine.execute(self._hold_plan(), quantity=math.inf)
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertIn("Quantity override", result.message)

    def test_hold_negative_infinity_override_is_rejected(self) -> None:
        result = self.engine.execute(self._hold_plan(), quantity=-math.inf)
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertIn("Quantity override", result.message)

    def test_hold_zero_override_is_rejected(self) -> None:
        result = self.engine.execute(self._hold_plan(), quantity=0.0)
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertIn("Quantity override", result.message)

    def test_hold_negative_override_is_rejected(self) -> None:
        result = self.engine.execute(self._hold_plan(), quantity=-1.0)
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertIn("Quantity override", result.message)

    def test_valid_hold_without_override_is_unchanged(self) -> None:
        result = self.engine.execute(self._hold_plan())
        self.assertEqual(result.status, ExecutionStatus.SKIPPED)
        self.assertIsNone(result.request)

    def test_valid_buy_with_override_is_unchanged(self) -> None:
        result = self.engine.execute(self._buy_plan(), quantity=2.0)
        self.assertEqual(result.status, ExecutionStatus.EXECUTED)
        self.assertIsNotNone(result.request)
        self.assertEqual(result.request.quantity, 2.0)


if __name__ == "__main__":
    unittest.main()
