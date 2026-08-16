import unittest
from datetime import datetime, timezone

import pandas as pd

from engines.opportunity_relative_ranking import OpportunityRankingInput, OpportunityRelativeRanker
from enums import DataHealth, Timeframe
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.opportunity import (
    FreshnessStatus,
    Opportunity,
    OpportunityDirection,
    OpportunityRisk,
    OpportunityStatus,
    RiskState,
)
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile
from models.score import ScoreResult


class TestOpportunityRelativeRanking(unittest.TestCase):
    _PANDAS_FREQ = {
        Timeframe.M1: "1min",
        Timeframe.M5: "5min",
        Timeframe.M15: "15min",
        Timeframe.H1: "1h",
        Timeframe.H4: "4h",
        Timeframe.D1: "1D",
    }

    def _input(
        self,
        *,
        symbol: str,
        score: float = 100.0,
        volume_last: float = 20.0,
        volume_baseline: float = 10.0,
        volatility: float = 2.0,
        liquidity: float = 100.0,
        momentum: str = "Buy",
        trend: str = "Bullish",
        ema_alignment: str = "Bullish",
        market_phase: str = "Markup",
        timeframe: str = "5m",
        direction: OpportunityDirection = OpportunityDirection.LONG,
    ) -> OpportunityRankingInput:
        now = datetime(2026, 8, 17, tzinfo=timezone.utc)
        selected_timeframe = Timeframe(timeframe)
        values = [volume_baseline, volume_baseline, volume_baseline, volume_last]
        close = [100.0, 100.5, 101.0, 101.5]
        frame = pd.DataFrame(
            {
                "open": close,
                "high": [v + 1 for v in close],
                "low": [v - 1 for v in close],
                "close": close,
                "volume": values,
            },
            index=pd.date_range(
                "2026-08-17 00:00",
                periods=4,
                freq=self._PANDAS_FREQ[selected_timeframe],
                tz="UTC",
            ),
        )
        dataset = MarketDataset(
            metadata=MarketMetadata(
                symbol=symbol,
                exchange="BINANCE",
                source="TEST",
                cache_version="TEST",
                downloaded_at=now,
                last_updated_at=now,
                is_valid=True,
            )
        )
        dataset.add_timeframe(
            TimeframeData(
                timeframe=selected_timeframe,
                dataframe=frame,
                data_health=DataHealth.GOOD,
                candles_count=len(frame),
                first_timestamp=frame.index[0].to_pydatetime(),
                last_timestamp=frame.index[-1].to_pydatetime(),
            )
        )
        timeframe_profile = TimeframeProfile(
            timeframe=timeframe,
            characteristics=MarketCharacteristics(
                trend=trend,
                ema_alignment=ema_alignment,
                momentum=momentum,
                volatility=volatility,
                volatility_level="Normal",
                risk_level="Medium",
                confidence=90.0,
            ),
            candles_count=4,
            first_timestamp=now,
            last_timestamp=now,
        )
        profile = ProfileResult(
            symbol=symbol,
            market=MarketCharacteristics(
                trend=trend,
                market_phase=market_phase,
                liquidity=liquidity,
                confidence=90.0,
            ),
            statistics=ProfileStatistics(completion_ratio=1.0, total_candles=4),
            timeframes=(timeframe_profile,),
            is_tradeable=True,
            generated_at=now,
        )
        opportunity = Opportunity(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            entry_candidate=101.5,
            confidence=90.0,
            setup_quality=None,
            risk=OpportunityRisk(state=RiskState.ACCEPTABLE),
            freshness=FreshnessStatus.FRESH,
            status=OpportunityStatus.ACTIVE,
            supporting_evidence=("signal",),
        )
        return OpportunityRankingInput(
            opportunity=opportunity,
            score=ScoreResult(
                score=score,
                category="BULLISH" if direction is OpportunityDirection.LONG else "BEARISH",
            ),
            profile=profile,
            dataset=dataset,
        )

    def test_raw_ties_are_broken_by_context(self) -> None:
        inputs = (
            self._input(
                symbol="AAAUSDT",
                volume_last=10.0,
                liquidity=10.0,
                momentum="Neutral",
                trend="Sideways",
                ema_alignment="None",
                market_phase="Range",
            ),
            self._input(symbol="BBBUSDT", volume_last=30.0, liquidity=1000.0, momentum="Strong Buy"),
        )
        ranked = OpportunityRelativeRanker().rank(inputs)
        by_symbol = {item.opportunity.symbol: item for item in ranked}
        self.assertEqual({item.raw_score for item in ranked}, {100.0})
        self.assertNotEqual(by_symbol["AAAUSDT"].composite_score, by_symbol["BBBUSDT"].composite_score)
        self.assertGreater(by_symbol["BBBUSDT"].composite_score, by_symbol["AAAUSDT"].composite_score)
        self.assertEqual(by_symbol["BBBUSDT"].relative_rank, 1)
        self.assertEqual(by_symbol["AAAUSDT"].relative_rank, 2)

    def test_relative_percentile_is_cohort_based(self) -> None:
        ranked = OpportunityRelativeRanker().rank(
            (
                self._input(symbol="A", volume_last=10.0, liquidity=10.0),
                self._input(symbol="B", volume_last=20.0, liquidity=50.0),
                self._input(symbol="C", volume_last=40.0, liquidity=90.0),
            )
        )
        percentiles = {item.opportunity.symbol: item.relative_percentile for item in ranked}
        self.assertGreater(percentiles["C"], percentiles["B"])
        self.assertGreater(percentiles["B"], percentiles["A"])
        self.assertEqual({item.peer_count for item in ranked}, {3})

    def test_same_timeframe_and_direction_form_the_peer_cohort(self) -> None:
        ranked = OpportunityRelativeRanker().rank(
            (
                self._input(symbol="A", timeframe="5m", direction=OpportunityDirection.LONG),
                self._input(symbol="B", timeframe="5m", direction=OpportunityDirection.LONG),
                self._input(symbol="C", timeframe="15m", direction=OpportunityDirection.LONG),
                self._input(symbol="D", timeframe="5m", direction=OpportunityDirection.SHORT, momentum="Strong Sell"),
            )
        )
        peer_counts = {item.opportunity.symbol: item.peer_count for item in ranked}
        self.assertEqual(peer_counts["A"], 2)
        self.assertEqual(peer_counts["B"], 2)
        self.assertEqual(peer_counts["C"], 1)
        self.assertEqual(peer_counts["D"], 1)

    def test_short_momentum_is_directionally_inverted(self) -> None:
        long_ranked = OpportunityRelativeRanker().rank((self._input(symbol="L", momentum="Strong Buy"),))[0]
        short_ranked = OpportunityRelativeRanker().rank(
            (self._input(symbol="S", momentum="Strong Sell", direction=OpportunityDirection.SHORT),)
        )[0]
        self.assertEqual(long_ranked.context.momentum_score, 100.0)
        self.assertEqual(short_ranked.context.momentum_score, 100.0)

    def test_ranking_does_not_mutate_opportunity_contract_state(self) -> None:
        item = self._input(symbol="AAA")
        before = item.opportunity
        before_complete = before.is_complete
        ranked = OpportunityRelativeRanker().rank((item,))[0]
        self.assertIs(ranked.opportunity, before)
        self.assertEqual(ranked.opportunity.is_complete, before_complete)
        self.assertIsNone(ranked.opportunity.setup_quality)
        self.assertEqual(ranked.opportunity.status, OpportunityStatus.ACTIVE)
        self.assertEqual(ranked.opportunity.freshness, FreshnessStatus.FRESH)

    def test_missing_volume_history_is_rejected_for_ranking(self) -> None:
        item = self._input(symbol="AAA")
        timeframe = item.dataset.get_timeframe(Timeframe.M5)
        assert timeframe is not None
        timeframe.dataframe.drop(columns=["volume"], inplace=True)
        with self.assertRaises(ValueError):
            OpportunityRelativeRanker().rank((item,))


if __name__ == "__main__":
    unittest.main()
