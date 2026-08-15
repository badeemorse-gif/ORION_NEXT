"""ORION Composition Root decision -> execution -> report E2E contract."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from core.dependency_container import ContainerConfiguration, DependencyContainer
from enums import DataHealth, Timeframe
from models.decision import DecisionResult
from models.execution import ExecutionPlan, ExecutionResult, ExecutionSide, ExecutionStatus
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics
from models.report import ReportResult


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
    def _dataset() -> MarketDataset:
        now = datetime.now(timezone.utc)
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
        timeframe_data = TimeframeData(
            timeframe=Timeframe.H1,
            dataframe=dataframe,
            data_health=DataHealth.GOOD,
            candles_count=len(dataframe),
            first_timestamp=now - timedelta(hours=len(dataframe) - 1),
            last_timestamp=now,
        )
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
            timeframes={Timeframe.H1: timeframe_data},
        )

    @staticmethod
    def _valid_profile() -> ProfileResult:
        return ProfileResult(
            symbol="BTCUSDT",
            market=MarketCharacteristics(),
            statistics=ProfileStatistics(),
            is_tradeable=True,
            warnings=(),
            blocks=(),
        )

    @staticmethod
    def _assert_failure_evidence_report(report: ReportResult, execution: ExecutionResult) -> None:
        assert report.execution is execution
        assert report.execution.status is ExecutionStatus.FAILED
        assert not report.execution.executed

    def _run_with_real_market_stages(
        self,
        decision: DecisionResult | None = None,
    ):
        dataset = self._dataset()
        provider = self.container.build_market_data_provider()
        storage = self.container.build_market_storage()
        pipeline = self.container.build_pipeline()
        profile_engine = pipeline._orchestrator._profile_engine

        decision_patch = (
            patch.object(pipeline._orchestrator._decision_engine, "decide", return_value=decision)
            if decision is not None
            else patch.object(
                pipeline._orchestrator._decision_engine,
                "decide",
                wraps=pipeline._orchestrator._decision_engine.decide,
            )
        )

        with patch.object(provider, "execute", return_value=dataset), patch.object(
            storage, "execute", return_value=None
        ), patch.object(profile_engine, "build_profile", return_value=self._valid_profile()), decision_patch:
            return pipeline.run_symbol("BTCUSDT", [Timeframe.H1.value], quantity=1.0)

    def test_container_pipeline_reaches_execution_and_builds_report(self) -> None:
        """Real container graph reaches execution and ReportEngine with the real decision."""
        result = self._run_with_real_market_stages()

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
        self.assertEqual(plan.side, ExecutionSide.HOLD)
        self.assertEqual(execution.status, ExecutionStatus.SKIPPED)
        self.assertFalse(execution.executed)
        self.assertIsNone(execution.order_id)
        self.assertIs(report.execution, execution)
        self.assertTrue(report.is_complete)

    def test_container_pipeline_executes_favorable_decision_end_to_end(self) -> None:
        """A favorable real-orchestrator decision must execute through PaperExecutionAdapter."""
        result = self._run_with_real_market_stages(
            DecisionResult(
                decision="FAVORABLE",
                confidence=0.95,
                reasons=["E2E executable decision"],
            )
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
