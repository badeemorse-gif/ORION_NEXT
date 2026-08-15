"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.decision_engine
Version      : 1.2.0
Status       : ORION Production V1.2 REFACTORED
===============================================================================

Decision Engine for transforming objective AnalysisResult and ScoreResult
insights into structured analytical decision statuses without order execution.
===============================================================================
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

from models.analysis import AnalysisResult
from models.score import ScoreResult
from models.decision import DecisionResult

base_logger = logging.getLogger(__name__)


class DecisionEngineError(Exception):
    """Base exception for all decision engine related errors."""
    pass


class InvalidDecisionData(DecisionEngineError):
    """Raised when analysis or score result data structures are invalid."""
    pass


class InvalidScoreData(DecisionEngineError):
    """Raised when ScoreResult value is invalid."""
    pass


class LoggerAdapter(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        if context_str:
            formatted_msg = f"[{context_str}] {msg}"
        else:
            formatted_msg = msg
        return formatted_msg, kwargs


class DecisionEngine:
    """Stateless decision engine over canonical AnalysisResult and ScoreResult."""

    def __init__(self) -> None:
        self.logger = LoggerAdapter(base_logger, {"operation": "init"})

    def _get_logger(
        self,
        operation: Optional[str] = None,
        decision: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> LoggerAdapter:
        return LoggerAdapter(
            base_logger,
            {"operation": operation, "decision": decision, "confidence": confidence},
        )

    def decide(self, analysis: AnalysisResult, score: ScoreResult) -> DecisionResult:
        if analysis is None:
            raise InvalidDecisionData("AnalysisResult is None. Cannot make a decision.")
        if score is None:
            raise InvalidDecisionData("ScoreResult is None. Cannot make a decision.")

        self._validate_inputs(analysis, score)

        try:
            decision = "WAIT"
            reasons: list[str] = []
            warnings: list[str] = list(analysis.warnings)

            if score.factors:
                reasons.extend(score.factors)
            if analysis.signals:
                for sig in analysis.signals:
                    if sig not in reasons:
                        reasons.append(sig)

            if score.category in {"STRONG_BULLISH", "BULLISH"} and analysis.market_state == "BEARISH":
                warnings.append("CONFLICT_SCORE_BULLISH_STATE_BEARISH")
            elif score.category in {"STRONG_BEARISH", "BEARISH"} and analysis.market_state == "BULLISH":
                warnings.append("CONFLICT_SCORE_BEARISH_STATE_BULLISH")

            if score.category == "STRONG_BULLISH" and analysis.market_state == "BULLISH":
                decision = "FAVORABLE"
                if "STRONG_SCORE" not in reasons:
                    reasons.append("STRONG_SCORE")
            elif score.category == "STRONG_BEARISH" and analysis.market_state == "BEARISH":
                decision = "UNFAVORABLE"
                if "STRONG_SCORE_NEGATIVE" not in reasons:
                    reasons.append("STRONG_SCORE_NEGATIVE")
            else:
                decision = "WAIT"
                if "NEUTRAL_OR_MIXED_CONDITIONS" not in reasons:
                    reasons.append("NEUTRAL_OR_MIXED_CONDITIONS")

            if decision == "WAIT":
                confidence = 0.0
            else:
                confidence = self._calculate_confidence(score.score)

            decision_result = DecisionResult(
                decision=decision,
                confidence=confidence,
                reasons=reasons,
                warnings=warnings,
            )

            self._get_logger(
                operation="decide",
                decision=decision,
                confidence=confidence,
            ).info("Decision derived successfully from analysis and score results.")

            return decision_result

        except Exception as e:
            if isinstance(e, DecisionEngineError):
                raise
            raise DecisionEngineError(f"Failed to calculate decision: {e}") from e

    def _validate_inputs(self, analysis: AnalysisResult, score: ScoreResult) -> None:
        if analysis.market_state not in {"BULLISH", "BEARISH", "NEUTRAL"}:
            raise InvalidDecisionData(
                f"Invalid market_state value ({analysis.market_state}) in AnalysisResult."
            )

        try:
            score_value = float(score.score)
        except (TypeError, ValueError) as exc:
            raise InvalidScoreData(
                f"Invalid score value ({score.score}) in ScoreResult. Expected a finite number from -100 to 100."
            ) from exc

        if not math.isfinite(score_value):
            raise InvalidScoreData(
                f"Invalid score value ({score.score}) in ScoreResult. Expected a finite number from -100 to 100."
            )

        if score_value < -100.0 or score_value > 100.0:
            raise InvalidScoreData(
                f"Invalid score value ({score.score}) in ScoreResult. Expected -100 to 100."
            )

    def _calculate_confidence(self, score_value: float) -> float:
        normalized_magnitude = abs(score_value)
        return float(max(0.0, min(100.0, normalized_magnitude)))


# End Of File
