# Opportunity Confidence Contract Fix

Opportunity confidence is sourced only from the canonical `ProfileResult.TimeframeProfile.confidence` for the requested timeframe.

`AnalysisResult.strength` is a distinct Core signal and is not treated as Opportunity confidence.

No aggregation formula, threshold, or synthetic confidence is introduced.

When canonical timeframe Profile confidence is unavailable, Opportunity confidence remains unavailable and the existing fail-closed Selection/TradingReadiness boundaries apply.
