from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from app.application import OrionApplication
from core.pipeline import PipelineItemResult, PipelineSummary


class TestApplicationFacadeContract(unittest.TestCase):
    def test_run_symbols_returns_pipeline_summary(self) -> None:
        application = OrionApplication()
        pipeline = Mock()
        summary = PipelineSummary(
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            elapsed_ms=1.0,
            processed_symbols=2,
            successful_symbols=2,
            failed_symbols=0,
            execution_count=1,
            success=True,
        )
        pipeline.run_symbols.return_value = (
            summary,
            [
                PipelineItemResult(symbol="BTCUSDT", success=True),
                PipelineItemResult(symbol="ETHUSDT", success=True),
            ],
        )
        application._pipeline = pipeline
        application._container = Mock()
        application._is_running = True

        result = application.run_symbols(
            symbols=(symbol for symbol in ("BTCUSDT", "ETHUSDT")),
            timeframes=["1h", "4h"],
            quantity=1.0,
        )

        self.assertIs(result, summary)
        pipeline.run_symbols.assert_called_once_with(
            symbols=["BTCUSDT", "ETHUSDT"],
            timeframes=["1h", "4h"],
            quantity=1.0,
        )

    def test_summary_reads_last_pipeline_summary(self) -> None:
        application = OrionApplication()
        pipeline = Mock()
        summary = PipelineSummary(processed_symbols=1, successful_symbols=1, success=True)
        pipeline.statistics.return_value = summary
        application._pipeline = pipeline

        self.assertIs(application.summary(), summary)
        pipeline.statistics.assert_called_once_with()

    def test_reset_clears_pipeline_summary_without_rebuilding_application(self) -> None:
        application = OrionApplication()
        pipeline = Mock()
        container = Mock()
        application._pipeline = pipeline
        application._container = container
        application._is_running = True

        application.reset()

        pipeline.reset.assert_called_once_with()
        container.reset.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
