"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : reports.report_engine
Version      : 1.1.0
Status       : ORION Production V1.1 REFACTORED
===============================================================================

Report Engine responsible solely for transforming typed market dataset analysis,
scoring, and decision results into structured FullReport data models without
performing rendering, file IO, or analytical execution.
===============================================================================
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Sequence, Union

from models.market import MarketDataset
from engines.score_engine import ScoreResult
from engines.decision_engine import DecisionResult
from reports.report_models import (
    ReportMetadata,
    ReportSummary,
    SymbolReport,
    FullReport,
)

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class ReportEngineError(Exception):
    """Base exception class for all report engine related errors."""
    pass


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting report engine operation context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Report Engine
# =============================================================================

class ReportEngine:
    """
    Stateless report generation engine transforming typed result sequences into
    structured FullReport instances using pure dependency injection.
    """

    def __init__(
        self,
        project_version: str = "1.0.0",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._project_version = project_version
        self._logger_instance = logger if logger is not None else base_logger

        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "ReportEngine",
                "operation": "init",
            },
        )
        self._logger.info(f"ReportEngine initialized with version: {project_version}")

    def _get_logger(
        self,
        operation: Optional[str] = None,
    ) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "ReportEngine",
                "operation": operation,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def build_report(
        self,
        symbol_results: Sequence[Union[MarketDataset, Any]],
        execution_time_ms: float,
        report_name: str = "Market Scan",
    ) -> FullReport:
        """
        Builds and returns a complete FullReport from a sequence of scan results
        and execution metrics.
        """
        logger = self._get_logger(operation="build_report")
        logger.info(f"Building report '{report_name}' for {len(symbol_results)} results.")

        try:
            generated_at = datetime.now(timezone.utc)
            metadata = ReportMetadata(
                generated_at=generated_at,
                project_version=self._project_version,
                report_name=report_name,
                execution_time_ms=execution_time_ms,
            )

            total_symbols = len(symbol_results)
            buy_count = 0
            sell_count = 0
            hold_count = 0
            symbol_reports: list[SymbolReport] = []

            for item in symbol_results:
                # 1. Extract symbol
                symbol = getattr(item, "symbol", "UNKNOWN")
                if not symbol and isinstance(item, MarketDataset):
                    symbol = item.symbol or "UNKNOWN"

                # 2. Extract decision result container/object
                decision_obj = getattr(item, "decision", None)
                decision_str = "WAIT"
                confidence = 0.0
                reasons: list[str] = []
                warnings: list[str] = []

                if isinstance(decision_obj, DecisionResult):
                    dec_val = decision_obj.decision
                    decision_str = dec_val.value if hasattr(dec_val, "value") else str(dec_val).upper()
                    confidence = float(getattr(decision_obj, "confidence", 0.0))
                    reasons = list(getattr(decision_obj, "reasons", []))
                    warnings = list(getattr(decision_obj, "warnings", []))
                elif hasattr(decision_obj, "decision"):
                    dec_val = getattr(decision_obj, "decision")
                    decision_str = dec_val.value if hasattr(dec_val, "value") else str(dec_val).upper()
                    confidence = float(getattr(decision_obj, "confidence", 0.0))
                    reasons = list(getattr(decision_obj, "reasons", []))
                    warnings = list(getattr(decision_obj, "warnings", []))
                elif isinstance(decision_obj, str):
                    decision_str = decision_obj.upper()

                # Tally summary counts based on standard decision states
                if decision_str in {"FAVORABLE", "BUY", "STRONG_BUY"}:
                    buy_count += 1
                elif decision_str in {"UNFAVORABLE", "SELL", "STRONG_SELL"}:
                    sell_count += 1
                else:
                    hold_count += 1

                # 3. Extract score value
                score_obj = getattr(item, "score", None)
                score_val = 0.0
                if isinstance(score_obj, ScoreResult):
                    score_val = float(getattr(score_obj, "total_score", 0.0))
                elif hasattr(score_obj, "total_score"):
                    score_val = float(getattr(score_obj, "total_score", 0.0))
                elif hasattr(score_obj, "score"):
                    score_val = float(getattr(score_obj, "score", 0.0))
                elif isinstance(score_obj, (int, float)):
                    score_val = float(score_obj)

                # 4. Extract timeframes list
                timeframes = getattr(item, "timeframes", [])
                if not isinstance(timeframes, list) and hasattr(item, "dataframes"):
                    timeframes = list(item.dataframes.keys())
                if not isinstance(timeframes, list):
                    timeframes = []

                # 5. Gather extra diagnostic details
                details: dict[str, Any] = {
                    "reasons": reasons,
                    "warnings": warnings,
                }
                
                for attr_name in ["analysis", "indicators", "notes", "factors", "market_state", "profile"]:
                    attr_val = getattr(item, attr_name, None)
                    if attr_val is not None:
                        details[attr_name] = attr_val

                symbol_report = SymbolReport(
                    symbol=symbol,
                    decision=decision_str,
                    score=score_val,
                    confidence=confidence,
                    timeframes=timeframes,
                    details=details,
                )
                symbol_reports.append(symbol_report)

            summary = ReportSummary(
                total_symbols=total_symbols,
                buy_count=buy_count,
                sell_count=sell_count,
                hold_count=hold_count,
                execution_time_ms=execution_time_ms,
            )

            full_report = FullReport(
                metadata=metadata,
                summary=summary,
                symbols=symbol_reports,
            )

            logger.info(f"Report '{report_name}' built successfully with {total_symbols} symbol entries.")
            return full_report

        except Exception as e:
            logger.error(f"Failed to build report '{report_name}': {e}")
            raise ReportEngineError(f"Failed to build report: {e}") from e


# =============================================================================
# End Of File
# =============================================================================
