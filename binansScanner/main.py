"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : main
Version      : 1.2.0
Status       : ORION Production Entry Point
===============================================================================

Unified entry point for the ORION application lifecycle. Bootstrap is responsible
for composing the dependency container; ApplicationRuntime owns runtime lifecycle
execution over that container.
===============================================================================
"""

from __future__ import annotations

from application.application_runtime import ApplicationRuntime
from bootstrap.bootstrap_models import BootstrapOptions
from bootstrap.bootstrap_runner import BootstrapRunner
from core.dependency_container import DependencyContainer


def main() -> int:
    """Bootstrap ORION, construct its runtime from the canonical container, and run it."""
    runner = BootstrapRunner()
    options = BootstrapOptions(
        environment="production",
        debug=False,
        config={},
    )

    result = runner.run(options)
    if not result.success:
        return 1

    container = result.initialized_components.get("dependency_container")
    if not isinstance(container, DependencyContainer):
        return 1

    runtime = ApplicationRuntime(container)
    runtime.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
