"""
===============================================================================
ORION
Module : tests.test_decision_execution_bridge
Status : Canonical Decision -> ExecutionPlan -> Paper Execution contract
===============================================================================

Verifies the production decision engine, canonical execution-plan bridge, and
real paper execution boundary without network access or live exchange calls.
===============================================================================
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

import pandas as pd

from core.dependency_container import DependencyContainer
from core.orchestrator import Orchestrator
from engines.decision_engine import DecisionEngine
from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.score import ScoreResult
from enums import DataHealth, Timeframe
from models.execution import ExecutionSide, ExecutionStatus


class TestDecisionExecutionBridge(unittest.TestCase):
    """Validate the canonical decision-to-execution boundary."""

    def setUp(self) -> None:
        self.container = DependencyContainer()
        self.execution_engine = self.container.build_execution_engine()
        self.decision_engine = DecisionEngine()

        now = datetime.now(timezone.utc)
        dataframe = pd.DataFrame(
            {
                "open": [99_000.0],
                "high": [101_000.0],
                "low": [98_500.0],
                "close": [100_000.0],
                "volume": [1_000.0],
            }
        )
        timeframe_data = TimeframeData(
            timeframe=Timeframe.H1,
            dataframe=dataframe,
            data_health=DataHealth.GOOD,
            candles_count=1,
            first_timestamp=now,
            last_timestamp=now,
        )
        metadata = MarketMetadata(
            symbol="BTCUSDT",
            exchange="BINANCE",
            source="BINANCE_API",
            cache_version="1.0.0",
            downloaded_at=now,
            last_updated_at=now,
        )
        self.dataset = MarketDataset(
            metadata=metadata,
            timeframes={Timeframe.H1: timeframe_data},
        )

    def tearDown(self) -> None:
        self.container.reset()

    def test_favorable_decision_becomes_buy_and_executes(self) -> None:
        decision = self.decision_engine.decide(
            AnalysisResult(
                market_state="BULLISH",
                strength=90.0,
                signals=["TREND_ALIGNED"],
            ),
            ScoreResult(
                score=92.0,
                category="STRONG_BULLISH",
                factors=["STRONG_SCORE"],
            ),
        )

        self.assertEqual(decision.decision, "FAVORABLE")
        self.assertEqual(decision.confidence, 92.0)

        plan = Orchestrator._build_execution_plan(self.dataset, decision)
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.side, ExecutionSide.BUY)
        self.assertEqual(plan.price, 100_000.0)
        self.assertEqual(plan.quantity, 1.0)
        self.assertEqual(plan.confidence, 92.0)

        result = self.execution_engine.execute(plan)

        self.assertEqual(result.status, ExecutionStatus.EXECUTED)
        self.assertTrue(result.executed)
        self.assertTrue(result.has_order_id)
        self.assertTrue(result.order_id.startswith("PAPER-ORD-"))
        self.assertEqual(result.request.side, ExecutionSide.BUY)

    def test_unfavorable_decision_becomes_sell_and_executes(self) -> None:
        decision = self.decision_engine.decide(
            AnalysisResult(
                market_state="BEARISH",
                strength=88.0,
                signals=["TREND_ALIGNED"],
            ),
            ScoreResult(
                score=-88.0,
                category="STRONG_BEARISH",
                factors=["STRONG_SCORE_NEGATIVE"],
            ),
        )

        self.assertEqual(decision.decision, "UNFAVORABLE")
        self.assertEqual(decision.confidence, 88.0)

        plan = Orchestrator._build_execution_plan(self.dataset, decision)
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.side, ExecutionSide.SELL)
        self.assertEqual(plan.price, 100_000.0)
        self.assertEqual(plan.quantity, 1.0)
        self.assertEqual(plan.confidence, 88.0)

        result = self.execution_engine.execute(plan)

        self.assertEqual(result.status, ExecutionStatus.EXECUTED)
        self.assertTrue(result.executed)
        self.assertTrue(result.has_order_id)
        self.assertTrue(result.order_id.startswith("PAPER-ORD-"))
        self.assertEqual(result.request.side, ExecutionSide.SELL)

    def test_wait_decision_becomes_hold_and_is_skipped(self) -> None:
        decision = DecisionResult(
            decision="WAIT",
            confidence=50.0,
            reasons=["NEUTRAL_OR_MIXED_CONDITIONS"],
        )

        plan = Orchestrator._build_execution_plan(self.dataset, decision)
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.side, ExecutionSide.HOLD)

        result = self.execution_engine.execute(plan)

        self.assertEqual(result.status, ExecutionStatus.SKIPPED)
        self.assertFalse(result.executed)
        self.assertIsNone(result.order_id)


if __name__ == "__main__":
    unittest.main()
