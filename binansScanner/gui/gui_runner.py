"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : gui.gui_runner
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

Thin GUI Runner layer responsible solely for managing the lifecycle execution
of the abstract GuiWindow shell (initialization, showing, and shutdown) without
containing any GUI frameworks, toolkits, widgets, or business logic.
===============================================================================
"""

from __future__ import annotations

from gui.gui_window import GuiWindow


# =============================================================================
# GUI Runner
# =============================================================================

class GuiRunner:
    """
    Thin execution runner providing a clean lifecycle control interface over
    the abstract GuiWindow shell.
    """

    def __init__(self, window: GuiWindow) -> None:
        self._window = window

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def run(self) -> None:
        """
        Initializes the GUI window shell if not already initialized and triggers
        the display command.
        """
        if not self._window.initialized():
            self._window.initialize()
        self._window.show()

    def shutdown(self) -> None:
        """
        Triggers the closure lifecycle hook on the underlying GUI window shell.
        """
        self._window.close()

    def window(self) -> GuiWindow:
        """
        Returns the managed abstract GUI window shell instance.
        """
        return self._window


# =============================================================================
# End Of File
# =============================================================================