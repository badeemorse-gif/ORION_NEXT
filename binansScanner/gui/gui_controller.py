"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : gui.gui_controller
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

Thin GUI Controller layer responsible solely for delegating requests and state
queries directly to the underlying GuiService without containing any logging,
business logic, validation, or UI widget dependencies.
===============================================================================
"""

from __future__ import annotations

from gui.gui_models import (
    GuiNotification,
    GuiResult,
    GuiState,
)
from gui.gui_service import (
    GuiService,
)


# =============================================================================
# GUI Controller
# =============================================================================

class GuiController:
    """
    Thin proxy controller providing a clean delegation interface over the
    GuiService for managing GUI states, notifications, and operations.
    """

    def __init__(self, service: GuiService) -> None:
        self._service = service

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def state(self) -> GuiState:
        """
        Delegates fetching the current GUI state to the underlying GUI service.
        """
        return self._service.state()

    def update_state(self, state: GuiState) -> None:
        """
        Delegates updating the GUI state snapshot to the underlying GUI service.
        """
        self._service.set_state(state)

    def notify(self, notification: GuiNotification) -> None:
        """
        Delegates adding a new GUI notification to the underlying GUI service.
        """
        self._service.add_notification(notification)

    def notifications(self) -> tuple[GuiNotification, ...]:
        """
        Delegates fetching all stored GUI notifications to the underlying GUI service.
        """
        return self._service.notifications()

    def clear_notifications(self) -> None:
        """
        Delegates clearing all GUI notifications to the underlying GUI service.
        """
        self._service.clear_notifications()

    def execute(self) -> GuiResult:
        """
        Delegates executing pending GUI operations to the underlying GUI service.
        """
        return self._service.execute()


# =============================================================================
# End Of File
# =============================================================================