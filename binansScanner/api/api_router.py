"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : api.api_router
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

Framework-agnostic API Router delegation layer responsible solely for routing
request operations to the underlying ApiService without containing web framework,
HTTP transport, or routing library dependencies.
===============================================================================
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from api.api_models import (
    ApiRequest,
    ApiResponse,
)
from api.api_service import ApiService

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class ApiRouterError(Exception):
    """Base exception class for all API router related errors."""
    pass


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting API router context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# API Router Delegation Layer
# =============================================================================

class ApiRouter:
    """
    Framework-agnostic router delegating operation calls to the ApiService
    while remaining completely isolated from any specific web framework or transport.
    """

    def __init__(
        self,
        service: Optional[ApiService] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._logger_instance = logger if logger is not None else base_logger
        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "ApiRouter",
                "operation": "init",
            },
        )

        self._service = service if service is not None else ApiService(logger=self._logger_instance)
        self._logger.info("ApiRouter initialized successfully.")

    def _get_logger(self, operation: Optional[str] = None) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "ApiRouter",
                "operation": operation,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def health(self) -> ApiResponse:
        """
        Delegates health check request to the API service.
        """
        logger = self._get_logger(operation="health")
        logger.debug("Delegating health check operation.")
        try:
            return self._service.health()
        except Exception as err:
            logger.error(f"Error during health check delegation: {err}")
            raise ApiRouterError(f"Health check delegation failed: {err}") from err

    def scheduler_state(self) -> ApiResponse:
        """
        Delegates scheduler state request to the API service.
        """
        logger = self._get_logger(operation="scheduler_state")
        logger.debug("Delegating scheduler state operation.")
        try:
            return self._service.scheduler_state()
        except Exception as err:
            logger.error(f"Error during scheduler state delegation: {err}")
            raise ApiRouterError(f"Scheduler state delegation failed: {err}") from err

    def registered_jobs(self) -> ApiResponse:
        """
        Delegates registered jobs request to the API service.
        """
        logger = self._get_logger(operation="registered_jobs")
        logger.debug("Delegating registered jobs operation.")
        try:
            return self._service.registered_jobs()
        except Exception as err:
            logger.error(f"Error during registered jobs delegation: {err}")
            raise ApiRouterError(f"Registered jobs delegation failed: {err}") from err

    def export_report(self, request: ApiRequest) -> ApiResponse:
        """
        Delegates report export request to the API service.
        """
        logger = self._get_logger(operation="export_report")
        logger.debug(f"Delegating export report operation for request_id: {request.request_id}")
        try:
            return self._service.export_report(request=request)
        except Exception as err:
            logger.error(f"Error during export report delegation: {err}")
            raise ApiRouterError(f"Export report delegation failed: {err}") from err

    def available_routes(self) -> tuple[str, ...]:
        """
        Returns a tuple of all supported logical route identifiers.
        """
        return (
            "health",
            "scheduler_state",
            "registered_jobs",
            "export_report",
        )


# =============================================================================
# End Of File
# =============================================================================