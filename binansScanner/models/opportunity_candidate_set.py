"""Future input boundary for the Scalping Opportunity Engine.

The candidate set is deliberately a transport/container contract. It does not
rank, score, filter, or create trading intent. Selection policy remains a
future Intelligence Engine concern.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from .opportunity import Opportunity


@dataclass(slots=True, frozen=True)
class OpportunityCandidateSet:
    """Immutable collection of distinct future opportunity candidates."""

    opportunities: tuple[Opportunity, ...]

    def __post_init__(self) -> None:
        candidates = tuple(self.opportunities)
        if not candidates:
            raise ValueError("opportunities must contain at least one candidate")
        if any(not isinstance(candidate, Opportunity) for candidate in candidates):
            raise ValueError("opportunities must contain only Opportunity instances")

        identities = [
            (candidate.symbol, candidate.timeframe, candidate.direction)
            for candidate in candidates
        ]
        if len(set(identities)) != len(identities):
            raise ValueError(
                "opportunities must not contain duplicate symbol/timeframe/direction candidates"
            )

        object.__setattr__(self, "opportunities", candidates)

    def __len__(self) -> int:
        return len(self.opportunities)

    def __iter__(self) -> Iterator[Opportunity]:
        return iter(self.opportunities)
