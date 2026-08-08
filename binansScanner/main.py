"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : main
Version      : 1.1.0
Status       : ORION Production V1.1 Updated with config parameter
===============================================================================

Unified entry point of the ORION project responsible solely for instantiating
the BootstrapRunner, executing the system initialization lifecycle, and running
the application runtime through clean separation of concerns and zero business logic.
===============================================================================
"""

from __future__ import annotations

from bootstrap.bootstrap_models import BootstrapOptions
from bootstrap.bootstrap_runner import BootstrapRunner


# =============================================================================
# Main Entry Point Function
# =============================================================================

def main() -> int:
    """
    Executes the system bootstrap sequence and starts the application runtime.
    Returns 0 on success and 1 on failure.
    """
    runner = BootstrapRunner()

    options = BootstrapOptions(
        environment="production",
        debug=False,
        config={},
    )

    result = runner.run(options)

    if not result.success:
        return 1

    runtime = runner.service().runtime()
    runtime.run()

    return 0


# =============================================================================
# Execution Guard
# =============================================================================

if __name__ == "__main__":
    raise SystemExit(main())


# =============================================================================
# End Of File
# =============================================================================