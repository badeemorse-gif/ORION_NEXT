from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class BootstrapResult:
    """
    Bootstrap Result Data Model
    Responsibility: Encapsulate the outcome of the bootstrap execution sequence.
    """
    success: bool
    initialized_components: Dict[str, Any]
    message: str = ""