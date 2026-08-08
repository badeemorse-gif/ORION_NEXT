from dataclasses import dataclass, field


@dataclass(slots=True)
class DecisionResult:
    decision: str = "WAIT"
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)