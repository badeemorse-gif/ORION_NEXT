from typing import Any
from bootstrap.bootstrap_builder import BootstrapBuilder
from core.dependency_container import DependencyContainer

class DependencyContainerBuilder(BootstrapBuilder):
    """
    Dependency Container Builder
    Responsibility: Initialize and return the DependencyContainer instance.
    """
    def bootstrap(self) -> Any:
        return DependencyContainer()