from __future__ import annotations

from typing import Any, Optional

from bootstrap.bootstrap_builder import BootstrapBuilder
from core.dependency_container import ContainerConfiguration, DependencyContainer


class DependencyContainerBuilder(BootstrapBuilder):
    """Bootstrap builder responsible for creating the canonical composition root."""

    def __init__(self, config: Optional[ContainerConfiguration] = None) -> None:
        self._config = config

    def bootstrap(self) -> Any:
        return DependencyContainer(config=self._config)
