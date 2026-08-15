"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module      : engines.score_engine
Version      : 2.1.0
Status       : ORION Production V2.1 REFACTORED
===============================================================================

Score Engine for translating objective AnalysisResult insights into
normalized numerical scores and categories without direct data-frame access.
===============================================================================
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Optional

from models.analysis import AnalysisResult
from models.score import ScoreResult

base_logger = logging.getLogger(__name__)


# =============================================================================
# Constants & Configuration Dataclasses
# =============================================================================

@dataclass(frozen=True)
class ScoreWeights:
    MARKET_STATE: float = 0.50
    STRENGTH: float = 0.40
    SIGNALS: float = 0.10


@dataclass(frozen=True)
class ScoreThresholds:
    MAX_SCORE: float = 100.0
    MIN_SCORE: float = -100.0

    STRONG_BULLISH: float = 60.0
    BULLISH: float = 20.0
    NEUTRAL_UPPER: float = 20.0
    NEUTRAL_LOWER: float = -20.0
    BEARISH: float = -20.0
    STRONG_BEARISH: float = -60.0


# =============================================================================
# Custom Exceptions
# =============================================================================

class ScoreEngineError(Exception):
    """Base exception for all score engine related errors."""
    pass


class InvalidScoreData(ScoreEngineError):
    """Raised when analysis result data structure or scoring bounds are invalid."""
    pass


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """
    Custom LoggerAdapter to inject contextual information into every log record.
    """

    def process(
        self,
        msg: str,
        kwargs: Any,
    ) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(
            f"{k}={v}"
            for k, v in context.items()
            if v is not None
        )

        if context_str:
            formatted_msg = f"[{context_str}] {msg}"
        else:
            formatted_msg = msg

        return formatted_msg, kwargs


# =============================================================================
# Score Engine
# =============================================================================

class ScoreEngine:
    """
    Stateless score engine operating exclusively on AnalysisResult instances
    without reading DataFrames or executing trades.
    """

    def __init__(self) -> None:
        self.logger = LoggerAdapter(
            base_logger,
            {"operation": "init"},
        )

        self.weights = ScoreWeights()
        self.thresholds = ScoreThresholds()

    def _get_logger(
        self,
        operation: Optional[str] = None,
        score: Optional[float] = None,
        category: Optional[str] = None,
    ) -> LoggerAdapter:
        return LoggerAdapter(
            base_logger,
            {
                "operation": operation,
                "score": score,
                "category": category,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def calculate(self, analysis: AnalysisResult) -> ScoreResult:
        """
        Calculate a ScoreResult from an AnalysisResult.
        """
        if analysis is None:
            raise InvalidScoreData(
                "AnalysisResult is None. Cannot calculate score."
            )

        self._validate_analysis(analysis)

        try:
            factors: list[str] = list(analysis.signals)
            warnings: list[str] = list(analysis.warnings)

            # 1. Market State Score Contribution
            state_score = 0.0

            if analysis.market_state == "BULLISH":
                state_score = 30.0
            elif analysis.market_state == "BEARISH":
                state_score = -30.0

            # 2. Strength Contribution
            #
            # Strength is represented as a magnitude from 0 to 100.
            # It is centered around 50:
            #
            #   0   -> -100
            #   50  ->    0
            #   100 -> +100
            #
            # Direction comes exclusively from the market state. A NEUTRAL
            # market state therefore contributes no directional strength; its
            # magnitude must never be interpreted as bullish merely because it
            # is not explicitly bearish.
            strength_val = max(
                0.0,
                min(100.0, analysis.strength),
            )

            centered_strength = (strength_val * 2.0) - 100.0

            if analysis.market_state == "BEARISH":
                strength_contribution = (
                    -abs(centered_strength)
                    * self.weights.STRENGTH
                )
            elif analysis.market_state == "BULLISH":
                strength_contribution = (
                    centered_strength
                    * self.weights.STRENGTH
                )
            else:
                strength_contribution = 0.0

            # 3. Signals Modifier Contributions
            signal_modifier = 0.0

            positive_signals = {
                "EMA_ALIGNMENT_BULLISH",
                "MOMENTUM_POSITIVE",
                "STRONG_TREND",
            }

            negative_signals = {
                "EMA_ALIGNMENT_BEARISH",
                "MOMENTUM_NEGATIVE",
                "WEAK_TREND",
            }

            for sig in analysis.signals:
                if sig in positive_signals:
                    signal_modifier += 10.0
                elif sig in negative_signals:
                    signal_modifier -= 10.0

            # 4. Combine weighted components
            raw_score = (
                (state_score * self.weights.MARKET_STATE)
                + strength_contribution
                + (signal_modifier * self.weights.SIGNALS)
            )

            total_score = self._normalize(raw_score)

            # 5. Classify normalized score
            category = self._classify_score(total_score)

            score_result = ScoreResult(
                score=total_score,
                category=category,
                factors=factors,
                warnings=warnings,
            )

            logger = self._get_logger(
                operation="calculate",
                score=total_score,
                category=category,
            )

            logger.info(
                "Score calculated successfully from AnalysisResult."
            )

            return score_result

        except Exception as e:
            if isinstance(e, ScoreEngineError):
                raise

            raise ScoreEngineError(
                f"Failed to calculate score from analysis result: {e}"
            ) from e

    # -------------------------------------------------------------------------
    # Internal Validation & Helper Methods
    # -------------------------------------------------------------------------

    def _validate_analysis(
        self,
        analysis: AnalysisResult,
    ) -> None:
        """
        Validate analysis result properties and bounds.

        Fail-closed boundary: non-finite strength must never reach scoring.
        In particular, NaN bypasses ordinary range comparisons and could
        otherwise contaminate normalization/classification into a false
        directional score.
        """
        if analysis.market_state not in {
            "BULLISH",
            "BEARISH",
            "NEUTRAL",
        }:
            raise InvalidScoreData(
                f"Invalid market_state value "
                f"({analysis.market_state}) in AnalysisResult."
            )

        try:
            strength = float(analysis.strength)
        except (TypeError, ValueError) as exc:
            raise InvalidScoreData(
                f"Invalid strength value ({analysis.strength}) in AnalysisResult. "
                "Expected a finite number from 0 to 100."
            ) from exc

        if not math.isfinite(strength):
            raise InvalidScoreData(
                f"Invalid strength value ({analysis.strength}) in AnalysisResult. "
                "Expected a finite number from 0 to 100."
            )

        if strength < 0.0 or strength > 100.0:
            raise InvalidScoreData(
                f"Invalid strength value "
                f"({analysis.strength}) in AnalysisResult. "
                f"Expected 0 to 100."
            )

    def _classify_score(self, score: float) -> str:
        """
        Classifies numerical score into standard market categories.
        """
        if score >= self.thresholds.STRONG_BULLISH:
            return "STRONG_BULLISH"

        elif score >= self.thresholds.BULLISH:
            return "BULLISH"

        elif (
            score > self.thresholds.NEUTRAL_LOWER
            and score < self.thresholds.NEUTRAL_UPPER
        ):
            return "NEUTRAL"

        elif score <= self.thresholds.STRONG_BEARISH:
            return "STRONG_BEARISH"

        elif score <= self.thresholds.BEARISH:
            return "BEARISH"

        return "NEUTRAL"

    def _normalize(self, value: float) -> float:
        """
        Clamps value strictly within boundaries.
        """
        return float(
            max(
                self.thresholds.MIN_SCORE,
                min(self.thresholds.MAX_SCORE, value),
            )
        )


# =============================================================================
# End Of File
# =============================================================================
