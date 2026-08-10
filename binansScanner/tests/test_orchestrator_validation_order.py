"""Contract tests for the canonical market validation/persistence order."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock

import pandas as pd

from core.orchestrator import Orchestrator, OrchestratorConfig, PipelineError, PipelineStage
from enums import DataHealth, Timeframe
from models.market import MarketDataset, MarketMetadata, TimeframeData


class TestOrchestratorValidationOrder(TestCase):
    def _dataset(self) -> MarketDataset:
        now = datetime.now(timezone.utc)
        dataframe = pd.DataFrame(
            {"open": [100.0], "high": [101.0], "low": [99.0], "close": [100.5], "volume": [10.0]},
            index=pd.DatetimeIndex([now], name="timestamp"),
        )
        return MarketDataset(
            metadata=MarketMetadata(
                symbol="BTCUSDT", exchange="BINANCE", source="TEST", cache_version="1.0.0",
                downloaded_at=now, last_updated_at=now,
            ),
            timeframes={
                Timeframe.M1: TimeframeData(
                    timeframe=Timeframe.M1, dataframe=dataframe,
                    data_health=DataHealth.ACCEPTABLE, candles_count=1,
                    first_timestamp=now, last_timestamp=now,
                )
            },
        )

    def _orchestrator(self, provider: MagicMock, storage: MagicMock, validation: MagicMock) -> Orchestrator:
        return Orchestrator(
            provider=provider, storage=storage,
            indicator_engine=MagicMock(), analysis_engine=MagicMock(), profile_engine=MagicMock(),
            score_engine=MagicMock(), decision_engine=MagicMock(), validation_engine=validation,
            config=OrchestratorConfig(ENABLE_TIMING=False),
        )

    def test_invalid_dataset_is_never_persisted(self) -> None:
        """Validation must reject provider output before the storage boundary is reached."""
        dataset = self._dataset()
        provider = MagicMock()
        provider.execute.return_value = dataset
        storage = MagicMock()
        validation = MagicMock()
        validation.validate_dataset.side_effect = ValueError("invalid market data")
        orchestrator = self._orchestrator(provider, storage, validation)

        with self.assertRaises(PipelineError):
            orchestrator.run_pipeline("BTCUSDT", ["1m"])

        validation.validate_dataset.assert_called_once_with(dataset)
        storage.execute.assert_not_called()
        self.assertEqual(orchestrator.statistics().current_stage, PipelineStage.VALIDATION)

    def test_valid_dataset_is_persisted_after_validation(self) -> None:
        """A valid dataset reaches storage only after successful validation."""
        dataset = self._dataset()
        provider = MagicMock()
        provider.execute.return_value = dataset
        storage = MagicMock()
        validation = MagicMock()
        validation.validate_dataset.return_value = MagicMock()

        indicator = MagicMock()
        indicator.calculate_dataset.return_value = dataset
        analysis = MagicMock()
        analysis.analyze.return_value = MagicMock()
        profile = MagicMock()
        profile.build_profile.return_value = MagicMock()
        score = MagicMock()
        score.calculate.return_value = MagicMock()
        decision = MagicMock()
        decision_result = MagicMock()
        decision_result.decision = "WAIT"
        decision_result.confidence = 50.0
        decision_result.reasons = ["test"]
        decision.decide.return_value = decision_result

        orchestrator = Orchestrator(
            provider=provider, storage=storage, indicator_engine=indicator,
            analysis_engine=analysis, profile_engine=profile, score_engine=score,
            decision_engine=decision, validation_engine=validation,
            config=OrchestratorConfig(ENABLE_TIMING=False),
        )

        result = orchestrator.run_pipeline("BTCUSDT", ["1m"])

        validation.validate_dataset.assert_called_once_with(dataset)
        storage.execute.assert_called_once_with(dataset)
        self.assertTrue(result.statistics.success)
        self.assertEqual(result.statistics.current_stage, PipelineStage.FINISHED)


if __name__ == "__main__":
    import unittest
    unittest.main()
