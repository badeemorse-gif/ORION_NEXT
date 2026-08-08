from dataclasses import dataclass, field


@dataclass(slots=True)
class AnalysisResult:
    """A data model holding technical market analysis results.

    This class contains no business logic, calculations, or heavy dependencies
    like pandas or numpy. It is used by the Analysis Engine and downstream layers
    (such as Score or Decision Engines) to evaluate market state, trend strength,
    signals, and warnings.
    """

    market_state: str = "NEUTRAL"
    strength: float = 0.0
    signals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)