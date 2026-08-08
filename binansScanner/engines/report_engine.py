"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.report_engine
Version      : 2.0.0
Status       : ORION Production Coordinator V2
===============================================================================

Report Engine Coordinator for compiling objective market profile, score, and decision results
into fully serializable JSON-ready reports via ReportBuilder delegation.
===============================================================================
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from models.market import MarketDataset
from engines.profile_engine import MarketProfile
from engines.score_engine import ScoreResult
from engines.decision_engine import DecisionResult
from engines.report_builder import ReportBuilder, ReportConfig, ReportTemplates

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class ReportEngineError(Exception):
    """Base exception for all report engine related errors."""
    pass


class InvalidReportData(ReportEngineError):
    """Raised when report input dataset, profile, score, or decision is missing/invalid."""
    pass


# =============================================================================
# Report Result Dataclass
# =============================================================================

@dataclass(slots=True)
class ReportResult:
    """
    Immutable dataclass representing a fully compiled, serializable, and exportable
    objective market report.
    """
    symbol: str = ""
    exchange: str = ""
    generated_at: Optional[datetime] = None
    profile: dict[str, Any] = field(default_factory=dict)
    score: dict[str, Any] = field(default_factory=dict)
    decision: dict[str, Any] = field(default_factory=dict)
    summary: list[str] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    json_ready: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """
    Custom LoggerAdapter to inject contextual information into every log record.
    """

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        if context_str:
            formatted_msg = f"[{context_str}] {msg}"
        else:
            formatted_msg = msg
        return formatted_msg, kwargs


# =============================================================================
# Report Engine
# =============================================================================

class ReportEngine:
    """
    Stateless report generation engine coordinator operating exclusively on MarketDataset objects
    (Profile, Score, Decision) by delegating construction to ReportBuilder.
    """

    def __init__(self, builder: Optional[ReportBuilder] = None) -> None:
        self._builder = builder if builder is not None else ReportBuilder()
        self.logger = LoggerAdapter(
            base_logger,
            {
                "symbol": None,
                "decision": None,
                "score": None,
                "elapsed_ms": None,
                "output_file": None,
                "operation": "init",
            },
        )
        self.config = self._builder.config

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def build_report(self, dataset: MarketDataset) -> MarketDataset:
        """
        Compile all dataset components (profile, score, decision) into a complete
        ReportResult using ReportBuilder and attach it directly to MarketDataset.report.
        """
        symbol = dataset.symbol or "UNKNOWN"
        exchange = getattr(dataset, "exchange", "binance")
        start_time = time.time()

        self._validate_dataset(dataset)

        try:
            profile_dict, score_dict, decision_dict = self._builder.build_report_sections(
                dataset.profile, dataset.score, dataset.decision
            )

            summary_lines = self._builder.build_summary(symbol, dataset.profile, dataset.score, dataset.decision)
            highlights = self._builder.build_highlights(dataset.profile, dataset.score)
            warnings = self._builder.build_warnings(dataset.profile, dataset.score, dataset.decision)
            metadata = self._builder.build_metadata(symbol, exchange)

            generated_at_dt = datetime.now(timezone.utc)

            raw_report_dict = {
                "symbol": symbol,
                "exchange": exchange,
                "generated_at": generated_at_dt,
                "profile": profile_dict,
                "score": score_dict,
                "decision": decision_dict,
                "summary": summary_lines,
                "highlights": highlights,
                "warnings": warnings,
                "metadata": metadata,
            }

            json_ready_dict = self._builder._to_serializable(raw_report_dict)

            report_result = ReportResult(
                symbol=symbol,
                exchange=exchange,
                generated_at=generated_at_dt,
                profile=profile_dict,
                score=score_dict,
                decision=decision_dict,
                summary=summary_lines,
                highlights=highlights,
                warnings=warnings,
                metadata=metadata,
                json_ready=json_ready_dict,
            )

            dataset.report = report_result

            elapsed_ms = (time.time() - start_time) * 1000.0
            score_val = getattr(dataset.score, "total_score", 0.0)
            decision_val = getattr(dataset.decision, "decision", "UNKNOWN")
            if hasattr(decision_val, "value"):
                decision_str = decision_val.value
            else:
                decision_str = str(decision_val)

            self.logger.extra.update({
                "symbol": symbol,
                "decision": decision_str,
                "score": score_val,
                "elapsed_ms": elapsed_ms,
                "output_file": None,
                "operation": "build_report",
            })
            self.logger.info("Report successfully built and attached to dataset.")

        except Exception as e:
            if isinstance(e, ReportEngineError):
                raise
            raise ReportEngineError(f"Failed to build report for dataset {symbol}: {e}") from e

        return dataset

    def build_summary(self, report: ReportResult) -> list[str]:
        """
        Return the concise summary lines from a ReportResult.
        """
        if report is None:
            return []
        return report.summary

    def export_dict(self, report: ReportResult) -> dict[str, Any]:
        """
        Export ReportResult as a fully serializable dictionary.
        """
        if report is None:
            raise InvalidReportData("Cannot export dictionary from None report.")
        return report.json_ready

    def export_json(self, report: ReportResult, pretty: bool = True) -> str:
        """
        Export ReportResult as a JSON formatted string.
        """
        data = self.export_dict(report)
        indent_val = self.config.JSON_INDENT if pretty else None
        return json.dumps(
            data,
            indent=indent_val,
            sort_keys=self.config.JSON_SORT_KEYS,
            ensure_ascii=False
        )

    def save_json(self, report: ReportResult, output_path: Union[str, Path], pretty: bool = True) -> Path:
        """
        Save ReportResult as a JSON file to the specified output path, automatically creating parent directories.
        """
        path_obj = Path(output_path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        json_str = self.export_json(report, pretty=pretty)
        
        with open(path_obj, "w", encoding=self.config.UTF8_ENCODING, newline="\n") as f:
            f.write(json_str)

        symbol = report.symbol if report else "UNKNOWN"
        score_val = report.score.get("total_score", 0.0) if report and report.score else 0.0
        decision_val = report.decision.get("decision", "UNKNOWN") if report and report.decision else "UNKNOWN"

        self.logger.extra.update({
            "symbol": symbol,
            "decision": str(decision_val),
            "score": score_val,
            "elapsed_ms": None,
            "output_file": str(path_obj),
            "operation": "save_json",
        })
        self.logger.info(f"Report saved successfully to {path_obj}.")

        return path_obj

    # -------------------------------------------------------------------------
    # Internal Validation Methods
    # -------------------------------------------------------------------------

    def _validate_dataset(self, dataset: MarketDataset) -> None:
        """
        Validate that the dataset contains required profile, score, and decision components.
        """
        if dataset is None:
            raise InvalidReportData("MarketDataset is None.")
        if not hasattr(dataset, "profile") or dataset.profile is None:
            raise InvalidReportData(f"Dataset for symbol '{dataset.symbol}' is missing required MarketProfile.")
        if not hasattr(dataset, "score") or dataset.score is None:
            raise InvalidReportData(f"Dataset for symbol '{dataset.symbol}' is missing required ScoreResult.")
        if not hasattr(dataset, "decision") or dataset.decision is None:
            raise InvalidReportData(f"Dataset for symbol '{dataset.symbol}' is missing required DecisionResult.")