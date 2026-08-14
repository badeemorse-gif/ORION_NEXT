"""Canonical ReportResult export facade."""
from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from models.report import ReportAuditStatus, ReportResult
from reports.html_report import HtmlReportRenderer
from reports.json_report import JsonReportRenderer

base_logger = logging.getLogger(__name__)


class ReportExporterError(Exception):
    """Base exception for report exporter failures."""


class ReportFormat(Enum):
    HTML = "html"
    JSON = "json"


class LoggerAdapter(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{key}={value}" for key, value in context.items() if value is not None)
        return (f"[{context_str}] {msg}" if context_str else msg), kwargs


class ReportExporter:
    """Write canonical reports without translating audit status into pipeline success."""

    def __init__(
        self,
        html_renderer: HtmlReportRenderer,
        json_renderer: JsonReportRenderer,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if html_renderer is None or json_renderer is None:
            raise ReportExporterError("Canonical report renderers are required.")
        self._html_renderer = html_renderer
        self._json_renderer = json_renderer
        self._logger_instance = logger if logger is not None else base_logger

    def _get_logger(self, operation: Optional[str] = None) -> LoggerAdapter:
        return LoggerAdapter(self._logger_instance, {"component": "ReportExporter", "operation": operation})

    def export(self, report: ReportResult, output_path: Path, report_format: ReportFormat) -> Path:
        if not isinstance(report, ReportResult):
            raise ReportExporterError("ReportExporter accepts only the canonical ReportResult contract.")
        logger = self._get_logger("export")
        audit_status = report.audit.status.value
        logger.info("Writing report '%s' format=%s audit_status=%s path='%s'", report.metadata.report_name, report_format.value, audit_status, output_path)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if report_format == ReportFormat.HTML:
                content = self._html_renderer.render(report)
            elif report_format == ReportFormat.JSON:
                content = self._json_renderer.render(report)
            else:
                raise ReportExporterError(f"Unsupported report format: {report_format}")
            output_path.write_text(content, encoding="utf-8")
            if report.audit.status is ReportAuditStatus.COMPLETE:
                logger.info("Report artifact written; audit_status=COMPLETE (structural evidence only) path='%s'", output_path)
            else:
                logger.warning("Report evidence artifact written; audit_status=%s path='%s'", audit_status, output_path)
            return output_path
        except ReportExporterError:
            raise
        except Exception as exc:
            logger.error("Failed to write report artifact to '%s': %s", output_path, exc)
            raise ReportExporterError(f"Failed to export report: {exc}") from exc

    def export_html(self, report: ReportResult, output_path: Path) -> Path:
        return self.export(report, output_path, ReportFormat.HTML)

    def export_json(self, report: ReportResult, output_path: Path) -> Path:
        return self.export(report, output_path, ReportFormat.JSON)


__all__ = ["ReportExporter", "ReportExporterError", "ReportFormat"]
