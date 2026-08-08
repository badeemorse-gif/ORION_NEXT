"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : api.api_service
Version      : 1.0.2
Status       : ORION Production V1.0 APPROVED
===============================================================================

API Service Facade responsible solely for orchestrating core business operations,
scheduler states, and export handlers without containing web framework elements,
HTTP routing, or request/response protocols.
===============================================================================
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Optional

from api.api_models import (
    ApiRequest,
    ApiResponse,
)

from scheduler.scheduler_service import SchedulerService
from reports.report_exporter import ReportExporter
from reports.html_report import HtmlReportRenderer
from reports.json_report import JsonReportRenderer

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class ApiServiceError(Exception):
    """Base exception class for all API service related errors."""
    pass


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting API service context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(
            f"{k}={v}" for k, v in context.items() if v is not None
        )
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# API Service Facade
# =============================================================================

class ApiService:
    """
    Facade service coordinating system health, scheduler operations, and report
    exports completely decoupled from any specific web transport or framework.
    """

    def __init__(
        self,
        scheduler: Optional[SchedulerService] = None,
        report_exporter: Optional[ReportExporter] = None,
        html_renderer: Optional[HtmlReportRenderer] = None,
        json_renderer: Optional[JsonReportRenderer] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._logger_instance = logger if logger is not None else base_logger

        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "ApiService",
                "operation": "init",
            },
        )

        self._scheduler = (
            scheduler
            if scheduler is not None
            else SchedulerService(logger=self._logger_instance)
        )

        if report_exporter is not None:
            self._report_exporter = report_exporter
        else:
            resolved_html_renderer = (
                html_renderer
                if html_renderer is not None
                else HtmlReportRenderer(logger=self._logger_instance)
            )

            resolved_json_renderer = (
                json_renderer
                if json_renderer is not None
                else JsonReportRenderer(logger=self._logger_instance)
            )

            self._report_exporter = ReportExporter(
                html_renderer=resolved_html_renderer,
                json_renderer=resolved_json_renderer,
                logger=self._logger_instance,
            )

        self._logger.info("ApiService initialized successfully.")

    def _get_logger(self, operation: Optional[str] = None) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "ApiService",
                "operation": operation,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def health(self) -> ApiResponse:
        """
        Returns system health status response.
        """
        logger = self._get_logger(operation="health")
        logger.debug("Health check requested.")

        return ApiResponse(
            success=True,
            message="OK",
            payload={},
        )

    def scheduler_state(self) -> ApiResponse:
        """
        Retrieves the current runtime state of the scheduler service.
        """
        logger = self._get_logger(operation="scheduler_state")
        logger.info("Fetching scheduler state.")

        try:
            state_obj = self._scheduler.state()
            state_dict = asdict(state_obj)

            return ApiResponse(
                success=True,
                message="Scheduler state retrieved successfully.",
                payload=state_dict,
            )

        except Exception as err:
            logger.error(f"Failed to retrieve scheduler state: {err}")
            raise ApiServiceError(
                f"Failed to retrieve scheduler state: {err}"
            ) from err

    def registered_jobs(self) -> ApiResponse:
        """
        Retrieves all currently registered jobs from the scheduler service.
        """
        logger = self._get_logger(operation="registered_jobs")
        logger.info("Fetching registered jobs.")

        try:
            jobs_tuple = self._scheduler.registered_jobs()
            jobs_list = [asdict(job) for job in jobs_tuple]

            return ApiResponse(
                success=True,
                message="Registered jobs retrieved successfully.",
                payload={
                    "jobs": jobs_list,
                    "count": len(jobs_list),
                },
            )

        except Exception as err:
            logger.error(f"Failed to retrieve registered jobs: {err}")
            raise ApiServiceError(
                f"Failed to retrieve registered jobs: {err}"
            ) from err

    def export_report(self, request: ApiRequest) -> ApiResponse:
        """
        Placeholder report export endpoint logic pending full pipeline integration.
        """
        logger = self._get_logger(operation="export_report")
        logger.info(
            f"Export report requested with request_id: {request.request_id}"
        )

        return ApiResponse(
            success=False,
            message="Not implemented yet.",
            payload={
                "request_id": request.request_id,
                "endpoint": request.endpoint,
            },
        )


# =============================================================================
# End Of File
# =============================================================================