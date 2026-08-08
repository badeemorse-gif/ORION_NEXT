from typing import Dict, Any

class BootstrapRegistry:
    """
    Bootstrap Registration Layer
    Responsibility: Pure storage mechanism for builders.
    """
    def __init__(self) -> None:
        self._builders: Dict[str, Any] = {}

    def register_builder(self, key: str, builder: Any) -> None:
        if key in self._builders:
            raise ValueError(f"Builder '{key}' is already registered.")
        self._builders[key] = builder

    def resolve_builder(self, key: str) -> Any:
        if key not in self._builders:
            raise KeyError(f"Builder '{key}' not found in the registry.")
        return self._builders[key]
        
    def get_all_builders(self) -> Dict[str, Any]:
        return self._builders