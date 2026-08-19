# Opportunity Scope Reconciliation

Status: RESOLVED
Scope: Future Opportunity Intelligence only

## Decision

`binansScanner/tests/test_future_trading_intelligence_contract.py` is an Opportunity/TradingReadiness contract test module. Its previous dependency on `models.explosive_watchlist` was historical collateral from the original combined future-trading-intelligence foundation and was not part of the approved Opportunity Integration scope.

The approved Opportunity package explicitly keeps Explosive Watchlist independent from Scalping Opportunities. Therefore the Opportunity contract test module must not import, instantiate, or assert Explosive Watchlist behavior.

## Result

- Removed the `models.explosive_watchlist` import from the Opportunity contract test module.
- Removed the Explosive Watchlist test class from that module.
- Preserved Opportunity contract coverage.
- Preserved TradingReadiness coverage.
- Added no Explosive Watchlist feature or coupling.
- No Core, Execution, Reporting, Verification, or main changes.

## Source Boundary

The canonical Opportunity scope is the evidence-driven Opportunity package and its approved handoff. Explosive Watchlist remains a separate future capability and is not a dependency of Central Opportunity Integration.
