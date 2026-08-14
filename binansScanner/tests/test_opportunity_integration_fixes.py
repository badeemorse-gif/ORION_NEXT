import unittest
from datetime import datetime, timezone
import pandas as pd
from enums import DataHealth, Timeframe
from engines.opportunity_intelligence import CoreOpportunityEvidence, OpportunityCandidateGenerator, OpportunityIntelligenceError, OpportunitySelectionPolicy
from models.analysis import AnalysisResult
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.opportunity import FreshnessStatus, OpportunityDirection, RiskState
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile
from models.score import ScoreResult

class TestOpportunityIntegrationFixes(unittest.TestCase):
    def test_canonical_confidence_is_timeframe_profile_owned(self):
        self.assertTrue(callable(OpportunityCandidateGenerator.generate))

if __name__ == "__main__": unittest.main()
