"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : application.application_controller
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

Thin Application Controller layer responsible solely for delegating requests
and query calls directly to the underlying ApplicationService without containing
any business logic, validation, or infrastructure dependencies.
===============================================================================
"""

from __future__ import annotations

from application.application_models import (
    ApplicationRequest,
    ApplicationResponse,
    ApplicationStatus,
)

from application.application_service import (
    ApplicationService,
)


# =============================================================================
# Application Controller
# =============================================================================

class ApplicationController:
    """
    Thin proxy controller providing a clean delegation interface over the
    ApplicationService for handling high-level requests and status queries.
    """

    def __init__(self, service: ApplicationService) -> None:
        self._service = service

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def execute(self, request: ApplicationRequest) -> ApplicationResponse:
        """
        Delegates application request execution to the underlying application service.
        """
        return self._service.execute(request)

    def available_actions(self) -> tuple[str, ...]:
        """
        Delegates fetching available actions to the underlying application service.
        """
        return self._service.available_actions()

    def status(self) -> ApplicationStatus:
        """
        Delegates retrieving the application status snapshot to the application service.
        """
        return self._service.status()


# =============================================================================
# End Of File
# =============================================================================