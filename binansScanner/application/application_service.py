"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : application.application_service
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

Application Service Facade orchestrating high-level command actions through
a modular registry pattern completely decoupled from business logic, transport
mechanisms, or infrastructure dependencies.
===============================================================================
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from application.application_models import (
    ApplicationRequest,
    ApplicationResponse,
    ApplicationStatus,
)

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class ApplicationServiceError(Exception):
    """Base exception class for all application service related errors."""
    pass


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting application service context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Application Service Orchestrator
# =============================================================================

class ApplicationService:
    """
    Central application orchestrator managing action handlers and executing
    high-level requests in a decoupled, unified service layer.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger_instance = logger if logger is not None else base_logger
        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "ApplicationService",
                "operation": "init",
            },
        )

        self._actions: dict[str, Callable[[ApplicationRequest], ApplicationResponse]] = {}
        self._logger.info("ApplicationService initialized successfully.")

    def _get_logger(self, operation: Optional[str] = None) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "ApplicationService",
                "operation": operation,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def register_action(
        self,
        name: str,
        handler: Callable[[ApplicationRequest], ApplicationResponse],
    ) -> None:
        """
        Registers a new action handler within the application action registry.
        Raises ApplicationServiceError if the action name is already registered.
        """
        logger = self._get_logger(operation="register_action")
        logger.info(f"Registering application action '{name}'.")

        if not name:
            raise ApplicationServiceError("Cannot register action with an empty name.")

        if name in self._actions:
            logger.error(f"Action '{name}' is already registered.")
            raise ApplicationServiceError(f"Action '{name}' is already registered.")

        self._actions[name] = handler
        logger.info(f"Action '{name}' registered successfully.")

    def available_actions(self) -> tuple[str, ...]:
        """
        Returns a sorted tuple of all currently registered action names.
        """
        return tuple(sorted(self._actions.keys()))

    def execute(self, request: ApplicationRequest) -> ApplicationResponse:
        """
        Executes a registered application action based on the request's action identifier.
        Raises ApplicationServiceError if the requested action does not exist.
        """
        logger = self._get_logger(operation="execute")
        logger.info(f"Executing request_id '{request.request_id}' for action '{request.action}'.")

        if request.action not in self._actions:
            logger.error(f"Action '{request.action}' is not supported or registered.")
            raise ApplicationServiceError(f"Action '{request.action}' is not supported or registered.")

        handler = self._actions[request.action]
        try:
            response = handler(request)
            logger.info(f"Action '{request.action}' executed successfully for request_id '{request.request_id}'.")
            return response
        except Exception as err:
            logger.error(f"Error executing action '{request.action}': {err}")
            raise ApplicationServiceError(f"Error executing action '{request.action}': {err}") from err

    def status(self) -> ApplicationStatus:
        """
        Returns a runtime status snapshot of the application service.
        """
        return ApplicationStatus(
            running=True,
            current_task=None,
            active_jobs=0,
            metadata={},
        )


# =============================================================================
# End Of File
# =============================================================================