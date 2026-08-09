import inspect
import unittest
from datetime import datetime, timezone

from engines.profile_engine import ProfileEngine
from models.market import MarketDataset, MarketMetadata
from models.profile import ProfileResult


class TestProfileContract(unittest.TestCase):
    def _empty_dataset(self) -> MarketDataset:
        metadata = MarketMetadata(
            symbol="BTCUSDT",
            exchange="BINANCE",
            source="TEST",
            cache_version="TEST",
            downloaded_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
            is_valid=True,
        )
        return MarketDataset(metadata=metadata)

    def test_profile_engine_exposes_canonical_result_boundary(self):
        method = getattr(ProfileEngine, "build_profile", None)

        self.assertIsNotNone(
            method,
            "ProfileEngine must expose build_profile().",
        )

        signature = inspect.signature(method)

        self.assertIn("dataset", signature.parameters)

    def test_profile_engine_returns_profile_result_for_empty_dataset(self):
        engine = ProfileEngine()
        dataset = self._empty_dataset()

        result = engine.build_profile(dataset)

        self.assertIsInstance(result, ProfileResult)
        self.assertEqual(result.symbol, "BTCUSDT")

    def test_profile_result_does_not_require_market_dataset(self):
        fields = {
            field.name
            for field in getattr(ProfileResult, "__dataclass_fields__", {}).values()
        }

        self.assertNotIn("dataset", fields)
        self.assertNotIn("market_dataset", fields)

    def test_profile_engine_does_not_store_profile_on_market_dataset(self):
        engine = ProfileEngine()
        dataset = self._empty_dataset()

        engine.build_profile(dataset)

        self.assertFalse(
            hasattr(dataset, "profile"),
            "MarketDataset must not contain ProfileResult state.",
        )

    def test_profile_engine_does_not_store_profile_state_on_timeframe_data(self):
        engine = ProfileEngine()
        dataset = self._empty_dataset()

        engine.build_profile(dataset)

        for timeframe_data in dataset.timeframes.values():
            self.assertFalse(hasattr(timeframe_data, "profile"))
            self.assertFalse(hasattr(timeframe_data, "profile_ready"))


if __name__ == "__main__":
    unittest.main()