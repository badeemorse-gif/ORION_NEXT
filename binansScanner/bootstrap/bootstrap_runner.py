from __future__ import annotations

from typing import Any

from bootstrap.bootstrap_registry import BootstrapRegistry
from bootstrap.bootstrap_service import BootstrapService
from bootstrap.dependency_container_builder import DependencyContainerBuilder
from bootstrap.bootstrap_result import BootstrapResult
from config.settings import OrionSettings, SettingsLoader
from core.dependency_container import ContainerConfiguration


class BootstrapRunner:
    """Compose ORION from configuration and execute the registered bootstrap builders."""

    def __init__(self) -> None:
        self.registry = BootstrapRegistry()
        self.service = BootstrapService(registry=self.registry)

    def _resolve_container_configuration(self, options: Any) -> ContainerConfiguration:
        """Resolve canonical container settings without exposing configuration to engines."""
        supplied = getattr(options, "config", None) if options is not None else None
        if isinstance(supplied, dict):
            explicit = supplied.get("container_configuration")
            if isinstance(explicit, ContainerConfiguration):
                return explicit

            settings = supplied.get("settings")
            if isinstance(settings, OrionSettings):
                return self._container_configuration_from_settings(settings)

        settings = SettingsLoader().load_from_environment()
        return self._container_configuration_from_settings(settings)

    @staticmethod
    def _container_configuration_from_settings(settings: OrionSettings) -> ContainerConfiguration:
        return ContainerConfiguration(
            paper_trading_enabled=settings.trading.paper_trading,
            cache_enabled=settings.cache.enabled,
            binance_api_key=settings.binance.api_key,
            binance_api_secret=settings.binance.api_secret,
            binance_testnet=settings.binance.testnet,
        )

    def _register_builders(self, options: Any) -> None:
        container_config = self._resolve_container_configuration(options)
        self.registry.register_builder(
            "dependency_container",
            DependencyContainerBuilder(config=container_config),
        )

    def run(self, options: Any = None) -> BootstrapResult:
        """Register the canonical composition root and execute the bootstrap sequence."""
        try:
            self._register_builders(options)
            components = self.service.execute_bootstrap()
            return BootstrapResult(
                success=True,
                initialized_components=components,
                message="Bootstrap completed successfully.",
            )
        except Exception as exc:
            return BootstrapResult(
                success=False,
                initialized_components={},
                message=str(exc),
            )
