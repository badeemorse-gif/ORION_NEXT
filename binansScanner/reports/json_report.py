"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : reports.json_report
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

JSON Report Renderer responsible solely for transforming a FullReport instance
into a formatted JSON string representation using standard Python libraries
with robust datetime serialization.
===============================================================================
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any, Optional

from reports.report_models import FullReport

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class JsonReportRendererError(Exception):
    """Base exception class for all JSON report rendering related errors."""
    pass


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting JSON renderer operation context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# JSON Report Renderer
# =============================================================================

class JsonReportRenderer:
    """
    Stateless JSON report renderer converting FullReport domain models into
    fully structured JSON strings using standard library json serialization.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger_instance = logger if logger is not None else base_logger

        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "JsonReportRenderer",
                "operation": "init",
            },
        )
        self._logger.info("JsonReportRenderer initialized successfully.")

    def _get_logger(self, operation: Optional[str] = None) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "JsonReportRenderer",
                "operation": operation,
            },
        )

    # -------------------------------------------------------------------------
    # Internal Serialization Helper
    # -------------------------------------------------------------------------

    def _default_serializer(self, obj: Any) -> Any:
        """
        Custom JSON serializer handling datetime objects into ISO 8601 strings.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def render(self, report: FullReport, indent: int = 4) -> str:
        """
        Renders a FullReport instance into a formatted JSON string.
        """
        logger = self._get_logger(operation="render")
        logger.info(f"Rendering JSON report: '{report.metadata.report_name}'")

        try:
            # Convert dataclass hierarchy to native dictionary
            report_dict = asdict(report)

            # Serialize to JSON string with custom encoder handler for datetime objects
            json_string = json.dumps(
                report_dict,
                default=self._default_serializer,
                ensure_ascii=False,
                indent=indent,
            )

            logger.info("JSON report rendered successfully.")
            return json_string

        except Exception as e:
            logger.error(f"Failed to render JSON report: {e}")
            raise JsonReportRendererError(f"Failed to render JSON report: {e}") from e


# =============================================================================
# End Of File
# =============================================================================