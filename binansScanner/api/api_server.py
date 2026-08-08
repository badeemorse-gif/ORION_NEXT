"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : api.api_server
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

FastAPI Server implementation serving as the sole web framework transport layer
binding HTTP endpoints and payloads directly to the abstract ApiRouter without
containing any core business or scheduling logic.
===============================================================================
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.api_router import ApiRouter, ApiRouterError
from api.api_models import ApiRequest

base_logger = logging.getLogger(__name__)


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting API server context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# API Server Transport Layer
# =============================================================================

class ApiServer:
    """
    FastAPI-based server instance wrapping application routes and delegating
    HTTP requests cleanly to the framework-agnostic ApiRouter layer.
    """

    def __init__(
        self,
        router: Optional[ApiRouter] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._logger_instance = logger if logger is not None else base_logger
        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "ApiServer",
                "operation": "init",
            },
        )

        self.router = router if router is not None else ApiRouter(logger=self._logger_instance)
        self.app = FastAPI(
            title="ORION_NEXT",
            version="1.0",
        )

        self._register_routes()
        self._logger.info("ApiServer initialized successfully with routes registered.")

    def _get_logger(self, operation: Optional[str] = None) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "ApiServer",
                "operation": operation,
            },
        )

    # -------------------------------------------------------------------------
    # Route Registrations
    # -------------------------------------------------------------------------

    def _register_routes(self) -> None:
        """
        Registers all HTTP endpoints on the FastAPI application instance.
        """

        @self.app.get("/health")
        async def health_endpoint() -> JSONResponse:
            logger = self._get_logger(operation="health_endpoint")
            logger.debug("Received GET /health request.")
            try:
                response = self.router.health()
                return JSONResponse(
                    status_code=200,
                    content=response.payload | {
                        "success": response.success,
                        "message": response.message,
                    },
                )
            except ApiRouterError as err:
                logger.error(f"Router error in health endpoint: {err}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": str(err),
                    },
                )
            except Exception as err:
                logger.error(f"Unexpected error in health endpoint: {err}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": f"Internal server error: {err}",
                    },
                )

        @self.app.get("/scheduler/state")
        async def scheduler_state_endpoint() -> JSONResponse:
            logger = self._get_logger(operation="scheduler_state_endpoint")
            logger.debug("Received GET /scheduler/state request.")
            try:
                response = self.router.scheduler_state()
                return JSONResponse(
                    status_code=200,
                    content=response.payload | {
                        "success": response.success,
                        "message": response.message,
                    },
                )
            except ApiRouterError as err:
                logger.error(f"Router error in scheduler state endpoint: {err}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": str(err),
                    },
                )
            except Exception as err:
                logger.error(f"Unexpected error in scheduler state endpoint: {err}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": f"Internal server error: {err}",
                    },
                )

        @self.app.get("/scheduler/jobs")
        async def scheduler_jobs_endpoint() -> JSONResponse:
            logger = self._get_logger(operation="scheduler_jobs_endpoint")
            logger.debug("Received GET /scheduler/jobs request.")
            try:
                response = self.router.registered_jobs()
                return JSONResponse(
                    status_code=200,
                    content=response.payload | {
                        "success": response.success,
                        "message": response.message,
                    },
                )
            except ApiRouterError as err:
                logger.error(f"Router error in scheduler jobs endpoint: {err}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": str(err),
                    },
                )
            except Exception as err:
                logger.error(f"Unexpected error in scheduler jobs endpoint: {err}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": f"Internal server error: {err}",
                    },
                )

        @self.app.post("/report/export")
        async def report_export_endpoint(request: Request) -> JSONResponse:
            logger = self._get_logger(operation="report_export_endpoint")
            logger.debug("Received POST /report/export request.")
            try:
                body = await request.json()
                api_request = ApiRequest(
                    request_id=body.get("request_id", "unknown"),
                    endpoint=body.get("endpoint", "/report/export"),
                    payload=body.get("payload", {}),
                )
                response = self.router.export_report(request=api_request)
                return JSONResponse(
                    status_code=200,
                    content=response.payload | {
                        "success": response.success,
                        "message": response.message,
                    },
                )
            except ApiRouterError as err:
                logger.error(f"Router error in report export endpoint: {err}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": str(err),
                    },
                )
            except Exception as err:
                logger.error(f"Unexpected error in report export endpoint: {err}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": f"Internal server error: {err}",
                    },
                )


# =============================================================================
# End Of File
# =============================================================================