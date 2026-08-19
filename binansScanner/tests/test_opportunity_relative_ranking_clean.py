import unittest
from datetime import datetime, timezone

import pandas as pd

from enums import DataHealth, Timeframe
from engines.opportunity_relative_ranking import OpportunityRankingInput, OpportunityRelativeRanker
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.opportunity import FreshnessStatus, Opportunity, OpportunityDirection, OpportunityRisk, OpportunityStatus, RiskState
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile
from models.score import ScoreResult


class TestCleanRelativeRanking(unittest.TestCase):
    _FREQ = {Timeframe.M5: "5min", Timeframe.M15: "15min"}

    def _input(
        self,
        *,
        symbol="BTCUSDT",
        score=100.0,
        volume_last=20.0,
        volume_baseline=10.0,
        volatility=2.0,
        liquidity=100.0,
        momentum="Buy",
        trend="Bullish",
        ema_alignment="Bullish",
        phase="Markup",
        timeframe="5m",
        direction=OpportunityDirection.LONG,
    ):
        now = datetime(2026, 8, 17, tzinfo=timezone.utc)
        tf = Timeframe(timeframe)
        close = [100.0, 100.5, 101.0, 101.5]
        volume = [volume_baseline, volume_baseline, volume_baseline, volume_last]
        frame = pd.DataFrame(
            {"open": close, "high": [x + 1 for x in close], "low": [x - 1 for x in close], "close": close, "volume": volume},
            index=pd.date_range("2026-08-17", periods=4, freq=self._FREQ[tf], tz="UTC"),
        )
        dataset = MarketDataset(
            metadata=MarketMetadata(symbol=symbol, exchange="TEST", source="TEST", cache_version="1", downloaded_at=now, last_updated_at=now, is_valid=True)
        )
        dataset.add_timeframe(TimeframeData(timeframe=tf, dataframe=frame, data_health=DataHealth.GOOD, candles_count=4, first_timestamp=now, last_timestamp=now))
        profile_tf = TimeframeProfile(
            timeframe=timeframe,
            characteristics=MarketCharacteristics(
                trend=trend, ema_alignment=ema_alignment, momentum=momentum, volatility=volatility,
                volatility_level="Normal", risk_level="Medium", confidence=90.0,
            ),
            candles_count=4, first_timestamp=now, last_timestamp=now,
        )
        profile = ProfileResult(
            symbol=symbol,
            market=MarketCharacteristics(trend=trend, market_phase=phase, liquidity=liquidity, confidence=90.0),
            statistics=ProfileStatistics(completion_ratio=1.0, total_candles=4),
            timeframes=(profile_tf,), is_tradeable=True, generated_at=now,
        )
        opportunity = Opportunity(
            symbol=symbol, timeframe=timeframe, direction=direction, entry_candidate=101.5,
            confidence=90.0, setup_quality=None, risk=OpportunityRisk(state=RiskState.ACCEPTABLE),
            freshness=FreshnessStatus.FRESH, status=OpportunityStatus.ACTIVE, supporting_evidence=("signal",),
        )
        return OpportunityRankingInput(opportunity=opportunity, score=ScoreResult(score=score, category="BULLISH" if direction is OpportunityDirection.LONG else "BEARISH"), profile=profile, dataset=dataset)

    def test_equal_raw_scores_separate_by_context(self):
        ranked = OpportunityRelativeRanker().rank((
            self._input(symbol="A", volume_last=10, liquidity=10, momentum="Neutral", trend="Sideways", ema_alignment="None", phase="Range"),
            self._input(symbol="B", volume_last=30, liquidity=1000, momentum="Strong Buy"),
        ))
        by_symbol = {x.opportunity.symbol: x for x in ranked}
        self.assertEqual(by_symbol["A"].raw_score, 100.0)
        self.assertEqual(by_symbol["B"].raw_score, 100.0)
        self.assertGreater(by_symbol["B"].context_score, by_symbol["A"].context_score)
        self.assertGreater(by_symbol["B"].composite_score, by_symbol["A"].composite_score)
        self.assertEqual(by_symbol["B"].relative_rank, 1)
        self.assertEqual(by_symbol["A"].relative_rank, 2)

    def test_percentile_is_cohort_relative(self):
        ranked = OpportunityRelativeRanker().rank((
            self._input(symbol="A", volume_last=10, liquidity=10),
            self._input(symbol="B", volume_last=20, liquidity=50),
            self._input(symbol="C", volume_last=40, liquidity=90),
        ))
        p = {x.opportunity.symbol: x.percentile for x in ranked}
        self.assertGreater(p["C"], p["B"])
        self.assertGreater(p["B"], p["A"])

    def test_cohort_is_timeframe_and_direction(self):
        ranked = OpportunityRelativeRanker().rank((
            self._input(symbol="A", timeframe="5m", direction=OpportunityDirection.LONG),
            self._input(symbol="B", timeframe="5m", direction=OpportunityDirection.LONG),
            self._input(symbol="C", timeframe="15m", direction=OpportunityDirection.LONG),
            self._input(symbol="D", timeframe="5m", direction=OpportunityDirection.SHORT, momentum="Strong Sell", trend="Bearish", ema_alignment="Bearish", phase="Markdown"),
        ))
        peer_counts = {x.opportunity.symbol: x.peer_count for x in ranked}
        self.assertEqual(peer_counts, {"A": 2, "B": 2, "C": 1, "D": 1})

    def test_short_supportive_momentum_scores_high(self):
        ranked = OpportunityRelativeRanker().rank((self._input(direction=OpportunityDirection.SHORT, momentum="Strong Sell", trend="Bearish", ema_alignment="Bearish", phase="Markdown"),))
        self.assertEqual(ranked[0].context.momentum, 100.0)

    def test_single_member_cohort_has_no_false_relative_precision(self):
        ranked = OpportunityRelativeRanker().rank((self._input(),))[0]
        self.assertIsNone(ranked.relative_rank)
        self.assertIsNone(ranked.percentile)

    def test_missing_volume_is_deterministically_rejected(self):
        item = self._input()
        frame = item.dataset.get_timeframe(Timeframe.M5)
        self.assertIsNotNone(frame)
        frame.dataframe.drop(columns=["volume"], inplace=True)
        with self.assertRaises(ValueError):
            OpportunityRelativeRanker().rank((item,))

    def test_ranking_does_not_change_opportunity_contract_state(self):
        item = self._input()
        before = item.opportunity
        ranked = OpportunityRelativeRanker().rank((item,))[0]
        self.assertIs(ranked.opportunity, before)
        self.assertIsNone(ranked.opportunity.setup_quality)
        self.assertEqual(ranked.opportunity.status, OpportunityStatus.ACTIVE)
        self.assertEqual(ranked.opportunity.freshness, FreshnessStatus.FRESH)


if __name__ == "__main__":
    unittest.main()
