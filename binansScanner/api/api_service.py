"""Framework-agnostic API service facade for ORION."""
from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from api.api_models import ApiRequest, ApiResponse
from core.pipeline import Pipeline
from models.report import ReportResult
from reports.html_report import HtmlReportRenderer
from reports.json_report import JsonReportRenderer
from reports.report_exporter import ReportExporter, ReportFormat
from scheduler.scheduler_service import SchedulerService

base_logger = logging.getLogger(__name__)


class ApiServiceError(Exception):
    """Base exception for API service failures."""


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter adding API service context."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(
            f"{key}={value}" for key, value in context.items() if value is not None
        )
        return (f"[{context_str}] {msg}" if context_str else msg), kwargs


class ApiService:
    """Coordinate API operations without HTTP/framework concerns."""

    def __init__(
        self,
        scheduler: Optional[SchedulerService] = None,
        report_exporter: Optional[ReportExporter] = None,
        html_renderer: Optional[HtmlReportRenderer] = None,
        json_renderer: Optional[JsonReportRenderer] = None,
        pipeline: Optional[Pipeline] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._logger_instance = logger if logger is not None else base_logger
        self._scheduler = scheduler or SchedulerService(logger=self._logger_instance)
        self._pipeline = pipeline
        if report_exporter is not None:
            self._report_exporter = report_exporter
        else:
            self._report_exporter = ReportExporter(
                html_renderer=html_renderer or HtmlReportRenderer(),
                json_renderer=json_renderer or JsonReportRenderer(),
                logger=self._logger_instance,
            )

    def _get_logger(self, operation: Optional[str] = None) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {"component": "ApiService", "operation": operation},
        )

    def health(self) -> ApiResponse:
        """Return service health."""
        return ApiResponse(success=True, message="OK", payload={})

    def scheduler_state(self) -> ApiResponse:
        """Return a JSON-safe scheduler runtime state snapshot."""
        logger = self._get_logger("scheduler_state")
        try:
            state = self._scheduler.state()
            payload = asdict(state)
            if state.last_tick is not None:
                payload["last_tick"] = state.last_tick.isoformat()
            return ApiResponse(
                success=True,
                message="Scheduler state retrieved successfully.",
                payload=payload,
            )
        except Exception as err:
            logger.error("Failed to retrieve scheduler state: %s", err)
            raise ApiServiceError(f"Failed to retrieve scheduler state: {err}") from err

    def registered_jobs(self) -> ApiResponse:
        """Return JSON-safe registered scheduler job definitions without callbacks."""
        logger = self._get_logger("registered_jobs")
        try:
            jobs = [asdict(job.definition) for job in self._scheduler.registered_jobs()]
            return ApiResponse(
                success=True,
                message="Registered jobs retrieved successfully.",
                payload={"jobs": jobs, "count": len(jobs)},
            )
        except Exception as err:
            logger.error("Failed to retrieve registered jobs: %s", err)
            raise ApiServiceError(f"Failed to retrieve registered jobs: {err}") from err

    def run_symbol(self, request: ApiRequest) -> ApiResponse:
        """Run one symbol through the canonical application pipeline."""
        if not isinstance(request, ApiRequest):
            raise ApiServiceError("run_symbol requires an ApiRequest.")
        if self._pipeline is None:
            raise ApiServiceError("Canonical pipeline is not configured for this API service.")

        payload = request.payload
        symbol = payload.get("symbol")
        timeframes = payload.get("timeframes")
        quantity = payload.get("quantity")

        if not isinstance(symbol, str) or not symbol.strip():
            raise ApiServiceError("run_symbol requires payload['symbol'] as a non-empty string.")
        if not isinstance(timeframes, list) or not timeframes or not all(
            isinstance(item, str) and item.strip() for item in timeframes
        ):
            raise ApiServiceError(
                "run_symbol requires payload['timeframes'] as a non-empty list of strings."
            )
        if quantity is not None:
            try:
                quantity = float(quantity)
            except (TypeError, ValueError) as err:
                raise ApiServiceError("run_symbol payload['quantity'] must be numeric.") from err

        try:
            result = self._pipeline.run_symbol(
                symbol=symbol.strip(),
                timeframes=timeframes,
                quantity=quantity,
            )
            execution_status = None
            if result.execution_result is not None:
                status = result.execution_result.status
                execution_status = getattr(status, "value", status)

            return ApiResponse(
                success=result.success,
                message=(
                    "Pipeline execution completed successfully."
                    if result.success
                    else "Pipeline execution failed."
                ),
                payload={
                    "request_id": request.request_id,
                    "symbol": result.symbol,
                    "success": result.success,
                    "failed_stage": result.failed_stage,
                    "error_message": result.error_message,
                    "elapsed_ms": result.elapsed_ms,
                    "execution_status": execution_status,
                    "report_available": result.report_result is not None,
                },
            )
        except Exception as err:
            self._get_logger("run_symbol").error("Failed to run pipeline: %s", err)
            raise ApiServiceError(f"Failed to run pipeline: {err}") from err

    def export_report(self, request: ApiRequest) -> ApiResponse:
        """Export a canonical ReportResult through ReportExporter.

        Required request payload keys are ``report``, ``output_path`` and
        ``format`` (``html`` or ``json``). The API layer never renders the
        report itself; it delegates to the canonical exporter boundary.
        """
        if not isinstance(request, ApiRequest):
            raise ApiServiceError("export_report requires an ApiRequest.")

        payload = request.payload
        report = payload.get("report")
        output_path = payload.get("output_path")
        requested_format = payload.get("format")

        if not isinstance(report, ReportResult):
            raise ApiServiceError(
                "export_report requires payload['report'] to be a ReportResult."
            )
        if output_path is None:
            raise ApiServiceError("export_report requires payload['output_path'].")

        if isinstance(requested_format, ReportFormat):
            selected_format = requested_format
        else:
            normalized_format = str(requested_format or "").strip().lower()
            try:
                selected_format = ReportFormat(normalized_format)
            except ValueError as err:
                raise ApiServiceError(
                    "export_report requires payload['format'] to be 'html' or 'json'."
                ) from err

        try:
            exported_path = self._report_exporter.export(
                report=report,
                output_path=Path(output_path),
                report_format=selected_format,
            )
            return ApiResponse(
                success=True,
                message="Report exported successfully.",
                payload={
                    "request_id": request.request_id,
                    "endpoint": request.endpoint,
                    "format": selected_format.value,
                    "output_path": str(exported_path),
                },
            )
        except Exception as err:
            self._get_logger("export_report").error("Failed to export report: %s", err)
            raise ApiServiceError(f"Failed to export report: {err}") from err


__all__ = ["ApiService", "ApiServiceError", "LoggerAdapter"]
