from typing import Any
from bootstrap.bootstrap_registry import BootstrapRegistry
from bootstrap.bootstrap_service import BootstrapService
from bootstrap.dependency_container_builder import DependencyContainerBuilder
from bootstrap.bootstrap_result import BootstrapResult

class BootstrapRunner:
    """
    Bootstrap Runner
    Responsibility: Application entry point. Owns the registration of builders 
    and triggers the execution sequence.
    """
    def __init__(self) -> None:
        self.registry = BootstrapRegistry()
        # Dependency Injection: Hand the populated registry to the service
        self.service = BootstrapService(registry=self.registry)

    def _register_builders(self, options: Any) -> None:
        """
        Orchestrates the registration of all required builders.
        Registers the dependency container builder into the registry.
        """
        self.registry.register_builder("dependency_container", DependencyContainerBuilder())

    def run(self, options: Any = None) -> BootstrapResult:
        """
        Triggers the registration and delegates execution to the service.
        Accepts 'options' from the Public API (main.py) to maintain compatibility,
        and returns a BootstrapResult instead of a raw dictionary.
        """
        self._register_builders(options)
        try:
            components = self.service.execute_bootstrap()
            return BootstrapResult(
                success=True,
                initialized_components=components,
                message="Bootstrap completed successfully."
            )
        except Exception as e:
            return BootstrapResult(
                success=False,
                initialized_components={},
                message=str(e)
            )