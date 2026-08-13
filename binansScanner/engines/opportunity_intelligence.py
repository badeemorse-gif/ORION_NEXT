"""Evidence-driven Scalping Opportunity Intelligence.

This module consumes only canonical Core Intelligence results and market data.
It deliberately contains no Binance, execution, watchlist, or live-trading code.

Missing or semantically unavailable Core evidence fails closed. No ranking
numbers, thresholds, forecasts, or synthetic setup-quality values are created.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from enums import Timeframe
from models.analysis import AnalysisResult
from models.market import MarketDataset
from models.opportunity import (
    FreshnessStatus,
    Opportunity,
    OpportunityDirection,
    OpportunityRisk,
    OpportunityStatus,
    RiskState,
)
from models.opportunity_candidate_set import OpportunityCandidateSet
from models.opportunity_evaluation import OpportunityEvaluation, OpportunityEvaluationStatus
from models.profile import ProfileResult, RiskLevel as ProfileRiskLevel, TimeframeProfile
from models.score import ScoreResult
from models.trading_readiness import TradingReadiness


class OpportunityIntelligenceError(ValueError):
    """Raised when Core evidence cannot produce a valid opportunity boundary."""


@dataclass(slots=True, frozen=True)
class CoreOpportunityEvidence:
    """Immutable bundle of real Core evidence consumed by Opportunity Intelligence."""

    dataset: MarketDataset
    analysis: AnalysisResult
    profile: ProfileResult
    score: ScoreResult
    timeframe: str
    freshness: FreshnessStatus = FreshnessStatus.UNKNOWN

    def __post_init__(self) -> None:
        if not isinstance(self.dataset, MarketDataset):
            raise ValueError("dataset must be MarketDataset")
        if not isinstance(self.analysis, AnalysisResult):
            raise ValueError("analysis must be AnalysisResult")
        if not isinstance(self.profile, ProfileResult):
            raise ValueError("profile must be ProfileResult")
        if not isinstance(self.score, ScoreResult):
            raise ValueError("score must be ScoreResult")
        if not self.timeframe or not self.timeframe.strip():
            raise ValueError("timeframe must be non-empty")
        if not isinstance(self.freshness, FreshnessStatus):
            raise ValueError("freshness must be FreshnessStatus")
        if self.dataset.symbol != self.profile.symbol:
            raise ValueError("dataset/profile symbol mismatch")


@dataclass(slots=True, frozen=True)
class OpportunitySelectionResult:
    """Final selection boundary; it contains no execution intent."""

    evaluations: tuple[OpportunityEvaluation, ...]
    selected: Optional[Opportunity]
    readiness: TradingReadiness
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluations", tuple(self.evaluations))
        object.__setattr__(self, "reasons", tuple(str(reason) for reason in self.reasons))
        if self.selected is not None and not any(
            evaluation.opportunity is self.selected and evaluation.accepted
            for evaluation in self.evaluations
        ):
            raise ValueError("selected opportunity must be an accepted evaluated candidate")


class OpportunityCandidateGenerator:
    """Generate candidates from actual Analysis/Profile/Score evidence."""

    def generate(self, evidence: CoreOpportunityEvidence) -> OpportunityCandidateSet:
        analysis = evidence.analysis
        if analysis.market_state == "NEUTRAL":
            raise OpportunityIntelligenceError(
                "No directional Core Intelligence evidence exists for candidate generation"
            )
        if analysis.market_state not in {"BULLISH", "BEARISH"}:
            raise OpportunityIntelligenceError("Unsupported analysis market state")
        if not evidence.profile.is_valid:
            raise OpportunityIntelligenceError("Profile is not valid/tradeable")

        timeframe = self._normalize_timeframe(evidence.timeframe)
        timeframe_data = evidence.dataset.get_timeframe(timeframe)
        if timeframe_data is None or timeframe_data.dataframe.empty:
            raise OpportunityIntelligenceError(
                f"No market data exists for requested timeframe {evidence.timeframe}"
            )
        profile = self._matching_timeframe_profile(evidence.profile, timeframe)
        if profile is None:
            raise OpportunityIntelligenceError(
                f"No ProfileResult timeframe matches requested timeframe {evidence.timeframe}"
            )
        if "close" not in timeframe_data.dataframe.columns:
            raise OpportunityIntelligenceError("Market data has no canonical close field")

        last_close = timeframe_data.dataframe["close"].iloc[-1]
        if last_close is None:
            raise OpportunityIntelligenceError("Latest close is unavailable")
        entry = float(last_close)
        if entry <= 0:
            raise OpportunityIntelligenceError("Latest close must be positive")

        direction = (
            OpportunityDirection.LONG
            if analysis.market_state == "BULLISH"
            else OpportunityDirection.SHORT
        )
        risk = self._risk_from_timeframe_profile(profile)
        supporting = tuple(dict.fromkeys((*analysis.signals, *evidence.score.factors)))
        if not supporting:
            raise OpportunityIntelligenceError(
                "Core evidence contains no directional signals/factors"
            )

        characteristics = profile.characteristics
        context = (
            f"trend={characteristics.trend}",
            f"momentum={characteristics.momentum}",
            f"ema_alignment={characteristics.ema_alignment}",
            f"volatility_level={characteristics.volatility_level}",
        )
        candidate = Opportunity(
            symbol=evidence.dataset.symbol,
            timeframe=timeframe.value,
            direction=direction,
            entry_candidate=entry,
            confidence=min(float(analysis.strength), float(profile.confidence)),
            setup_quality=None,
            risk=risk,
            expected_move=None,
            supporting_evidence=supporting,
            market_context=context,
            freshness=evidence.freshness,
            status=OpportunityStatus.ACTIVE,
        )
        return OpportunityCandidateSet((candidate,))

    @staticmethod
    def _normalize_timeframe(value: str) -> Timeframe:
        try:
            return Timeframe(value)
        except ValueError as exc:
            raise OpportunityIntelligenceError(
                f"Unsupported canonical timeframe: {value!r}"
            ) from exc

    @staticmethod
    def _matching_timeframe_profile(
        profile: ProfileResult,
        timeframe: Timeframe,
    ) -> Optional[TimeframeProfile]:
        matches = tuple(item for item in profile.timeframes if item.timeframe == timeframe.value)
        if len(matches) != 1:
            return None
        return matches[0]

    @staticmethod
    def _risk_from_timeframe_profile(profile: TimeframeProfile) -> OpportunityRisk:
        level = profile.risk_level
        if level == ProfileRiskLevel.EXTREME.value:
            return OpportunityRisk(
                state=RiskState.UNACCEPTABLE,
                invalidation="Core Profile timeframe reports extreme risk",
            )
        if level == ProfileRiskLevel.HIGH.value:
            return OpportunityRisk(
                state=RiskState.ELEVATED,
                invalidation="Core Profile timeframe reports high risk",
            )
        if level in {ProfileRiskLevel.LOW.value, ProfileRiskLevel.MEDIUM.value}:
            return OpportunityRisk(state=RiskState.ACCEPTABLE)
        return OpportunityRisk(
            state=RiskState.UNKNOWN,
            invalidation="Core Profile timeframe risk level is unknown",
        )


class OpportunitySelectionPolicy:
    """Select only when Core evidence provides an unambiguous candidate."""

    _DIRECTIONAL_SCORE_CATEGORIES = {
        OpportunityDirection.LONG: {"BULLISH", "STRONG_BULLISH"},
        OpportunityDirection.SHORT: {"BEARISH", "STRONG_BEARISH"},
    }

    def select(
        self,
        candidates: OpportunityCandidateSet,
        evidence: CoreOpportunityEvidence,
    ) -> OpportunitySelectionResult:
        evaluations = tuple(self._evaluate(candidate, evidence) for candidate in candidates)
        accepted = tuple(
            evaluation.opportunity for evaluation in evaluations if evaluation.accepted
        )
        reasons: list[str] = []
        selected: Optional[Opportunity] = None

        if len(accepted) == 1:
            selected = accepted[0]
        elif len(accepted) == 0:
            reasons.append("No candidate satisfies every evidence gate")
        else:
            reasons.append(
                "Selection is ambiguous: Core evidence supplies no tie-breaker, so no ranking is invented"
            )
            evaluations = tuple(
                OpportunityEvaluation(
                    opportunity=evaluation.opportunity,
                    status=OpportunityEvaluationStatus.REJECTED,
                    reasons=evaluation.reasons
                    + ("ambiguous selection; no evidence-backed tie-breaker",),
                )
                if evaluation.accepted
                else evaluation
                for evaluation in evaluations
            )

        readiness = self._readiness(selected, evidence, tuple(reasons))
        return OpportunitySelectionResult(
            evaluations=evaluations,
            selected=selected,
            readiness=readiness,
            reasons=tuple(reasons),
        )

    def _evaluate(
        self,
        candidate: Opportunity,
        evidence: CoreOpportunityEvidence,
    ) -> OpportunityEvaluation:
        reasons: list[str] = []
        timeframe = OpportunityCandidateGenerator._normalize_timeframe(candidate.timeframe)
        timeframe_profile = OpportunityCandidateGenerator._matching_timeframe_profile(
            evidence.profile, timeframe
        )
        expected_state = (
            "BULLISH" if candidate.direction is OpportunityDirection.LONG else "BEARISH"
        )
        if evidence.analysis.market_state != expected_state:
            reasons.append("analysis direction does not support candidate direction")

        if timeframe_profile is None:
            reasons.append("profile timeframe evidence is missing or ambiguous")
        else:
            expected_trend = (
                "Bullish" if candidate.direction is OpportunityDirection.LONG else "Bearish"
            )
            characteristics = timeframe_profile.characteristics
            if characteristics.trend != expected_trend:
                reasons.append("profile timeframe trend does not support candidate direction")
            if characteristics.ema_alignment != expected_trend:
                reasons.append(
                    "profile timeframe EMA alignment does not support candidate direction"
                )
            expected_confidence = min(
                float(evidence.analysis.strength), float(timeframe_profile.confidence)
            )
            if candidate.confidence != expected_confidence:
                reasons.append("candidate confidence does not match timeframe Core evidence")

        if evidence.score.category not in self._DIRECTIONAL_SCORE_CATEGORIES[candidate.direction]:
            reasons.append("score category does not support candidate direction")
        if not evidence.profile.is_valid:
            reasons.append("profile is not valid/tradeable")
        if candidate.risk.state is not RiskState.ACCEPTABLE:
            reasons.append(f"risk gate is {candidate.risk.state.value}")
        if candidate.freshness is not FreshnessStatus.FRESH:
            reasons.append(f"freshness gate is {candidate.freshness.value}")
        if not candidate.is_complete:
            if candidate.setup_quality is None:
                reasons.append("setup quality evidence is unavailable in Core")
            reasons.append("candidate contract is incomplete")

        status = (
            OpportunityEvaluationStatus.ACCEPTED
            if not reasons
            else OpportunityEvaluationStatus.REJECTED
        )
        return OpportunityEvaluation(
            opportunity=candidate,
            status=status,
            reasons=tuple(reasons),
        )

    @staticmethod
    def _readiness(
        selected: Optional[Opportunity],
        evidence: CoreOpportunityEvidence,
        selection_reasons: tuple[str, ...],
    ) -> TradingReadiness:
        if selected is None:
            return TradingReadiness(
                intelligence_complete=False,
                confidence_acceptable=False,
                opportunity_fresh=False,
                risk_acceptable=False,
                market_conditions_valid=False,
                reasons=selection_reasons or ("No selected opportunity",),
            )
        return TradingReadiness(
            intelligence_complete=selected.is_complete and evidence.profile.is_valid,
            confidence_acceptable=selected.confidence is not None
            and selected.setup_quality is not None,
            opportunity_fresh=selected.freshness is FreshnessStatus.FRESH,
            risk_acceptable=selected.risk.state is RiskState.ACCEPTABLE,
            market_conditions_valid=selected.direction
            is (
                OpportunityDirection.LONG
                if evidence.analysis.market_state == "BULLISH"
                else OpportunityDirection.SHORT
            ),
            reasons=selection_reasons,
        )


__all__ = [
    "CoreOpportunityEvidence",
    "OpportunityCandidateGenerator",
    "OpportunityIntelligenceError",
    "OpportunitySelectionPolicy",
    "OpportunitySelectionResult",
]
