"""Developer 5 verification gates for the canonical ORION pipeline."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from core.dependency_container import ContainerConfiguration, DependencyContainer
from core.orchestrator import Orchestrator
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
        closes = [100_000.0 + float(index * 100.0) for index in range(60)]
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

    def test_execution_plan_isolated_from_upstream_pipeline_state(self) -> None:
        fields = set(ExecutionPlan.__dataclass_fields__)
        prohibited = {"dataset", "market_dataset", "analysis", "profile", "score", "decision", "orchestrator_result"}
        self.assertTrue(fields.isdisjoint(prohibited))
        self.assertNotIn("MarketDataset", str(ExecutionPlan.__annotations__))

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

        self.assertEqual(Orchestrator._build_execution_plan(dataset, favorable).side, ExecutionSide.BUY)
        self.assertEqual(Orchestrator._build_execution_plan(dataset, unfavorable).side, ExecutionSide.SELL)
        self.assertEqual(Orchestrator._build_execution_plan(dataset, wait).side, ExecutionSide.HOLD)
        self.assertEqual(Orchestrator._build_execution_plan(dataset, unknown).side, ExecutionSide.NONE)

        engine = self.container.build_execution_engine()
        for decision in (wait, unknown):
            result = engine.execute(Orchestrator._build_execution_plan(dataset, decision))
            self.assertEqual(result.status, ExecutionStatus.SKIPPED)
            self.assertIsNone(result.order_id)

    def test_report_integrity_preserves_exact_upstream_contract_objects(self) -> None:
        analysis = AnalysisResult()
        profile = ProfileResult(
            symbol="BTCUSDT",
            market=MarketCharacteristics(),
            statistics=ProfileStatistics(),
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
        self.assertIsNotNone(result.execution_result)
        self.assertIsNotNone(result.report_result)
        assert result.orchestrator_result is not None
        assert result.execution_result is not None
        assert result.report_result is not None
        self.assertIsInstance(result.orchestrator_result.execution_payload, ExecutionPlan)
        self.assertIsInstance(result.execution_result, ExecutionResult)
        self.assertIsInstance(result.report_result, ReportResult)
        self.assertTrue(result.report_result.is_complete)

    def test_invalid_input_fails_closed_before_execution(self) -> None:
        pipeline = self.container.build_pipeline()
        execution = MagicMock()
        pipeline._execution_engine = execution

        result = pipeline.run_symbol("", [Timeframe.H1.value])

        self.assertFalse(result.success)
        self.assertIsNone(result.execution_result)
        self.assertIsNone(result.report_result)
        execution.execute.assert_not_called()

    def test_execution_failure_is_a_hard_verification_gate(self) -> None:
        """Expose the current production defect instead of masking it.

        Pipeline currently treats an ExecutionResult(FAILED) as a successful
        pipeline item and still builds a report. This assertion is deliberately
        strict so CI cannot certify the fail-closed contract until the Pipeline
        owner corrects that production behavior.
        """
        pipeline = self.container.build_pipeline()
        failed_execution = ExecutionResult(
            status=ExecutionStatus.FAILED,
            message="forced verification failure",
        )

        with patch.object(pipeline._orchestrator, "run", return_value=MagicMock(execution_payload=ExecutionPlan(symbol="BTCUSDT", side=ExecutionSide.BUY, price=100_000.0, quantity=1.0))), patch.object(
            pipeline._execution_engine,
            "execute",
            return_value=failed_execution,
        ), patch.object(pipeline._report_engine, "build_report") as report_builder:
            result = pipeline.run_symbol("BTCUSDT", [Timeframe.H1.value], quantity=1.0)

        self.assertFalse(
            result.success,
            "FAIL-CLOSED GATE: Pipeline must not report success after ExecutionStatus.FAILED.",
        )
        report_builder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
