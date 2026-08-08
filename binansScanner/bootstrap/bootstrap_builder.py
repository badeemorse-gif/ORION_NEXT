from abc import ABC, abstractmethod
from typing import Any

class BootstrapBuilder(ABC):
    """
    Abstract base class for all startup builders.
    Contract for architectural consistency.
    """
    @abstractmethod
    def bootstrap(self) -> Any:
        """Executes the specific bootstrap/initialization logic."""
        raise NotImplementedError