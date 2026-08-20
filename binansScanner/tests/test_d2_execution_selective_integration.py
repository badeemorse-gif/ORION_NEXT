"""D2 selective integration contracts for Execution only."""
from __future__ import annotations

import math
import unittest

from core.dependency_container import ContainerConfiguration, ContainerError, DependencyContainer
from core.execution_plan_builder import ExecutionPlanBuilder
from engines.execution_engine import ExecutionEngine, PaperExecutionAdapter
from models.decision import DecisionResult
from models.execution import ExecutionPlan, ExecutionRequest, ExecutionSide, ExecutionStatus


class TestD2SelectiveExecutionIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = PaperExecutionAdapter()
        self.engine = ExecutionEngine(self.adapter)
        self.builder = ExecutionPlanBuilder()

    def test_disabled_paper_fails_closed_without_live_fallback(self) -> None:
        container = DependencyContainer(ContainerConfiguration(paper_trading_enabled=False))
        try:
            with self.assertRaises(ContainerError):
                container.build_execution_engine()
            self.assertIsNone(container._execution_adapter_instance)
            self.assertIsNone(container._execution_engine_instance)
        finally:
            container.reset()

    def test_credentials_do_not_change_paper_adapter(self) -> None:
        container = DependencyContainer(
            ContainerConfiguration(
                paper_trading_enabled=True,
                binance_api_key="unused-paper-key",
                binance_api_secret="unused-paper-secret",
                binance_testnet=False,
            )
        )
        try:
            engine = container.build_execution_engine()
            self.assertIsInstance(engine._adapter, PaperExecutionAdapter)
        finally:
            container.reset()

    def test_wait_maps_to_hold_zero_quantity_and_skipped(self) -> None:
        decision = DecisionResult(
            decision="WAIT",
            confidence=50.0,
            reasons=["NEUTRAL_OR_MIXED_CONDITIONS"],
        )
        plan = self.builder.build(None, None)
        self.assertIsNone(plan)

        # Exercise the canonical builder/engine contract with a minimal dataset.
        from datetime import datetime, timezone
        import pandas as pd
        from enums import DataHealth, Timeframe
        from models.market import MarketDataset, MarketMetadata, TimeframeData

        now = datetime.now(timezone.utc)
        dataset = MarketDataset(
            metadata=MarketMetadata(
                symbol="BTCUSDT",
                exchange="BINANCE",
                source="BINANCE_API",
                cache_version="1.0.0",
                downloaded_at=now,
                last_updated_at=now,
            ),
            timeframes={
                Timeframe.H1: TimeframeData(
                    timeframe=Timeframe.H1,
                    dataframe=pd.DataFrame({"close": [100_000.0]}),
                    data_health=DataHealth.GOOD,
                    candles_count=1,
                    first_timestamp=now,
                    last_timestamp=now,
                )
            },
        )
        plan = self.builder.build(dataset, decision)
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.side, ExecutionSide.HOLD)
        self.assertEqual(plan.quantity, 0.0)
        result = self.engine.execute(plan)
        self.assertEqual(result.status, ExecutionStatus.SKIPPED)

    def test_unknown_decision_is_rejected(self) -> None:
        from datetime import datetime, timezone
        import pandas as pd
        from enums import DataHealth, Timeframe
        from models.market import MarketDataset, MarketMetadata, TimeframeData

        now = datetime.now(timezone.utc)
        dataset = MarketDataset(
            metadata=MarketMetadata(
                symbol="BTCUSDT",
                exchange="BINANCE",
                source="BINANCE_API",
                cache_version="1.0.0",
                downloaded_at=now,
                last_updated_at=now,
            ),
            timeframes={
                Timeframe.H1: TimeframeData(
                    timeframe=Timeframe.H1,
                    dataframe=pd.DataFrame({"close": [100_000.0]}),
                    data_health=DataHealth.GOOD,
                    candles_count=1,
                    first_timestamp=now,
                    last_timestamp=now,
                )
            },
        )
        with self.assertRaisesRegex(ValueError, "Unsupported execution decision: UNSPECIFIED"):
            self.builder.build(dataset, DecisionResult("UNSPECIFIED", 50.0, ["UNKNOWN_DECISION"]))

    def test_non_finite_execution_values_are_rejected(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                request = ExecutionRequest("BTCUSDT", ExecutionSide.BUY, value, 1.0, 90.0)
                self.assertFalse(self.adapter.validate(request))
                self.assertEqual(
                    self.engine.execute(
                        ExecutionPlan("BTCUSDT", ExecutionSide.BUY, value, 1.0, 90.0, decision="FAVORABLE")
                    ).status,
                    ExecutionStatus.FAILED,
                )

    def test_decision_side_mismatch_is_rejected(self) -> None:
        plan = ExecutionPlan(
            symbol="BTCUSDT",
            side=ExecutionSide.SELL,
            price=100_000.0,
            quantity=1.0,
            confidence=90.0,
            decision="FAVORABLE",
        )
        result = self.engine.execute(plan)
        self.assertEqual(result.status, ExecutionStatus.FAILED)

    def test_invalid_quantity_override_is_rejected_before_hold_shortcut(self) -> None:
        hold = ExecutionPlan(
            symbol="BTCUSDT",
            side=ExecutionSide.HOLD,
            price=0.0,
            quantity=0.0,
            confidence=90.0,
            decision="WAIT",
        )
        for value in (math.nan, math.inf, -math.inf, 0.0, -1.0):
            with self.subTest(value=value):
                self.assertEqual(self.engine.execute(hold, quantity=value).status, ExecutionStatus.FAILED)

    def test_executable_buy_and_sell_remain_unchanged(self) -> None:
        for side, decision in ((ExecutionSide.BUY, "FAVORABLE"), (ExecutionSide.SELL, "UNFAVORABLE")):
            with self.subTest(side=side):
                result = self.engine.execute(
                    ExecutionPlan(
                        symbol="BTCUSDT",
                        side=side,
                        price=100_000.0,
                        quantity=1.0,
                        confidence=90.0,
                        decision=decision,
                    )
                )
                self.assertEqual(result.status, ExecutionStatus.EXECUTED)
                self.assertEqual(result.request.side, side)


if __name__ == "__main__":
    unittest.main()
