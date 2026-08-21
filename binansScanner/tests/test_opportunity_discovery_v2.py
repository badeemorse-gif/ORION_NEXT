from __future__ import annotations

import math
import unittest

from models.opportunity import MarketMetrics
from providers.binance_opportunity_source import BinanceSpotOpportunitySource
from services.opportunity_discovery import (
    MarketEligibilityFilter, MarketUniverseDiscovery, OpportunityConfig,
    OpportunityDiscovery, OpportunityRanker, OpportunityScorer,
)


class Universe:
    def __init__(self, rows): self.rows = rows; self.calls = 0
    def exchange_info(self): self.calls += 1; return {"symbols": self.rows}


class BulkMetrics:
    def __init__(self, data): self.data = data; self.bulk_calls = 0; self.single_calls = 0
    def metrics_bulk(self, symbols): self.bulk_calls += 1; return {s: self.data[s] for s in symbols if s in self.data}
    def metrics(self, symbol): self.single_calls += 1; return self.data[symbol]


class Clock:
    def __init__(self): self.value = 0.0
    def __call__(self): return self.value


class D1V2Tests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"symbol":"BTCUSDT","baseAsset":"BTC","quoteAsset":"USDT","status":"TRADING","isSpotTradingAllowed":True},
            {"symbol":"ETHUSDT","baseAsset":"ETH","quoteAsset":"USDT","status":"TRADING","isSpotTradingAllowed":True},
            {"symbol":"USDCUSDT","baseAsset":"USDC","quoteAsset":"USDT","status":"TRADING","isSpotTradingAllowed":True},
            {"symbol":"BADUSDT","baseAsset":"BAD","quoteAsset":"USDT","status":"BREAK","isSpotTradingAllowed":True},
            {"symbol":"BTCEUR","baseAsset":"BTC","quoteAsset":"EUR","status":"TRADING","isSpotTradingAllowed":True},
            {"symbol":"NO_SPOT","baseAsset":"X","quoteAsset":"USDT","status":"TRADING","isSpotTradingAllowed":False},
        ]
        self.data = {
            "BTCUSDT": MarketMetrics("BTCUSDT", 200e6, .03, 3, True, 100000, .9, .9, .8, .9),
            "ETHUSDT": MarketMetrics("ETHUSDT", 100e6, .03, 5, True, 3000, .8, .7, .7, .8),
        }

    def test_dynamic_universe_exclusion(self):
        result = MarketUniverseDiscovery(Universe(self.rows)).discover()
        self.assertEqual(tuple(x.symbol for x in result), ("BTCUSDT", "ETHUSDT"))

    def test_bulk_efficiency(self):
        source = BulkMetrics(self.data)
        clock = Clock()
        discovery = OpportunityDiscovery(MarketUniverseDiscovery(Universe(self.rows)), source, OpportunityConfig(default_top_n=2, refresh_interval_seconds=10), clock)
        discovery.discover()
        self.assertEqual(source.bulk_calls, 1)
        self.assertEqual(source.single_calls, 0)
        discovery.discover()
        self.assertEqual(source.bulk_calls, 1)
        clock.value = 11
        discovery.discover()
        self.assertEqual(source.bulk_calls, 2)

    def test_rejection_fail_closed(self):
        candidate = MarketUniverseDiscovery(Universe([self.rows[0]])).discover()[0]
        filt = MarketEligibilityFilter(OpportunityConfig(min_quote_volume_24h=1e6, min_volatility=.01, max_volatility=.1, max_spread_bps=10))
        result = filt.evaluate(candidate, MarketMetrics("BTCUSDT", math.nan, .03, 5, True, -1))
        self.assertFalse(result.eligible)
        self.assertIn("INVALID_VOLUME", result.reasons)
        self.assertIn("INVALID_PRICE", result.reasons)

    def test_rich_components_affect_score(self):
        scorer = OpportunityScorer(OpportunityConfig())
        weak = scorer.score(MarketMetrics("X", 100e6, .03, 5, True, 1, .5, .1, .1, .1))
        strong = scorer.score(MarketMetrics("X", 100e6, .03, 5, True, 1, .5, .9, .9, .9))
        self.assertGreater(strong, weak)
        self.assertLessEqual(strong, 100)

    def test_bulk_market_fields_contribute_without_extra_requests(self):
        scorer = OpportunityScorer(OpportunityConfig())
        neutral = scorer.score(MarketMetrics("X", 100e6, .03, 5, True, 100, None, None, None, None, 0.0, 100))
        moving = scorer.score(MarketMetrics("X", 100e6, .03, 5, True, 110, None, None, None, None, 8.0, 100))
        self.assertGreater(moving, neutral)

    def test_score_determinism_and_bounds(self):
        m = MarketMetrics("X", 100e6, .03, 5, True, 1, .8, .8, .8, .8)
        scorer = OpportunityScorer(OpportunityConfig())
        self.assertEqual(scorer.score(m), scorer.score(m))
        self.assertGreaterEqual(scorer.score(m), 0)
        self.assertLessEqual(scorer.score(m), 100)

    def test_ranking_and_top_n(self):
        candidates = MarketUniverseDiscovery(Universe(self.rows[:2])).discover()
        ranker = OpportunityRanker(config=OpportunityConfig(default_top_n=1))
        out = ranker.rank(candidates, self.data)
        self.assertEqual(out.symbols(), ("BTCUSDT",))
        self.assertEqual(out.candidates[0].rank, 1)
        self.assertTrue(out.candidates[0].score_components)

    def test_near_tie_hysteresis_prefers_incumbent(self):
        rows = [self.rows[0], self.rows[1]]
        candidates = MarketUniverseDiscovery(Universe(rows)).discover()
        cfg = OpportunityConfig(hysteresis_score_delta=5.0, default_top_n=2)
        ranker = OpportunityRanker(config=cfg)
        first = ranker.rank(candidates, self.data)
        altered = dict(self.data)
        altered["ETHUSDT"] = MarketMetrics("ETHUSDT", 200e6, .03, 3, True, 3000, .9, .9, .8, .9)
        altered["BTCUSDT"] = MarketMetrics("BTCUSDT", 200e6, .03, 3, True, 100000, .9, .86, .8, .9)
        second = ranker.rank(candidates, altered)
        self.assertEqual(first.symbols(), second.symbols())

    def test_malformed_optional_feature_rejects(self):
        candidate = MarketUniverseDiscovery(Universe([self.rows[0]])).discover()[0]
        result = MarketEligibilityFilter().evaluate(candidate, MarketMetrics("BTCUSDT", 2e6, .03, 5, True, 1, 2.0))
        self.assertFalse(result.eligible)
        self.assertIn("INVALID_VOLUME_QUALITY", result.reasons)

    def test_dynamic_universe_refresh(self):
        source = Universe(self.rows[:2])
        metrics = BulkMetrics(self.data)
        clock = Clock()
        discovery = OpportunityDiscovery(MarketUniverseDiscovery(source), metrics, OpportunityConfig(refresh_interval_seconds=10), clock)
        discovery.discover()
        source.rows.append({"symbol":"SOLUSDT","baseAsset":"SOL","quoteAsset":"USDT","status":"TRADING","isSpotTradingAllowed":True})
        metrics.data["SOLUSDT"] = MarketMetrics("SOLUSDT", 300e6, .03, 2, True, 150, .9, .95, .9, .9)
        self.assertNotIn("SOLUSDT", discovery.discover().symbols())
        clock.value = 11
        self.assertIn("SOLUSDT", discovery.discover().symbols())

    def test_end_to_end_contract(self):
        source = BulkMetrics(self.data)
        output = OpportunityDiscovery(MarketUniverseDiscovery(Universe(self.rows)), source, OpportunityConfig(default_top_n=2)).discover()
        self.assertEqual(len(output.candidates), 2)
        self.assertEqual(tuple(c.rank for c in output.candidates), (1, 2))
        self.assertTrue(all(math.isfinite(c.opportunity_score) for c in output.candidates))


class SourceTests(unittest.TestCase):
    def test_bulk_endpoint_contract_and_cache(self):
        calls=[]
        source=BinanceSpotOpportunitySource(ttl_seconds=30, clock=lambda:0)
        payloads={
            'exchangeInfo': {'symbols': [{'symbol':'BTCUSDT','status':'TRADING','baseAsset':'BTC','quoteAsset':'USDT','isSpotTradingAllowed':True}]},
            'ticker/24hr': [{'symbol':'BTCUSDT','lastPrice':'100','quoteVolume':'200000000','priceChangePercent':'3','weightedAvgPrice':'99'}],
            'ticker/bookTicker': [{'symbol':'BTCUSDT','bidPrice':'99.9','askPrice':'100.1'}],
        }
        source._get_json=lambda path: (calls.append(path) or payloads[path])
        self.assertEqual(source.exchange_info()['symbols'][0]['symbol'],'BTCUSDT')
        result=source.metrics_bulk(['BTCUSDT'])
        self.assertEqual(result['BTCUSDT'].quote_volume_24h,200000000)
        self.assertAlmostEqual(result['BTCUSDT'].spread_bps,20.0,places=5)
        self.assertEqual(result['BTCUSDT'].price_change_pct_24h,3.0)
        source.metrics_bulk(['BTCUSDT'])
        self.assertEqual(calls,['exchangeInfo','ticker/24hr','ticker/bookTicker'])

    def test_malformed_rows_fail_closed(self):
        source=BinanceSpotOpportunitySource(clock=lambda:0)
        source._get_json=lambda path: [] if path != 'ticker/24hr' else [{'symbol':'BTCUSDT','lastPrice':'bad','quoteVolume':'1','priceChangePercent':'1','weightedAvgPrice':'1'}]
        self.assertEqual(source.metrics_bulk(['BTCUSDT']),{})


if __name__ == "__main__":
    unittest.main()
