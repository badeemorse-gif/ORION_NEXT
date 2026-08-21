# ORION_NEXT — Production UI Visual Reference

> **Status:** TEMPORARY DEVELOPMENT REFERENCE / APPROVED VISUAL DIRECTION
>
> This document records the current visual reference selected for the future ORION_NEXT Production Control Center. It is a design reference only and does **not** authorize implementation of UI behavior, business logic, trading execution, or risk logic.

## 1. Selected Reference

The **second generated Production Control Center reference** is the currently preferred visual direction for the final desktop/web operating interface of ORION_NEXT.

The reference is characterized by a dark, high-density professional trading-console layout with:

- ORION_NEXT identity and system health in the top bar.
- A persistent left navigation rail.
- Executive KPI cards across the top: balance, profit, win rate, open positions, daily P&L, and bot mode.
- A central live market chart and trading workspace.
- An open-positions table with actionable position controls.
- A right-side Trading Control Center for mode, strategy, risk level, Start/Resume, Pause, and Stop All.
- A dedicated Binance connection/status panel.
- AI Intelligence / market-analysis status.
- Recent alerts and operational notifications.
- Performance and Risk & Exposure summaries.
- Clear Arabic callouts in the reference image identifying the intended control areas during development.

## 2. Reference Layout Contract

The visual reference establishes the following provisional information hierarchy:

```text
TOP BAR
  System / Version / Runtime Health / Time / Global Controls

LEFT NAVIGATION
  Dashboard
  Trading
  Signals
  Positions
  Orders
  Backtesting
  Market Scanner
  Risk Management
  AI Intelligence
  Performance
  Logs & Reports
  Settings
  API & Exchange
  System Monitor

MAIN WORKSPACE
  KPI SUMMARY
  Live Market Chart
  Open Positions
  Performance
  Risk & Exposure

RIGHT CONTROL RAIL
  Trading Control Center
  Exchange Connection
  AI Intelligence
  Recent Alerts

BOTTOM STATUS
  Runtime / Version / Build / System Health
```

## 3. Functional Mapping Rule

The reference must be treated as a **presentation contract**, not as an independent source of truth.

Every displayed value or control must eventually map to the authoritative ORION_NEXT state/contracts:

| UI Element | Required authoritative source |
|---|---|
| Bot Mode | Runtime / Orchestrator state |
| Binance Connected | Exchange adapter connectivity state |
| Account Balance | Exchange/account provider state |
| Open Positions | Position / execution state |
| Orders | Order lifecycle state |
| Daily P&L | Authoritative performance/account calculation |
| Risk Level | Risk configuration + active risk state |
| Start / Pause / Resume / Stop | Application/orchestration control contract |
| Stop All / Emergency Stop | Risk + execution emergency control |
| AI Status | AI/analysis subsystem state |
| Alerts | Event/notification subsystem |
| Performance | Authoritative performance/audit data |

## 4. Non-Negotiable Architecture Rule

The GUI must remain a presentation and control layer.

It must **not** contain the core implementation of:

- market analysis
- indicators
- scoring
- decision making
- order execution
- risk management
- position management
- exchange authentication
- secret storage

The intended dependency direction remains:

```text
GUI
↓
Application Layer
↓
Orchestrator
↓
Pipeline
↓
Domain / Engines
↓
Providers / Repositories / Storage
↓
External Systems
```

## 5. Live Trading Safety

The visual presence of a `LIVE` control does not constitute permission to trade.

Before Live Trading is enabled, the implementation must satisfy the project's production gates for credentials, exchange connectivity, risk controls, execution lifecycle, emergency stop, auditability, and verification.

API secrets must never be committed to source control or displayed in logs/UI.

## 6. Development Status

This reference is **temporary and intentionally non-final**.

It may be refined during UI implementation after the actual Application/Orchestrator/Execution/Risk contracts are verified. Any material deviation from this reference must be recorded as an architectural/product decision rather than introduced silently through frontend implementation.

## 7. Asset Handling

The selected reference image was generated during the ORION_NEXT design review session on **2026-08-21**. The binary visual asset is retained as the design-session reference; repository asset materialization remains a separate documentation/infrastructure step and is not to be replaced by an invented placeholder.

## 8. Approval State

**APPROVED — TEMPORARY DEVELOPMENT VISUAL REFERENCE**

Approval applies only to the visual direction and information hierarchy. It does not approve any implementation, trading behavior, production credential handling, or Live Trading activation.
