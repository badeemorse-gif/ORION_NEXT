"""ORION Composition Root Execution -> Report E2E contract tests."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from core.dependency_container import ContainerConfiguration, DependencyContainer
from enums import DataHealth, Timeframe
from models.decision import DecisionResult
from models.execution import ExecutionResult, ExecutionSide, ExecutionStatus
from models.market import MarketDataset, MarketMetadata, TimeframeData


class TestPipelineExecutionE2E(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_directory = tempfile.TemporaryDirectory()
        self.container = DependencyContainer(
            ContainerConfiguration(
                database_path=str(Path(self._temp_directory.name) / "orion_e2e.db"),
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
            symbol="BTCUSDT", exchange="BINANCE", source="E2E_FIXTURE",
            cache_version="1.0.0", downloaded_at=now, last_updated_at=now,
        )
        return MarketDataset(metadata=metadata, timeframes={Timeframe.H1: timeframe_data})

    def _run_with_real_market_stages(self, decision: DecisionResult | None = None):
        dataset = self._dataset()
        provider = self.container.build_market_data_provider()
        storage = self.container.build_market_storage()
        pipeline = self.container.build_pipeline()
        decision_patch = (
            patch.object(pipeline._orchestrator._decision_engine, "decide", return_value=decision)
            if decision is not None
            else patch.object(pipeline._orchestrator._decision_engine, "decide", wraps=pipeline._orchestrator._decision_engine.decide)
        )
        with patch.object(provider, "execute", return_value=dataset), patch.object(storage, "execute", return_value=None), decision_patch:
            return pipeline.run_symbol("BTCUSDT", [Timeframe.H1.value], quantity=1.0)

    def test_successful_execution_report_is_complete(self) -> None:
        result = self._run_with_real_market_stages(DecisionResult(decision="FAVORABLE", confidence=0.95, reasons=["E2E executable decision"]))
        self.assertTrue(result.success)
        self.assertIsNotNone(result.report_result)
        assert result.report_result is not None
        self.assertEqual(result.execution_result.status, ExecutionStatus.EXECUTED)
        self.assertEqual(result.report_result.audit.status.value, "COMPLETE")
        self.assertEqual(result.report_result.audit.execution_status, ExecutionStatus.EXECUTED)
        self.assertEqual(result.report_result.audit.decision_reasons, ("E2E executable decision",))

    def test_skipped_execution_report_is_complete(self) -> None:
        result = self._run_with_real_market_stages()
        self.assertTrue(result.success)
        self.assertIsNotNone(result.report_result)
        assert result.report_result is not None
        self.assertEqual(result.execution_result.status, ExecutionStatus.SKIPPED)
        self.assertEqual(result.orchestrator_result.execution_plan.side, ExecutionSide.HOLD)
        self.assertEqual(result.report_result.audit.status.value, "COMPLETE")
        self.assertEqual(result.report_result.audit.execution_status, ExecutionStatus.SKIPPED)

    def test_execution_failure_is_reported_as_failed_not_success(self) -> None:
        pipeline = self.container.build_pipeline()
        execution_failure = ExecutionResult(status=ExecutionStatus.FAILED, message="forced execution failure")
        with patch.object(
            pipeline._orchestrator,
            "run",
            return_value=MagicMock(execution_plan=MagicMock(), analysis=None, profile=None, score=None, decision=None, statistics=MagicMock(elapsed_ms=0.0)),
        ), patch.object(pipeline._execution_engine, "execute", return_value=execution_failure):
            result = pipeline.run_symbol("BTCUSDT", [Timeframe.H1.value], quantity=1.0)
        self.assertFalse(result.success)
        self.assertEqual(result.failed_stage, "EXECUTION")
        self.assertIsNotNone(result.report_result)
        assert result.report_result is not None
        self.assertEqual(result.report_result.audit.status.value, "FAILED")
        self.assertEqual(result.report_result.audit.execution_status, ExecutionStatus.FAILED)
        self.assertEqual(result.report_result.audit.failure_stage, "EXECUTION")
        self.assertEqual(result.report_result.audit.stage_trace, ("ORCHESTRATION", "EXECUTION", "REPORT"))

    def test_orchestration_failure_builds_failure_evidence(self) -> None:
        pipeline = self.container.build_pipeline()
        last_result = MagicMock(
            execution_plan=None,
            analysis=None,
            profile=None,
            score=None,
            decision=None,
            statistics=MagicMock(elapsed_ms=0.0),
        )
        with patch.object(pipeline._orchestrator, "run", side_effect=RuntimeError("orchestration exploded")), patch.object(
            pipeline._orchestrator, "last_result", return_value=last_result
        ):
            result = pipeline.run_symbol("BTCUSDT", [Timeframe.H1.value], quantity=1.0)
        self.assertFalse(result.success)
        self.assertEqual(result.failed_stage, "ORCHESTRATION")
        self.assertIsNotNone(result.report_result)
        assert result.report_result is not None
        self.assertEqual(result.report_result.audit.status.value, "FAILED")
        self.assertIsNone(result.report_result.audit.execution_status)
        self.assertEqual(result.report_result.audit.failure_stage, "ORCHESTRATION")
        self.assertEqual(result.report_result.audit.failure_message, "orchestration exploded")
        self.assertEqual(result.report_result.audit.stage_trace, ("ORCHESTRATION", "REPORT"))


if __name__ == "__main__":
    unittest.main()
