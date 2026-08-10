"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : api.api_server
Version      : 1.1.0
Status       : ORION Production V1.0
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

from api.api_models import ApiRequest
from api.api_router import ApiRouter, ApiRouterError

base_logger = logging.getLogger(__name__)


class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting API server context attributes into log entries."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


class ApiServer:
    """FastAPI transport wrapper around the framework-agnostic ApiRouter."""

    def __init__(self, router: Optional[ApiRouter] = None, logger: Optional[logging.Logger] = None) -> None:
        self._logger_instance = logger if logger is not None else base_logger
        self._logger = LoggerAdapter(self._logger_instance, {"component": "ApiServer", "operation": "init"})
        self.router = router if router is not None else ApiRouter(logger=self._logger_instance)
        self.app = FastAPI(title="ORION_NEXT", version="1.1")
        self._register_routes()
        self._logger.info("ApiServer initialized successfully with routes registered.")

    @staticmethod
    async def _request_body(request: Request, default_endpoint: str) -> ApiRequest:
        body = await request.json()
        return ApiRequest(
            request_id=body.get("request_id", "unknown"),
            endpoint=body.get("endpoint", default_endpoint),
            payload=body.get("payload", {}),
        )

    @staticmethod
    def _json_response(payload: dict[str, Any], status_code: int) -> JSONResponse:
        return JSONResponse(content=payload, status_code=status_code)

    def _register_routes(self) -> None:
        @self.app.get("/health")
        async def health_endpoint() -> JSONResponse:
            try:
                response = self.router.health()
                return self._json_response(response.payload | {"success": response.success, "message": response.message}, 200)
            except ApiRouterError as err:
                return self._json_response({"success": False, "message": str(err)}, 500)
            except Exception as err:
                return self._json_response({"success": False, "message": f"Internal server error: {err}"}, 500)

        @self.app.get("/scheduler/state")
        async def scheduler_state_endpoint() -> JSONResponse:
            try:
                response = self.router.scheduler_state()
                return self._json_response(response.payload | {"success": response.success, "message": response.message}, 200)
            except ApiRouterError as err:
                return self._json_response({"success": False, "message": str(err)}, 500)
            except Exception as err:
                return self._json_response({"success": False, "message": f"Internal server error: {err}"}, 500)

        @self.app.get("/scheduler/jobs")
        async def scheduler_jobs_endpoint() -> JSONResponse:
            try:
                response = self.router.registered_jobs()
                return self._json_response(response.payload | {"success": response.success, "message": response.message}, 200)
            except ApiRouterError as err:
                return self._json_response({"success": False, "message": str(err)}, 500)
            except Exception as err:
                return self._json_response({"success": False, "message": f"Internal server error: {err}"}, 500)

        @self.app.post("/pipeline/run")
        async def pipeline_run_endpoint(request: Request) -> JSONResponse:
            try:
                api_request = await self._request_body(request, "/pipeline/run")
                response = self.router.run_symbol(request=api_request)
                return self._json_response(
                    response.payload | {"success": response.success, "message": response.message},
                    200 if response.success else 422,
                )
            except ApiRouterError as err:
                return self._json_response({"success": False, "message": str(err)}, 500)
            except Exception as err:
                return self._json_response({"success": False, "message": f"Internal server error: {err}"}, 500)

        @self.app.post("/report/export")
        async def report_export_endpoint(request: Request) -> JSONResponse:
            try:
                api_request = await self._request_body(request, "/report/export")
                response = self.router.export_report(request=api_request)
                return self._json_response(response.payload | {"success": response.success, "message": response.message}, 200)
            except ApiRouterError as err:
                return self._json_response({"success": False, "message": str(err)}, 500)
            except Exception as err:
                return self._json_response({"success": False, "message": f"Internal server error: {err}"}, 500)


__all__ = ["ApiServer", "LoggerAdapter"]
