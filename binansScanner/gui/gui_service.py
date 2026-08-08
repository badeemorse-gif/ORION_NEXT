"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : gui.gui_service
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

GUI Service layer managing user interface state, notifications, and actions
completely decoupled from any graphical widgets, UI frameworks, or controllers.
===============================================================================
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from gui.gui_models import (
    GuiAction,
    GuiNotification,
    GuiResult,
    GuiState,
)

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class GuiServiceError(Exception):
    """Base exception class for all GUI service related errors."""
    pass


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting GUI service context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# GUI Service Manager
# =============================================================================

class GuiService:
    """
    Service layer managing GUI state transitions, notification feeds, and action
    registrations without dependency on any display framework or window engine.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger_instance = logger if logger is not None else base_logger
        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "GuiService",
                "operation": "init",
            },
        )

        self._state: GuiState = GuiState(
            connected=False,
            running=False,
            busy=False,
            metadata={},
        )
        self._notifications: list[GuiNotification] = []
        self._actions: dict[str, GuiAction] = {}

        self._logger.info("GuiService initialized successfully.")

    def _get_logger(self, operation: Optional[str] = None) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "GuiService",
                "operation": operation,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def state(self) -> GuiState:
        """
        Returns the current state snapshot of the GUI.
        """
        return self._state

    def set_state(self, state: GuiState) -> None:
        """
        Replaces the current GUI state with a new state snapshot.
        """
        logger = self._get_logger(operation="set_state")
        logger.info("Updating GUI state snapshot.")
        self._state = state

    def add_notification(self, notification: GuiNotification) -> None:
        """
        Appends a new GUI notification to the notification queue.
        """
        logger = self._get_logger(operation="add_notification")
        logger.info(f"Adding notification with title '{notification.title}'.")
        self._notifications.append(notification)

    def notifications(self) -> tuple[GuiNotification, ...]:
        """
        Returns an immutable tuple of all stored GUI notifications.
        """
        return tuple(self._notifications)

    def clear_notifications(self) -> None:
        """
        Clears all stored GUI notifications.
        """
        logger = self._get_logger(operation="clear_notifications")
        logger.info("Clearing all GUI notifications.")
        self._notifications.clear()

    def register_action(self, action: GuiAction) -> None:
        """
        Registers an interactive GUI action.
        Raises GuiServiceError if the action name is already registered.
        """
        logger = self._get_logger(operation="register_action")
        logger.info(f"Registering GUI action '{action.name}'.")

        if not action.name:
            raise GuiServiceError("Cannot register GUI action with an empty name.")

        if action.name in self._actions:
            logger.error(f"GUI action '{action.name}' is already registered.")
            raise GuiServiceError(f"GUI action '{action.name}' is already registered.")

        self._actions[action.name] = action
        logger.info(f"GUI action '{action.name}' registered successfully.")

    def actions(self) -> tuple[GuiAction, ...]:
        """
        Returns an immutable tuple of all registered GUI actions.
        """
        return tuple(self._actions.values())

    def execute(self) -> GuiResult:
        """
        Executes pending GUI operations. Placeholder method for future expansions.
        """
        logger = self._get_logger(operation="execute")
        logger.info("Executing GUI service operation.")
        return GuiResult(
            success=True,
            message="GUI service executed successfully.",
            metadata={},
        )


# =============================================================================
# End Of File
# =============================================================================