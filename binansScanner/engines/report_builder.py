"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.report_builder
Version      : 1.0.0
Status       : ORION Production Report Builder Component
===============================================================================

Standalone report builder component responsible for compiling sections, summaries,
highlights, warnings, and metadata for market reports.
===============================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from engines.profile_engine import MarketProfile
from engines.score_engine import ScoreResult
from engines.decision_engine import DecisionResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReportConfig:
    REPORT_VERSION: str = "1.0.0"
    ENGINE_VERSION: str = "1.0.0"
    JSON_INDENT: int = 4
    JSON_SORT_KEYS: bool = True
    UTF8_ENCODING: str = "utf-8"
    MAX_SUMMARY_LINES: int = 5


@dataclass(frozen=True)
class ReportTemplates:
    SUMMARY_TEMPLATE: str = (
        "Market State Summary for {symbol}:\n"
        "• Trend: {trend} | Phase: {phase}\n"
        "• Total Score: {score:.1f}/100 | Decision: {decision}\n"
        "• Risk Level: {risk} | Confidence: {confidence:.1f}%"
    )


class ReportBuilderError(Exception):
    """Base exception for report builder errors."""
    pass


class ReportBuilder:
    """
    Encapsulates all report section building, summary generation, highlights,
    warnings, and metadata construction logic.
    """

    def __init__(self, config: Optional[ReportConfig] = None, templates: Optional[ReportTemplates] = None) -> None:
        self.config = config or ReportConfig()
        self.templates = templates or ReportTemplates()

    def build_report_sections(
        self,
        profile: MarketProfile,
        score: ScoreResult,
        decision: DecisionResult
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        """
        Build profile, score, and decision sections in a single dedicated helper method.
        """
        profile_dict = self._to_serializable(profile)
        score_dict = self._to_serializable(score)
        decision_dict = self._to_serializable(decision)
        return profile_dict, score_dict, decision_dict

    def build_summary(
        self,
        symbol: str,
        profile: MarketProfile,
        score: ScoreResult,
        decision: DecisionResult
    ) -> list[str]:
        trend_val = getattr(profile, "trend", "UNKNOWN")
        trend_str = trend_val.value if hasattr(trend_val, "value") else str(trend_val)

        phase_val = getattr(profile, "market_phase", "UNKNOWN")
        phase_str = phase_val.value if hasattr(phase_val, "value") else str(phase_val)

        total_score = getattr(score, "total_score", 0.0)

        dec_val = getattr(decision, "decision", "UNKNOWN")
        dec_str = dec_val.value if hasattr(dec_val, "value") else str(dec_val)

        risk_val = getattr(profile, "risk_level", "UNKNOWN")
        risk_str = risk_val.value if hasattr(risk_val, "value") else str(risk_val)

        confidence = getattr(profile, "confidence", 0.0)

        formatted_text = self.templates.SUMMARY_TEMPLATE.format(
            symbol=symbol,
            trend=trend_str,
            phase=phase_str,
            score=total_score,
            decision=dec_str,
            risk=risk_str,
            confidence=confidence,
        )

        lines = [line.strip() for line in formatted_text.split("\n") if line.strip()]
        return lines[:self.config.MAX_SUMMARY_LINES]

    def build_highlights(self, profile: MarketProfile, score: ScoreResult) -> list[str]:
        highlights: list[str] = []

        trend_val = getattr(profile, "trend", None)
        trend_str = trend_val.value if hasattr(trend_val, "value") else str(trend_val)
        if trend_str == "Bullish":
            highlights.append("Strong Trend")

        confidence = getattr(profile, "confidence", 0.0)
        if confidence >= 75.0:
            highlights.append("High Confidence")

        vol_val = getattr(profile, "volume_strength", None)
        vol_str = vol_val.value if hasattr(vol_val, "value") else str(vol_val)
        if vol_str == "Strong":
            highlights.append("Healthy Volume")

        risk_val = getattr(profile, "risk_level", None)
        risk_str = risk_val.value if hasattr(risk_val, "value") else str(risk_val)
        if risk_str in {"Low", "Medium"}:
            highlights.append("Low Risk")

        mom_val = getattr(profile, "momentum", None)
        mom_str = mom_val.value if hasattr(mom_val, "value") else str(mom_val)
        if "Buy" in mom_str:
            highlights.append("Momentum Confirmed")

        return highlights

    def build_warnings(self, profile: MarketProfile, score: ScoreResult, decision: DecisionResult) -> list[str]:
        warnings: list[str] = []

        vol_lvl = getattr(profile, "volatility_level", None)
        vol_lvl_str = vol_lvl.value if hasattr(vol_lvl, "value") else str(vol_lvl)
        if vol_lvl_str in {"High", "Extreme"}:
            warnings.append("High Volatility")

        trend_str = getattr(profile, "trend", None)
        trend_str_val = trend_str.value if hasattr(trend_str, "value") else str(trend_str)
        trend_strength = getattr(profile, "trend_strength", None)
        trend_strength_val = trend_strength.value if hasattr(trend_strength, "value") else str(trend_strength)
        if trend_strength_val == "Weak" or trend_str_val == "Sideways":
            warnings.append("Weak Trend")

        confidence = getattr(profile, "confidence", 0.0)
        if confidence < 40.0:
            warnings.append("Low Confidence")

        phase = getattr(profile, "market_phase", None)
        phase_str = phase.value if hasattr(phase, "value") else str(phase)
        if phase_str == "Range":
            warnings.append("Range Market")

        risk_val = getattr(profile, "risk_level", None)
        risk_str = risk_val.value if hasattr(risk_val, "value") else str(risk_val)
        if risk_str in {"High", "Extreme"}:
            warnings.append("High Risk")

        dec_warnings = getattr(decision, "warnings", [])
        for w in dec_warnings:
            w_str = w.value if hasattr(w, "value") else str(w)
            if w_str not in warnings:
                warnings.append(w_str)

        return warnings

    def build_metadata(self, symbol: str, exchange: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "exchange": exchange,
            "engine_version": self.config.ENGINE_VERSION,
            "report_version": self.config.REPORT_VERSION,
            "generated_at": datetime.now(timezone.utc),
        }

    def _to_serializable(self, obj: Any) -> Any:
        if obj is None:
            return None
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, (list, tuple, set)):
            return [self._to_serializable(item) for item in obj]
        if isinstance(obj, dict):
            return {str(k): self._to_serializable(v) for k, v in obj.items()}
        if hasattr(obj, "__dataclass_fields__"):
            return {field_name: self._to_serializable(getattr(obj, field_name)) for field_name in obj.__dataclass_fields__}
        if hasattr(obj, "__dict__"):
            return {str(k): self._to_serializable(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
        
        raise ReportBuilderError(f"Object of type {type(obj).__name__} is not JSON serializable: {obj}")