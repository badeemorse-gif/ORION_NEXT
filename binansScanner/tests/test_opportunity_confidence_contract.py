import unittest
from datetime import datetime, timezone
import pandas as pd
from enums import DataHealth, Timeframe
from engines.opportunity_intelligence import CoreOpportunityEvidence, OpportunityCandidateGenerator
from models.analysis import AnalysisResult
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile
from models.score import ScoreResult

class TestOpportunityConfidenceContract(unittest.TestCase):
    def _evidence(self, strength, confidence):
        now=datetime.now(timezone.utc)
        ds=MarketDataset(metadata=MarketMetadata(symbol="BTCUSDT",exchange="TEST",source="TEST",cache_version="TEST",downloaded_at=now,last_updated_at=now,is_valid=True))
        ds.add_timeframe(TimeframeData(timeframe=Timeframe.M5,dataframe=pd.DataFrame({"close":[100.0,101.0]}),data_health=DataHealth.GOOD,candles_count=2,first_timestamp=now,last_timestamp=now))
        tp=TimeframeProfile(timeframe="5m",characteristics=MarketCharacteristics(trend="Bullish",ema_alignment="Bullish",momentum="Buy",volatility_level="Normal",risk_level="Medium",confidence=confidence),candles_count=2,first_timestamp=now,last_timestamp=now)
        p=ProfileResult(symbol="BTCUSDT",market=MarketCharacteristics(trend="Sideways",confidence=5.0),statistics=ProfileStatistics(completion_ratio=1.0,total_candles=2),timeframes=(tp,),is_tradeable=True,generated_at=now)
        return CoreOpportunityEvidence(ds,AnalysisResult(market_state="BULLISH",strength=strength,signals=("EMA_ALIGNMENT_BULLISH",)),p,ScoreResult(score=40.0,category="BULLISH",factors=("EMA_ALIGNMENT_BULLISH",)),"5m")
    def test_profile_confidence_is_canonical(self):
        e=self._evidence(10.0,80.0); c=OpportunityCandidateGenerator().generate(e).opportunities[0]; self.assertEqual(c.confidence,80.0)
    def test_analysis_strength_is_not_confidence(self):
        e=self._evidence(95.0,30.0); c=OpportunityCandidateGenerator().generate(e).opportunities[0]; self.assertEqual(c.confidence,30.0); self.assertNotEqual(c.confidence,e.analysis.strength)
if __name__ == "__main__": unittest.main()
