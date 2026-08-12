"""Execution boundary validation contracts."""

from __future__ import annotations

import math
import unittest

from engines.execution_engine import PaperExecutionAdapter
from models.execution import ExecutionRequest, ExecutionSide


class TestExecutionValidationContract(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = PaperExecutionAdapter()

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


if __name__ == "__main__":
    unittest.main()
