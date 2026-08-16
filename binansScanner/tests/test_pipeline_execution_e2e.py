"""ORION Composition Root decision -> execution -> report E2E contract."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pandas as pd

from core.dependency_container import ContainerConfiguration, DependencyContainer
from enums import DataHealth, Timeframe
from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.execution import ExecutionPlan, ExecutionResult, ExecutionSide, ExecutionStatus
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile
from models.report import ReportResult
from models.score import ScoreResult


class TestPipelineExecutionE2E(unittest.TestCase):
    """Validate the real Composition Root application path end-to-end."""

    def setUp(self) -> None:
        self._temp_directory = tempfile.TemporaryDirectory()
        database_path = str(Path(self._temp_directory.name) / "orion_e2e.db")
        self.container = DependencyContainer(
            ContainerConfiguration(
                database_path=database_path,
                binance_api_key="",
                binance_api_secret="",
                binance_testnet=True,
            )
        )

    def tearDown(self) -> None:
        self.container.reset()
        self._temp_directory.cleanup()

    @staticmethod
    def _timeframe_data(timeframe: Timeframe, now: datetime) -> TimeframeData:
        closes = [100_000.0 + float(index * 100.0) for index in range(250)]
        timestamps = pd.date_range(
            end=now,
            periods=len(closes),
            freq="h",
            tz="UTC",
        )
        dataframe = pd.DataFrame(
            {
                "open": [value - 50.0 for value in closes],
                "high": [value + 100.0 for value in closes],
                "low": [value - 100.0 for value in closes],
                "close": closes,
                "volume": [1_000.0] * len(closes),
            },
            index=timestamps,
        )
        return TimeframeData(
            timeframe=timeframe,
            dataframe=dataframe,
            data_health=DataHealth.GOOD,
            candles_count=len(dataframe),
            first_timestamp=now - timedelta(hours=len(dataframe) - 1),
            last_timestamp=now,
        )

    @staticmethod
    def _dataset() -> MarketDataset:
        now = datetime.now(timezone.utc)
        metadata = MarketMetadata(
            symbol="BTCUSDT",
            exchange="BINANCE",
            source="E2E_FIXTURE",
            cache_version="1.0.0",
            downloaded_at=now,
            last_updated_at=now,
        )
        return MarketDataset(
            metadata=metadata,
            timeframes={
                Timeframe.D1: TestPipelineExecutionE2E._timeframe_data(Timeframe.D1, now),
                Timeframe.H4: TestPipelineExecutionE2E._timeframe_data(Timeframe.H4, now),
                Timeframe.H1: TestPipelineExecutionE2E._timeframe_data(Timeframe.H1, now),
            },
        )

    @staticmethod
    def _valid_profile() -> ProfileResult:
        now = datetime.now(timezone.utc)
        timeframes = tuple(
            TimeframeProfile(
                timeframe=timeframe.value,
                characteristics=MarketCharacteristics(),
                candles_count=250,
                first_timestamp=now - timedelta(hours=249),
                last_timestamp=now,
                data_health=DataHealth.GOOD,
                missing_candles=0,
                warnings=(),
            )
            for timeframe in (Timeframe.D1, Timeframe.H4, Timeframe.H1)
        )
        return ProfileResult(
            symbol="BTCUSDT",
            market=MarketCharacteristics(),
            statistics=ProfileStatistics(
                completion_ratio=1.0,
                total_candles=750,
                missing_candles=0,
            ),
            timeframes=timeframes,
            is_tradeable=True,
            warnings=(),
            blocks=(),
        )

    @staticmethod
    def _assert_failure_evidence_report(report: ReportResult, execution: ExecutionResult) -> None:
        assert report.execution is execution
        assert report.execution.status is ExecutionStatus.FAILED
        assert not report.execution.executed

    @staticmethod
    def _canonical_favorable_analysis() -> AnalysisResult:
        return AnalysisResult(
            market_state="BULLISH",
            strength=100.0,
            signals=[
                "EMA_ALIGNMENT_BULLISH",
                "MOMENTUM_POSITIVE",
                "STRONG_TREND",
            ],
            warnings=[],
        )

    @staticmethod
    def _canonical_favorable_score() -> ScoreResult:
        return ScoreResult(
            score=60.0,
            category="STRONG_BULLISH",
            factors=["CANONICAL_FAVORABLE_E2E_FIXTURE"],
            warnings=[],
        )

    def _run_with_real_market_stages(
        self,
        decision: DecisionResult | None = None,
        *,
        quantity: Optional[float] = None,
    ):
        dataset = self._dataset()
        provider = self.container.build_market_data_provider()
        storage = self.container.build_market_storage()
        pipeline = self.container.build_pipeline()
        profile_engine = pipeline._orchestrator._profile_engine

        patches = [
            patch.object(provider, "execute", return_value=dataset),
            patch.object(storage, "execute", return_value=None),
            patch.object(profile_engine, "build_profile", return_value=self._valid_profile()),
        ]

        if decision is not None and decision.decision == "FAVORABLE":
            patches.extend(
                [
                    patch.object(
                        pipeline._orchestrator._analysis_engine,
                        "analyze",
                        return_value=self._canonical_favorable_analysis(),
                    ),
                    patch.object(
                        pipeline._orchestrator._score_engine,
                        "calculate",
                        return_value=self._canonical_favorable_score(),
                    ),
                ]
            )

        with patches[0], patches[1], patches[2]:
            if len(patches) == 5:
                with patches[3], patches[4]:
                    return pipeline.run_symbol(
                        "BTCUSDT",
                        [Timeframe.H1.value],
                        quantity=quantity,
                    )
            return pipeline.run_symbol(
                "BTCUSDT",
                [Timeframe.H1.value],
                quantity=quantity,
            )

    def test_container_pipeline_reaches_execution_and_builds_report(self) -> None:
        """WAIT reaches HOLD with canonical quantity semantics and is skipped with a complete report."""
        result = self._run_with_real_market_stages(
            DecisionResult(
                decision="WAIT",
                confidence=0.0,
                reasons=["E2E WAIT fixture"],
            ),
            quantity=None,
        )

        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)
        self.assertIsNotNone(result.orchestrator_result)
        self.assertIsNotNone(result.orchestrator_result.execution_plan)
        self.assertIsNotNone(result.execution_result)
        self.assertIsNotNone(result.report_result)

        plan = result.orchestrator_result.execution_plan
        execution = result.execution_result
        report = result.report_result
        assert plan is not None
        assert execution is not None
        assert report is not None

        self.assertEqual(result.orchestrator_result.decision.decision, "WAIT")
        self.assertEqual(result.orchestrator_result.decision.confidence, 0.0)
        self.assertEqual(plan.side, ExecutionSide.HOLD)
        self.assertEqual(plan.quantity, 0.0)
        self.assertEqual(execution.status, ExecutionStatus.SKIPPED)
        self.assertFalse(execution.executed)
        self.assertIsNone(execution.order_id)
        self.assertIs(report.execution, execution)
        self.assertTrue(report.is_complete)

    def test_container_pipeline_executes_favorable_decision_end_to_end(self) -> None:
        """Canonical bullish analysis/score fixtures must yield FAVORABLE through the real DecisionEngine."""
        result = self._run_with_real_market_stages(
            DecisionResult(
                decision="FAVORABLE",
                confidence=60.0,
                reasons=["CANONICAL_FAVORABLE_E2E_FIXTURE"],
            ),
            quantity=1.0,
        )

        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)
        self.assertIsNotNone(result.orchestrator_result)
        self.assertIsNotNone(result.execution_result)
        self.assertIsNotNone(result.report_result)

        plan = result.orchestrator_result.execution_plan
        execution = result.execution_result
        report = result.report_result
        assert plan is not None
        assert execution is not None
        assert report is not None

        self.assertEqual(result.orchestrator_result.analysis.market_state, "BULLISH")
        self.assertEqual(result.orchestrator_result.score.category, "STRONG_BULLISH")
        self.assertGreaterEqual(result.orchestrator_result.score.score, 60.0)
        self.assertEqual(result.orchestrator_result.decision.decision, "FAVORABLE")
        self.assertEqual(plan.side, ExecutionSide.BUY)
        self.assertEqual(execution.status, ExecutionStatus.EXECUTED)
        self.assertTrue(execution.executed)
        self.assertIsNotNone(execution.order_id)
        self.assertTrue(execution.order_id.startswith("PAPER-"))
        self.assertIs(report.execution, execution)
        self.assertTrue(report.is_complete)

    def test_execution_failure_is_observable_and_failure_report_is_never_success(self) -> None:
        """Execution FAILED must fail the pipeline; failure evidence may still be returned."""
        pipeline = self.container.build_pipeline()
        execution_failure = ExecutionResult(
            status=ExecutionStatus.FAILED,
            message="forced execution failure",
        )
        failure_evidence = ReportResult(
            symbol="BTCUSDT",
            execution=execution_failure,
            warnings=("execution failed; evidence only",),
        )

        with patch.object(
            pipeline._orchestrator,
            "run",
            return_value=type(
                "OrchestratorFixture",
                (),
                {
                    "execution_plan": ExecutionPlan(
                        symbol="BTCUSDT",
                        side=ExecutionSide.BUY,
                        price=100_000.0,
                        quantity=1.0,
                    ),
                    "analysis": None,
                    "profile": None,
                    "score": None,
                    "decision": None,
                    "statistics": type("Stats", (), {"elapsed_ms": 0.0})(),
                },
            )(),
        ), patch.object(
            pipeline._execution_engine,
            "execute",
            return_value=execution_failure,
        ), patch.object(
            pipeline._report_engine,
            "build_report",
            return_value=failure_evidence,
        ):
            result = pipeline.run_symbol("BTCUSDT", [Timeframe.H1.value], quantity=1.0)

        self.assertFalse(result.success)
        self.assertEqual(result.failed_stage, "EXECUTION")
        self.assertIs(result.execution_result, execution_failure)

        if result.report_result is not None:
            self.assertIs(result.report_result, failure_evidence)
            self._assert_failure_evidence_report(result.report_result, execution_failure)

        self.assertFalse(
            bool(
                result.report_result
                and result.report_result.execution
                and result.report_result.execution.executed
            )
        )


if __name__ == "__main__":
    unittest.main()
