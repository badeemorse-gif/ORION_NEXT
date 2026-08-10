"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : api.api_router
Version      : 1.1.0
Status       : ORION Production V1.0
===============================================================================

Framework-agnostic API Router delegation layer responsible solely for routing
request operations to the underlying ApiService without containing web framework,
HTTP transport, or routing library dependencies.
===============================================================================
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from api.api_models import ApiRequest, ApiResponse
from api.api_service import ApiService

base_logger = logging.getLogger(__name__)


class ApiRouterError(Exception):
    """Base exception class for all API router related errors."""


class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting API router context attributes into log entries."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


class ApiRouter:
    """Framework-agnostic router delegating operations to ApiService."""

    def __init__(
        self,
        service: Optional[ApiService] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._logger_instance = logger if logger is not None else base_logger
        self._logger = LoggerAdapter(
            self._logger_instance,
            {"component": "ApiRouter", "operation": "init"},
        )
        self._service = service if service is not None else ApiService(logger=self._logger_instance)
        self._logger.info("ApiRouter initialized successfully.")

    def _get_logger(self, operation: Optional[str] = None) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {"component": "ApiRouter", "operation": operation},
        )

    def health(self) -> ApiResponse:
        try:
            return self._service.health()
        except Exception as err:
            self._get_logger("health").error("Health delegation failed: %s", err)
            raise ApiRouterError(f"Health check delegation failed: {err}") from err

    def scheduler_state(self) -> ApiResponse:
        try:
            return self._service.scheduler_state()
        except Exception as err:
            self._get_logger("scheduler_state").error("Scheduler state delegation failed: %s", err)
            raise ApiRouterError(f"Scheduler state delegation failed: {err}") from err

    def registered_jobs(self) -> ApiResponse:
        try:
            return self._service.registered_jobs()
        except Exception as err:
            self._get_logger("registered_jobs").error("Registered jobs delegation failed: %s", err)
            raise ApiRouterError(f"Registered jobs delegation failed: {err}") from err

    def run_symbol(self, request: ApiRequest) -> ApiResponse:
        try:
            return self._service.run_symbol(request=request)
        except Exception as err:
            self._get_logger("run_symbol").error("Pipeline delegation failed: %s", err)
            raise ApiRouterError(f"Pipeline execution delegation failed: {err}") from err

    def export_report(self, request: ApiRequest) -> ApiResponse:
        try:
            return self._service.export_report(request=request)
        except Exception as err:
            self._get_logger("export_report").error("Export delegation failed: %s", err)
            raise ApiRouterError(f"Export report delegation failed: {err}") from err

    def available_routes(self) -> tuple[str, ...]:
        return (
            "health",
            "scheduler_state",
            "registered_jobs",
            "run_symbol",
            "export_report",
        )


__all__ = ["ApiRouter", "ApiRouterError", "LoggerAdapter"]
