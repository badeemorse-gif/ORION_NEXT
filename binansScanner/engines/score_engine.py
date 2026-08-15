"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.score_engine
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


class ScoreEngineError(Exception):
    pass


class InvalidScoreData(ScoreEngineError):
    pass


class LoggerAdapter(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        return (f"[{context_str}] {msg}" if context_str else msg), kwargs


class ScoreEngine:
    """Stateless score engine operating exclusively on AnalysisResult."""

    def __init__(self) -> None:
        self.logger = LoggerAdapter(base_logger, {"operation": "init"})
        self.weights = ScoreWeights()
        self.thresholds = ScoreThresholds()

    def _get_logger(self, operation: Optional[str] = None, score: Optional[float] = None, category: Optional[str] = None) -> LoggerAdapter:
        return LoggerAdapter(base_logger, {"operation": operation, "score": score, "category": category})

    def calculate(self, analysis: AnalysisResult) -> ScoreResult:
        if analysis is None:
            raise InvalidScoreData("AnalysisResult is None. Cannot calculate score.")
        self._validate_analysis(analysis)
        try:
            factors = list(analysis.signals)
            warnings = list(analysis.warnings)
            state_score = 30.0 if analysis.market_state == "BULLISH" else -30.0 if analysis.market_state == "BEARISH" else 0.0
            strength_val = max(0.0, min(100.0, float(analysis.strength)))
            centered_strength = (strength_val * 2.0) - 100.0
            if analysis.market_state == "BEARISH":
                strength_contribution = -abs(centered_strength) * self.weights.STRENGTH
            elif analysis.market_state == "BULLISH":
                strength_contribution = centered_strength * self.weights.STRENGTH
            else:
                strength_contribution = 0.0

            positive_signals = {"EMA_ALIGNMENT_BULLISH", "MOMENTUM_POSITIVE", "STRONG_TREND"}
            negative_signals = {"EMA_ALIGNMENT_BEARISH", "MOMENTUM_NEGATIVE", "WEAK_TREND"}
            signal_modifier = 0.0
            for sig in analysis.signals:
                if sig in positive_signals:
                    signal_modifier += 10.0
                elif sig in negative_signals:
                    signal_modifier -= 10.0

            raw_score = (state_score * self.weights.MARKET_STATE) + strength_contribution + (signal_modifier * self.weights.SIGNALS)
            total_score = self._normalize(raw_score)
            category = self._classify_score(total_score)
            result = ScoreResult(score=total_score, category=category, factors=factors, warnings=warnings)
            self._get_logger(operation="calculate", score=total_score, category=category).info("Score calculated successfully from AnalysisResult.")
            return result
        except Exception as exc:
            if isinstance(exc, ScoreEngineError):
                raise
            raise ScoreEngineError(f"Failed to calculate score from analysis result: {exc}") from exc

    def _validate_analysis(self, analysis: AnalysisResult) -> None:
        if analysis.market_state not in {"BULLISH", "BEARISH", "NEUTRAL"}:
            raise InvalidScoreData(f"Invalid market_state value ({analysis.market_state}) in AnalysisResult.")
        try:
            strength = float(analysis.strength)
        except (TypeError, ValueError) as exc:
            raise InvalidScoreData(f"Invalid strength value ({analysis.strength}) in AnalysisResult. Expected a finite number from 0 to 100.") from exc
        if not math.isfinite(strength):
            raise InvalidScoreData(f"Invalid strength value ({analysis.strength}) in AnalysisResult. Expected a finite number from 0 to 100.")
        if strength < 0.0 or strength > 100.0:
            raise InvalidScoreData(f"Invalid strength value ({analysis.strength}) in AnalysisResult. Expected 0 to 100.")

    def _classify_score(self, score: float) -> str:
        if score >= self.thresholds.STRONG_BULLISH:
            return "STRONG_BULLISH"
        if score >= self.thresholds.BULLISH:
            return "BULLISH"
        if self.thresholds.NEUTRAL_LOWER < score < self.thresholds.NEUTRAL_UPPER:
            return "NEUTRAL"
        if score <= self.thresholds.STRONG_BEARISH:
            return "STRONG_BEARISH"
        if score <= self.thresholds.BEARISH:
            return "BEARISH"
        return "NEUTRAL"

    def _normalize(self, value: float) -> float:
        return float(max(self.thresholds.MIN_SCORE, min(self.thresholds.MAX_SCORE, value)))
