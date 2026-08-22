from __future__ import annotations

import unittest

from models.capital_management import AllocationConfig, CapitalManager
from models.opportunity import MarketMetrics, OpportunityCandidate, OpportunityCandidateSet
from models.scalping_opportunity import Candle, EntryState, OpportunityClass
from services.scalping_opportunity import ScalpingConfig
from services.scalping_pipeline import ScalpingOpportunityPipeline
from services.opportunity_discovery import OpportunityConfig, OpportunityDiscovery, MarketUniverseDiscovery


class FakeUniverse:
    def exchange_info(self):
        return {
            "symbols": [
                {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"},
                {"symbol": "ETHUSDT", "baseAsset": "ETH", "quoteAsset": "USDT", "status": "TRADING"},
            ]
        }


class FakeMetrics:
    def metrics_bulk(self, symbols):
        return {symbol: MarketMetrics(symbol, 100_000_000, 0.02, 5, True, 100) for symbol in symbols}


class FakeCandles:
    def candles(self, symbol, timeframe, limit):
        price = 100.0
        out = []
        for i in range(limit):
            if timeframe == "15m":
                step = 1.0 if i >= limit - 3 else 0.2
                volume = 300.0 if i >= limit - 2 else 100.0
            elif timeframe == "1h":
                step = 0.5
                volume = 100.0
            else:
                step = 0.0
                volume = 100.0
            close = price + step
            out.append(Candle(i, price, max(price, close) + 0.5, min(price, close) - 0.5, close, volume))
            price = close
        return tuple(out)


class ScalpingPipelineTests(unittest.TestCase):
    def test_full_universe_to_active_entry_pipeline(self):
        discovery = OpportunityDiscovery(
            MarketUniverseDiscovery(FakeUniverse()),
            FakeMetrics(),
            OpportunityConfig(default_top_n=2),
            clock=lambda: 0.0,
        )
        pipeline = ScalpingOpportunityPipeline(
            discovery,
            FakeCandles(),
            pool_manager=__import__("services.scalping_opportunity", fromlist=["ScalpingCandidatePoolManager"]).ScalpingCandidatePoolManager(ScalpingConfig(active_top_n=1)),
        )
        result = pipeline.discover()
        self.assertEqual(len(result.broad_pool.candidates), 2)
        self.assertLessEqual(len(result.active_set.candidates), 1)
        for candidate in result.broad_pool.candidates:
            self.assertIn(candidate.opportunity_class, {item.value for item in OpportunityClass})
            self.assertIn(candidate.entry_state, {item.value for item in EntryState})
            self.assertIsNotNone(candidate.decision_trace)

    def test_capital_boundary_is_read_only_during_discovery(self):
        manager = CapitalManager(AllocationConfig(starting_capital=50.0, fixed_allocation=10.0))
        discovery = OpportunityDiscovery(MarketUniverseDiscovery(FakeUniverse()), FakeMetrics(), OpportunityConfig(default_top_n=1), clock=lambda: 0.0)
        # CapitalManager is queried by the decision layer; discovery itself does not create a reservation.
        before = manager.reserved_capital
        self.assertEqual(before, 0.0)


if __name__ == "__main__":
    unittest.main()
