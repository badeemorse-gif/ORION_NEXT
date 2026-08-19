"""Shared score/decision semantic checks for Core Intelligence."""
from __future__ import annotations

import math

from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.score import ScoreResult


class ScoreDecisionSemanticError(ValueError):
    pass


def validate_score_category(score: ScoreResult) -> None:
    if not isinstance(score, ScoreResult):
        raise ScoreDecisionSemanticError("ScoreResult contract required.")
    value = float(score.score)
    if not math.isfinite(value) or not -100.0 <= value <= 100.0:
        raise ScoreDecisionSemanticError("Score must be finite and bounded to [-100, 100].")
    expected = (
        "STRONG_BULLISH" if value >= 60 else
        "BULLISH" if value >= 20 else
        "NEUTRAL" if value > -20 else
        "BEARISH" if value > -60 else
        "STRONG_BEARISH"
    )
    if score.category != expected:
        raise ScoreDecisionSemanticError(
            f"Score category/value mismatch: {score.category!r} != {expected!r}."
        )


def validate_decision_semantics(
    analysis: AnalysisResult,
    score: ScoreResult,
    decision: DecisionResult,
) -> None:
    validate_score_category(score)
    if not isinstance(decision, DecisionResult):
        raise ScoreDecisionSemanticError("DecisionResult contract required.")
    confidence = float(decision.confidence)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 100.0:
        raise ScoreDecisionSemanticError("Decision confidence must be finite and bounded to [0, 100].")
    if decision.decision == "WAIT":
        if confidence != 0.0:
            raise ScoreDecisionSemanticError("WAIT must have zero actionable confidence.")
        return
    if decision.decision == "FAVORABLE":
        if analysis.market_state != "BULLISH" or score.category != "STRONG_BULLISH":
            raise ScoreDecisionSemanticError("FAVORABLE contradicts Analysis/Score semantics.")
        return
    if decision.decision == "UNFAVORABLE":
        if analysis.market_state != "BEARISH" or score.category != "STRONG_BEARISH":
            raise ScoreDecisionSemanticError("UNFAVORABLE contradicts Analysis/Score semantics.")
        return
    raise ScoreDecisionSemanticError(f"Unsupported decision: {decision.decision!r}.")
