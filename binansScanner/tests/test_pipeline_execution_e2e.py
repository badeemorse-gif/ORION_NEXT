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
from models.execution import ExecutionSide, ExecutionStatus
from models.market import MarketDataset, MarketMetadata, TimeframeData


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
        timestamps = pd.date_range(
            end=pd.Timestamp(now),
            periods=60,
            freq="h",
            tz="UTC",
        )
        closes = [100_000.0 + float(index * 100.0) for index in range(60)]
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

    def test_container_pipeline_executes_buy_and_builds_report(self) -> None:
        """Real container graph reaches PaperExecutionAdapter and ReportEngine."""
        dataset = self._dataset()
        provider = self.container.build_market_data_provider()
        storage = self.container.build_market_storage()
        pipeline = self.container.build_pipeline()

        with patch.object(provider, "execute", return_value=dataset), patch.object(
            storage, "execute", return_value=None
        ):
            result = pipeline.run_symbol("BTCUSDT", [Timeframe.H1.value])

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

        self.assertEqual(plan.side, ExecutionSide.BUY)
        self.assertEqual(execution.status, ExecutionStatus.EXECUTED)
        self.assertTrue(execution.executed)
        self.assertTrue(execution.has_order_id)
        self.assertTrue(execution.order_id.startswith("PAPER-ORD-"))
        self.assertEqual(execution.request.side, ExecutionSide.BUY)
        self.assertIs(report.execution, execution)
        self.assertTrue(report.is_complete)


if __name__ == "__main__":
    unittest.main()
