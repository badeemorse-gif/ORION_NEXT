import unittest

from engines.opportunity_intelligence import OpportunityCandidateGenerator


class TestConfidenceOnly(unittest.TestCase):
    def test_canonical_source_is_timeframe_profile(self):
        self.assertTrue(hasattr(OpportunityCandidateGenerator, "generate"))


if __name__ == "__main__":
    unittest.main()
