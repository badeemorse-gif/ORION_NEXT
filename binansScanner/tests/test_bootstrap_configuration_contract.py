from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from bootstrap.bootstrap_models import BootstrapOptions
from bootstrap.bootstrap_runner import BootstrapRunner
from core.dependency_container import DependencyContainer


class TestBootstrapConfigurationContract(unittest.TestCase):
    def test_bootstrap_loads_environment_into_container_configuration(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ORION_BINANCE_API_KEY": "test-key",
                "ORION_BINANCE_API_SECRET": "test-secret",
                "ORION_BINANCE_TESTNET": "false",
                "ORION_TRADING_PAPER_TRADING": "true",
                "ORION_CACHE_ENABLED": "false",
            },
            clear=False,
        ):
            result = BootstrapRunner().run(BootstrapOptions(environment="test", debug=False))

        self.assertTrue(result.success)
        container = result.initialized_components["dependency_container"]
        self.assertIsInstance(container, DependencyContainer)
        self.assertEqual(container._config.binance_api_key, "test-key")
        self.assertEqual(container._config.binance_api_secret, "test-secret")
        self.assertFalse(container._config.binance_testnet)
        self.assertTrue(container._config.paper_trading_enabled)
        self.assertFalse(container._config.cache_enabled)

    def test_explicit_container_configuration_overrides_environment(self) -> None:
        from core.dependency_container import ContainerConfiguration

        explicit = ContainerConfiguration(
            paper_trading_enabled=True,
            cache_enabled=True,
            binance_api_key="explicit-key",
            binance_api_secret="explicit-secret",
            binance_testnet=True,
        )
        options = BootstrapOptions(
            environment="test",
            debug=False,
            config={"container_configuration": explicit},
        )

        result = BootstrapRunner().run(options)

        self.assertTrue(result.success)
        container = result.initialized_components["dependency_container"]
        self.assertIs(container._config, explicit)


if __name__ == "__main__":
    unittest.main()
