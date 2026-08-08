"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : tests.test_pipeline_integration
Version      : 2.0.0
Status       : ORION Composition Root Integration Contract
===============================================================================

Integration tests for the ORION dependency graph.

These tests intentionally validate construction and dependency wiring only.
They do not perform network calls or real market execution.
===============================================================================
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.dependency_container import (
    ContainerConfiguration,
    DependencyContainer,
)

from core.orchestrator import Orchestrator
from core.pipeline import Pipeline

from providers.market_data_provider import MarketDataProvider
from repositories.market_repository import MarketRepository
from services.market_service import MarketService
from storage.sqlite_market_storage import SQLiteMarketStorage


class TestPipelineIntegration(unittest.TestCase):
    """
    Validate the Composition Root and the construction graph.
    """

    def setUp(self) -> None:
        self._temp_directory = tempfile.TemporaryDirectory()

        database_path = str(
            Path(self._temp_directory.name)
            / "orion_test_market_data.db"
        )

        self.container = DependencyContainer(
            ContainerConfiguration(
                database_path=database_path,
                binance_api_key="",
                binance_api_secret="",
                binance_testnet=True,
            )
        )

    def tearDown(self) -> None:
        self.container.reset()
        self._temp_directory.cleanup()

    def test_dependency_container_creation(self) -> None:
        """DependencyContainer can be instantiated."""

        self.assertIsInstance(
            self.container,
            DependencyContainer,
        )

    def test_market_provider_creation(self) -> None:
        """MarketDataProvider is correctly wired."""

        provider = self.container.build_market_data_provider()

        self.assertIsInstance(
            provider,
            MarketDataProvider,
        )

    def test_market_repository_creation(self) -> None:
        """MarketRepository is correctly wired."""

        repository = self.container.build_market_repository()

        self.assertIsInstance(
            repository,
            MarketRepository,
        )

        self.assertIs(
            repository._market_provider,
            self.container.build_market_data_provider(),
        )

        self.assertIs(
            repository._storage,
            self.container.build_market_storage(),
        )

    def test_market_service_creation(self) -> None:
        """MarketService is correctly wired."""

        service = self.container.build_market_service()

        self.assertIsInstance(
            service,
            MarketService,
        )

        self.assertIs(
            service._repository,
            self.container.build_market_repository(),
        )

    def test_storage_creation(self) -> None:
        """SQLite storage can be instantiated."""

        storage = self.container.build_market_storage()

        self.assertIsInstance(
            storage,
            SQLiteMarketStorage,
        )

    def test_orchestrator_creation(self) -> None:
        """Orchestrator can be created successfully."""

        orchestrator = self.container.build_orchestrator()

        self.assertIsInstance(
            orchestrator,
            Orchestrator,
        )

        self.assertIs(
            orchestrator._provider,
            self.container.build_market_data_provider(),
        )

        self.assertIs(
            orchestrator._storage,
            self.container.build_market_storage(),
        )

        self.assertIs(
            orchestrator._indicator_engine,
            self.container.build_indicator_engine(),
        )

        self.assertIs(
            orchestrator._profile_engine,
            self.container.build_profile_engine(),
        )

        self.assertIs(
            orchestrator._score_engine,
            self.container.build_score_engine(),
        )

        self.assertIs(
            orchestrator._decision_engine,
            self.container.build_decision_engine(),
        )

        self.assertIs(
            orchestrator._report_engine,
            self.container.build_report_engine(),
        )

        self.assertIs(
            orchestrator._validation_engine,
            self.container.build_validation_engine(),
        )

    def test_pipeline_creation(self) -> None:
        """Pipeline can be created from container."""

        pipeline = self.container.build_pipeline()

        self.assertIsInstance(
            pipeline,
            Pipeline,
        )

        self.assertIs(
            pipeline._orchestrator,
            self.container.build_orchestrator(),
        )

        self.assertIs(
            pipeline._execution_engine,
            self.container.build_execution_engine(),
        )


if __name__ == "__main__":
    unittest.main()