"""Developer 5 verification gates for the canonical ORION pipeline."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from core.dependency_container import ContainerConfiguration, DependencyContainer
from core.execution_plan_builder import ExecutionPlanBuilder
from engines.decision_engine import DecisionEngine
from enums import DataHealth, Timeframe
from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.execution import ExecutionPlan, ExecutionResult, ExecutionSide, ExecutionStatus
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics
from models.report import ReportResult
from models.score import ScoreResult


class TestVerificationGates(unittest.TestCase):
    """Executable verification gates; production semantics are not modified."""

    def setUp(self) -> None:
        self._temp_directory = tempfile.TemporaryDirectory()
        database_path = str(Path(self._temp_directory.name) / "orion_verification.db")
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
        timestamps = pd.date_range(end=now, periods=len(closes), freq="h", tz="UTC")
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
            source="VERIFICATION_FIXTURE",
            cache_version="1.0.0",
            downloaded_at=now,
            last_updated_at=now,
        )
        return MarketDataset(metadata=metadata, timeframes={Timeframe.H1: timeframe_data})

    @staticmethod
    def _assert_failure_evidence_report(
        report: ReportResult,
        execution: ExecutionResult,
    ) -> None:
        """A failure-evidence report may exist, but it can never imply success."""
        if not isinstance(report, ReportResult):
            raise AssertionError("Failure evidence must be represented by ReportResult when present.")
        if report.execution is not execution:
            raise AssertionError("Failure evidence must retain the exact failed ExecutionResult.")
        if report.execution.status is not ExecutionStatus.FAILED:
            raise AssertionError("Failure evidence report must explicitly retain FAILED execution status.")
        if report.execution.status is ExecutionStatus.EXECUTED:
            raise AssertionError("A failure evidence report must never imply execution success.")

    @staticmethod
    def _build_plan(dataset: MarketDataset, decision: DecisionResult) -> ExecutionPlan:
        plan = ExecutionPlanBuilder().build(dataset, decision)
        if plan is None:
            raise AssertionError("Expected a canonical ExecutionPlan.")
        return plan

    def test_execution_plan_isolated_from_upstream_pipeline_state(self) -> None:
        """ExecutionPlan carries execution intent only, not upstream result objects."""
        fields = set(ExecutionPlan.__dataclass_fields__)
        prohibited = {
            "dataset",
            "market_dataset",
            "analysis",
            "profile",
            "score",
            "decision",
            "orchestrator_result",
        }
        self.assertTrue(prohibited.isdisjoint(fields))

    def test_decision_to_execution_mapping_is_consistent_and_fail_closed(self) -> None:
        dataset = self._dataset()
        decision_engine = DecisionEngine()

        favorable = decision_engine.decide(
            AnalysisResult(market_state="BULLISH", strength=90.0, signals=["TREND_ALIGNED"]),
            ScoreResult(score=92.0, category="STRONG_BULLISH", factors=["STRONG_SCORE"]),
        )
        unfavorable = decision_engine.decide(
            AnalysisResult(market_state="BEARISH", strength=88.0, signals=["TREND_ALIGNED"]),
            ScoreResult(score=-88.0, category="STRONG_BEARISH", factors=["STRONG_SCORE_NEGATIVE"]),
        )
        wait = DecisionResult(decision="WAIT", confidence=50.0, reasons=["NEUTRAL"])
        unknown = DecisionResult(decision="UNSPECIFIED", confidence=0.0, reasons=["UNKNOWN"])

        self.assertEqual(self._build_plan(dataset, favorable).side, ExecutionSide.BUY)
        self.assertEqual(self._build_plan(dataset, unfavorable).side, ExecutionSide.SELL)
        self.assertEqual(self._build_plan(dataset, wait).side, ExecutionSide.HOLD)
        self.assertEqual(self._build_plan(dataset, unknown).side, ExecutionSide.NONE)

        engine = self.container.build_execution_engine()
        for decision in (wait, unknown):
            result = engine.execute(self._build_plan(dataset, decision))
            self.assertEqual(result.status, ExecutionStatus.SKIPPED)
            self.assertIsNone(result.order_id)

    def test_report_integrity_preserves_exact_upstream_contract_objects(self) -> None:
        analysis = AnalysisResult()
        profile = ProfileResult(
            symbol="BTCUSDT",
            market=MarketCharacteristics(),
            statistics=ProfileStatistics(),
            is_tradeable=True,
        )
        score = ScoreResult()
        decision = DecisionResult()
        execution = ExecutionResult(status=ExecutionStatus.SKIPPED, message="not executable")

        report = self.container.build_report_engine().build_report(
            symbol="BTCUSDT",
            analysis=analysis,
            profile=profile,
            score=score,
            decision=decision,
            execution=execution,
        )

        self.assertIs(report.analysis, analysis)
        self.assertIs(report.profile, profile)
        self.assertIs(report.score, score)
        self.assertIs(report.decision, decision)
        self.assertIs(report.execution, execution)
        self.assertTrue(report.is_complete)
        self.assertEqual(report.execution.status, ExecutionStatus.SKIPPED)

    def test_failure_evidence_report_is_explicitly_failed_not_successful(self) -> None:
        """ReportResult may carry failure evidence without becoming a success signal."""
        failed_execution = ExecutionResult(
            status=ExecutionStatus.FAILED,
            message="forced verification failure",
        )

        report = self.container.build_report_engine().build_report(
            symbol="BTCUSDT",
            analysis=AnalysisResult(),
            profile=ProfileResult(
                symbol="BTCUSDT",
                market=MarketCharacteristics(),
                statistics=ProfileStatistics(),
                is_tradeable=True,
            ),
            score=ScoreResult(),
            decision=DecisionResult(decision="FAVORABLE", confidence=92.0, reasons=["verification"]),
            execution=failed_execution,
            warnings=("execution failed; report is evidence only",),
        )

        self.assertTrue(report.is_complete)
        self.assertTrue(report.has_warnings)
        self._assert_failure_evidence_report(report, failed_execution)
        self.assertFalse(report.execution.executed)

    def test_real_pipeline_e2e_reaches_report_without_live_market_io(self) -> None:
        pipeline = self.container.build_pipeline()
        provider = self.container.build_market_data_provider()
        storage = self.container.build_market_storage()
        fixture = self._dataset()

        with patch.object(provider, "execute", return_value=fixture), patch.object(storage, "execute", return_value=None):
            result = pipeline.run_symbol("BTCUSDT", [Timeframe.H1.value], quantity=1.0)

        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)
        self.assertIsNotNone(result.orchestrator_result)
        self.assertIsNotNone(result.orchestrator_result.execution_plan)
        self.assertIsNotNone(result.execution_result)
        self.assertIsNotNone(result.report_result)
        assert result.orchestrator_result is not None
        assert result.execution_result is not None
        assert result.report_result is not None
        self.assertIsInstance(result.orchestrator_result.execution_plan, ExecutionPlan)
        self.assertIsInstance(result.execution_result, ExecutionResult)
        self.assertIsInstance(result.report_result, ReportResult)
        self.assertTrue(result.report_result.is_complete)
        self.assertIn(
            result.execution_result.status,
            (ExecutionStatus.EXECUTED, ExecutionStatus.SKIPPED),
        )
        self.assertIs(result.report_result.execution, result.execution_result)

    def test_invalid_input_fails_closed_before_execution(self) -> None:
        pipeline = self.container.build_pipeline()
        execution = MagicMock()
        pipeline._execution_engine = execution

        result = pipeline.run_symbol("", [Timeframe.H1.value])

        self.assertFalse(result.success)
        self.assertIsNone(result.execution_result)
        self.assertIsNone(result.report_result)
        execution.execute.assert_not_called()

    def test_execution_failure_is_observable_and_report_never_implies_success(self) -> None:
        """Verify the final failure contract without requiring report suppression."""
        pipeline = self.container.build_pipeline()
        failed_execution = ExecutionResult(
            status=ExecutionStatus.FAILED,
            message="forced execution failure",
        )
        failure_evidence = ReportResult(
            symbol="BTCUSDT",
            execution=failed_execution,
            warnings=("execution failed; evidence only",),
        )

        with patch.object(
            pipeline._orchestrator,
            "run",
            return_value=MagicMock(
                execution_plan=ExecutionPlan(
                    symbol="BTCUSDT",
                    side=ExecutionSide.BUY,
                    price=100_000.0,
                    quantity=1.0,
                )
            ),
        ), patch.object(
            pipeline._execution_engine,
            "execute",
            return_value=failed_execution,
        ), patch.object(
            pipeline._report_engine,
            "build_report",
            return_value=failure_evidence,
        ):
            result = pipeline.run_symbol("BTCUSDT", [Timeframe.H1.value], quantity=1.0)

        self.assertFalse(result.success)
        self.assertEqual(result.failed_stage, "EXECUTION")
        self.assertIs(result.execution_result, failed_execution)

        if result.report_result is not None:
            self._assert_failure_evidence_report(result.report_result, failed_execution)
        self.assertFalse(
            bool(result.report_result and result.report_result.execution and result.report_result.execution.executed),
            "A failure report must never imply execution success.",
        )


if __name__ == "__main__":
    unittest.main()
