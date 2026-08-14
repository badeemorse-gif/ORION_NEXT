"""Cross-layer Core Intelligence contract enforcement.

This module validates semantic boundaries between Indicator, Analysis,
Profile, Score and Decision without changing their domain architecture.
"""

from __future__ import annotations

import math

from core.profile_intelligence import ProfileIntelligence
from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.profile import ProfileResult
from models.score import ScoreResult


class IntelligenceContractError(ValueError):
    """Raised when a Core Intelligence result violates a trusted boundary."""


FAIL_CLOSED_ANALYSIS_WARNINGS = frozenset({
    "EMPTY_DATASET",
    "NO_VALID_TIMEFRAME_DATA",
    "MISSING_REQUIRED_INDICATORS",
    "INVALID_REQUIRED_INDICATORS",
})


def validate_analysis(analysis: AnalysisResult) -> None:
    if not isinstance(analysis, AnalysisResult):
        raise IntelligenceContractError("Analysis boundary requires AnalysisResult.")
    if analysis.market_state not in {"BULLISH", "BEARISH", "NEUTRAL"}:
        raise IntelligenceContractError("Analysis boundary contains invalid market_state.")
    if not _finite_range(analysis.strength, 0.0, 100.0):
        raise IntelligenceContractError("Analysis boundary contains invalid strength.")
    if not isinstance(analysis.signals, list) or any(not isinstance(item, str) for item in analysis.signals):
        raise IntelligenceContractError("Analysis boundary signals must be strings.")
    if not isinstance(analysis.warnings, list) or any(not isinstance(item, str) for item in analysis.warnings):
        raise IntelligenceContractError("Analysis boundary warnings must be strings.")
    fail_closed = FAIL_CLOSED_ANALYSIS_WARNINGS.intersection(analysis.warnings)
    if fail_closed and analysis.market_state != "NEUTRAL":
        raise IntelligenceContractError(
            "Directional AnalysisResult carries fail-closed warnings: "
            + ", ".join(sorted(fail_closed))
        )


def validate_profile(profile: ProfileResult) -> None:
    if not isinstance(profile, ProfileResult):
        raise IntelligenceContractError("Profile boundary requires ProfileResult.")
    if profile.warnings:
        raise IntelligenceContractError(
            "Profile boundary blocked: warning-bearing ProfileResult is not actionable."
        )
    result = ProfileIntelligence().evaluate(profile)
    if result.blocked or not result.is_valid:
        reason = "; ".join(result.reasons) or "Profile intelligence is not actionable."
        raise IntelligenceContractError(f"Profile boundary blocked: {reason}")


def validate_score(score: ScoreResult) -> None:
    if not isinstance(score, ScoreResult):
        raise IntelligenceContractError("Score boundary requires ScoreResult.")
    if not _finite_range(score.score, -100.0, 100.0):
        raise IntelligenceContractError("Score boundary contains invalid score.")
    expected = _score_category(score.score)
    if score.category != expected:
        raise IntelligenceContractError(
            f"Score boundary category/score mismatch: category={score.category!r}, expected={expected!r}."
        )
    if not isinstance(score.factors, list) or any(not isinstance(item, str) for item in score.factors):
        raise IntelligenceContractError("Score boundary factors must be strings.")
    if not isinstance(score.warnings, list) or any(not isinstance(item, str) for item in score.warnings):
        raise IntelligenceContractError("Score boundary warnings must be strings.")


def validate_decision(
    analysis: AnalysisResult,
    score: ScoreResult,
    decision: DecisionResult,
) -> None:
    validate_analysis(analysis)
    validate_score(score)
    if not isinstance(decision, DecisionResult):
        raise IntelligenceContractError("Decision boundary requires DecisionResult.")
    if decision.decision not in {"FAVORABLE", "UNFAVORABLE", "WAIT"}:
        raise IntelligenceContractError("Decision boundary contains invalid decision.")
    if not _finite_range(decision.confidence, 0.0, 100.0):
        raise IntelligenceContractError("Decision boundary contains invalid confidence.")

    if decision.decision == "WAIT":
        if decision.confidence != 0.0:
            raise IntelligenceContractError("WAIT decision must expose zero actionable confidence.")
        return

    if decision.decision == "FAVORABLE":
        if analysis.market_state != "BULLISH" or score.category != "STRONG_BULLISH" or score.score < 60.0:
            raise IntelligenceContractError("FAVORABLE decision contradicts Analysis/Score semantics.")
        return

    if analysis.market_state != "BEARISH" or score.category != "STRONG_BEARISH" or score.score > -60.0:
        raise IntelligenceContractError("UNFAVORABLE decision contradicts Analysis/Score semantics.")


def _score_category(score: float) -> str:
    if score >= 60.0:
        return "STRONG_BULLISH"
    if score >= 20.0:
        return "BULLISH"
    if -20.0 < score < 20.0:
        return "NEUTRAL"
    if score <= -60.0:
        return "STRONG_BEARISH"
    if score <= -20.0:
        return "BEARISH"
    return "NEUTRAL"


def _finite_range(value: object, lower: float, upper: float) -> bool:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(numeric) and lower <= numeric <= upper


__all__ = [
    "IntelligenceContractError",
    "validate_analysis",
    "validate_profile",
    "validate_score",
    "validate_decision",
]
