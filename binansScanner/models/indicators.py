from dataclasses import dataclass, field


@dataclass(slots=True)
class IndicatorResult:
    """A data model holding metadata and quality metrics for technical indicator calculations.

    This class contains no business logic, calculations, or heavy dependencies
    like pandas or numpy. It is used by the Indicator Engine and downstream layers
    to inspect calculation success, failures, and warnings.
    """

    quality: str = "SUFFICIENT"
    failed_indicators: list[str] = field(default_factory=list)
    calculated_indicators: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)