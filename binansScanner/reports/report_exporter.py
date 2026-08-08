"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : reports.report_exporter
Version      : 1.1.0
Status       : ORION Production V1.1 REFACTORED
===============================================================================

Report Exporter Facade responsible solely for coordinating report export operations
across various file formats using injected renderers and pathlib file operations
with strict UTF-8 encoding.
===============================================================================
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
import logging
from typing import Any, Optional

from reports.report_models import FullReport
from reports.html_report import HtmlReportRenderer
from reports.json_report import JsonReportRenderer

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class ReportExporterError(Exception):
    """Base exception class for all report exporter related errors."""
    pass


# =============================================================================
# Report Format Enum
# =============================================================================

class ReportFormat(Enum):
    """Enumeration of supported export report formats."""
    HTML = "html"
    JSON = "json"


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting report exporter operation context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Report Exporter Facade
# =============================================================================

class ReportExporter:
    """
    Stateless report exporter facade coordinating file generation and format
    selection using mandatory pure dependency injection for renderers and standard pathlib operations.
    """

    def __init__(
        self,
        html_renderer: HtmlReportRenderer,
        json_renderer: JsonReportRenderer,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if html_renderer is None:
            raise ReportExporterError("HtmlReportRenderer must be provided via dependency injection.")
        if json_renderer is None:
            raise ReportExporterError("JsonReportRenderer must be provided via dependency injection.")

        self._html_renderer = html_renderer
        self._json_renderer = json_renderer
        self._logger_instance = logger if logger is not None else base_logger

        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "ReportExporter",
                "operation": "init",
            },
        )
        self._logger.info("ReportExporter initialized successfully.")

    def _get_logger(self, operation: Optional[str] = None) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "ReportExporter",
                "operation": operation,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def export(
        self,
        report: FullReport,
        output_path: Path,
        report_format: ReportFormat,
    ) -> Path:
        """
        Exports a FullReport instance to a specified file path in the requested format.
        """
        logger = self._get_logger(operation="export")
        logger.info(f"Exporting report '{report.metadata.report_name}' to format '{report_format.value}' at path: {output_path}")

        try:
            # Ensure parent directories exist
            output_path.parent.mkdir(parents=True, exist_ok=True)

            content = ""
            if report_format == ReportFormat.HTML:
                content = self._html_renderer.render(report)
            elif report_format == ReportFormat.JSON:
                content = self._json_renderer.render(report)
            else:
                raise ReportExporterError(f"Unsupported report format: {report_format}")

            # Write content using UTF-8 encoding via pathlib
            output_path.write_text(content, encoding="utf-8")
            logger.info(f"Successfully exported report to '{output_path}'.")
            return output_path

        except Exception as e:
            logger.error(f"Failed to export report to '{output_path}': {e}")
            raise ReportExporterError(f"Failed to export report: {e}") from e

    def export_html(self, report: FullReport, output_path: Path) -> Path:
        """
        Exports a FullReport instance as an HTML file.
        """
        return self.export(report, output_path, ReportFormat.HTML)

    def export_json(self, report: FullReport, output_path: Path) -> Path:
        """
        Exports a FullReport instance as a JSON file.
        """
        return self.export(report, output_path, ReportFormat.JSON)


# =============================================================================
# End Of File
# =============================================================================
