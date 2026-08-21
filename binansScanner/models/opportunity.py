"""Canonical market-universe and opportunity contracts.

The contracts in this module contain discovery/eligibility/ranking data only.
They intentionally do not own signal, decision, execution, or position state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class UniverseCandidate:
    """A deterministic market-universe candidate discovered from a venue."""

    symbol: str
    base_asset: str
    quote_asset: str


@dataclass(frozen=True, slots=True)
class MarketMetrics:
    """Venue-independent metrics used by eligibility and opportunity scoring."""

    symbol: str
    quote_volume_24h: float
    volatility: float
    spread_bps: Optional[float] = None
    tradable: bool = True


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    """Fail-closed eligibility result with deterministic reasons."""

    symbol: str
    eligible: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OpportunityCandidate:
    """A ranked, eligible opportunity candidate."""

    symbol: str
    opportunity_score: float
    rank: int
    metrics: MarketMetrics
    eligibility_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OpportunityCandidateSet:
    """Stable top-N candidate output contract."""

    candidates: tuple[OpportunityCandidate, ...]
    top_n: int

    def symbols(self) -> tuple[str, ...]:
        """Return candidate symbols in rank order."""
        return tuple(candidate.symbol for candidate in self.candidates)
