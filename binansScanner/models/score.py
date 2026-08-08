from dataclasses import dataclass, field


@dataclass(slots=True)
class ScoreResult:
    score: float = 0.0
    category: str = "NEUTRAL"
    factors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)