# ORION — Target Architecture & Implementation Baseline

**File:** `ORION_TARGET_ARCHITECTURE_IMPLEMENTATION_BASELINE.md`
**Project:** ORION_NEXT
**Repository:** `badeemorse-gif/ORION_NEXT`
**Branch:** `main`
**Status:** BASELINE — Architecture Review Completed / Implementation Ready
**Baseline Date:** 2026-08-08

---

# 1. Purpose

This document is the central executable baseline for the ORION implementation.

It converts the completed architecture review into a concrete implementation path.

It defines:

* the target architecture;
* canonical domain contracts;
* layer boundaries;
* approved components;
* components requiring reconstruction;
* duplicated/legacy components;
* implementation order;
* verification requirements;
* current implementation state;
* the exact next implementation step.

This document is not merely descriptive documentation.

It is an **execution control document**.

Every subsequent ORION development session must use this document to determine:

1. what has already been completed;
2. what is currently in progress;
3. what is approved;
4. what remains;
5. what the next executable step is.

---

# 2. Execution Principle

ORION must be reconstructed in dependency order.

The implementation must not proceed by fixing isolated errors throughout the repository.

The governing implementation path is:

```text
Contracts
    ↓
Domain Models
    ↓
Market Foundation
    ↓
Validation
    ↓
Indicators
    ↓
Analysis
    ↓
Profile
    ↓
Score
    ↓
Decision
    ↓
Execution
    ↓
Report
    ↓
Core / Pipeline / Orchestrator
    ↓
Application
    ↓
Scheduler / API / GUI
    ↓
Integration / E2E Verification
```

A later layer must not establish its own incompatible contract merely to consume an earlier incomplete layer.

---

# 3. Target Architecture

```text
External Market Source
        │
        ▼
Provider Layer
 ├── Client
 ├── Mapper
 └── Provider
        │
        ▼
MarketDataset
        │
        ▼
Data Validation
        │
        ▼
Indicators
        │
        ├─────────────────┐
        ▼                 ▼
    Analysis           Profile
        │                 │
        ▼                 ▼
 AnalysisResult      ProfileResult
        │                 │
        └────────┬────────┘
                 ▼
               Score
                 │
                 ▼
            ScoreResult
                 │
                 ▼
              Decision
                 │
                 ▼
          DecisionResult
                 │
                 ▼
          Execution Planning
                 │
          ┌──────┴──────┐
          ▼             ▼
      Execution     No Execution
          │
          ▼
   ExecutionResult
          │
          └──────────────┐
                         ▼
                      Report
                         │
                   ┌─────┴─────┐
                   ▼           ▼
                  JSON        HTML


Application
    │
    ▼
Pipeline / Orchestrator
    │
    └── coordinates the processing flow


API / GUI / Scheduler
    │
    ▼
Application
```

---

# 4. Architectural Rules

## 4.1 Dependency Direction

Dependencies must point toward stable contracts.

The following direction is forbidden:

```text
Execution
    ↓
Core internals
```

The preferred direction is:

```text
Core / Application
    ↓
Execution Contract
    ↓
Execution
```

Likewise:

```text
API
    ↓
Application
```

not:

```text
Application
    ↓
API
```

---

# 5. Market Data Boundary

The market-data architecture is:

```text
External Provider
       ↓
Client
       ↓
Mapper
       ↓
Provider
       ↓
MarketDataProvider
       ↓
MarketDataset
```

The Binance-specific implementation must remain isolated from the rest of the application.

No analysis, score, decision, execution, or reporting component may directly depend on Binance APIs.

---

# 6. Canonical MarketDataset

`MarketDataset` represents market data.

It must not become a generic container for the entire pipeline.

Its responsibility is limited to market information and its legitimate metadata.

Target structure:

```text
MarketDataset
├── metadata
└── timeframes
```

It must not be used as a general-purpose container for:

```text
profile
score
decision
execution
report
```

as permanent pipeline state.

---

# 7. Canonical Timeframe Data

A timeframe must represent one market-data series.

Target conceptual structure:

```text
TimeframeData
├── timeframe
├── dataframe
├── data_health
├── candles_count
├── first_timestamp
└── last_timestamp
```

The canonical tabular-data attribute is:

```text
dataframe
```

The implementation must eliminate inconsistent use of:

```text
df
```

where that difference represents an accidental contract mismatch.

---

# 8. Result Contracts

Every major processing stage must return a dedicated result.

Canonical result contracts:

```text
AnalysisResult
ProfileResult
ScoreResult
DecisionResult
ExecutionResult
ReportResult
```

The result of one stage must not be silently embedded into an unrelated domain object.

---

# 9. Provider Contract

## Client

Responsible only for communication with the external market provider.

## Mapper

Responsible for converting external provider data into the internal representation.

## Provider

Responsible for obtaining market data through the client and mapper.

## MarketDataProvider

The internal abstraction used by higher layers.

No higher layer may require Binance-specific implementation details.

---

# 10. Repository and Storage

The application must interact with market persistence through a repository abstraction.

Target:

```text
Application
    ↓
MarketRepository
    ↓
Storage
```

The storage implementation may use:

```text
SQLite
Parquet
other approved persistence mechanisms
```

without exposing those details to higher layers.

The repository contract must be canonical.

Duplicated or incompatible repository/storage contracts must be removed after migration.

---

# 11. Validation

Validation is divided into boundaries.

## Data Validation

```text
Provider
    ↓
MarketDataset
    ↓
Validation
    ↓
Valid MarketDataset
```

## Processing Preconditions

Each processing layer must verify the minimum conditions it requires.

Example:

```text
Indicators
    ↓
required columns / sufficient candles
```

## Result Validation

Results may be validated at their respective boundaries.

Validation must not be treated as a single operation performed only after Report generation.

---

# 12. Indicators

Canonical direction:

```text
IndicatorEngine
       ↓
IndicatorCalculator
       ↓
MarketDataset / Indicator data
```

There must be one authoritative indicator contract.

Analysis must not invent indicator names or parameters independently.

The canonical indicator set must be defined centrally.

The initial required set includes:

```text
EMA 9
EMA 20
EMA 50
RSI 14
ADX 14
Momentum 5
```

The final implementation may contain additional indicators only when they are explicitly required by the approved architecture or decision logic.

---

# 13. Analysis

Target contract:

```text
MarketDataset
    ↓
AnalysisEngine
    ↓
AnalysisResult
```

Analysis must:

* consume validated market information;
* use the canonical indicator contract;
* produce `AnalysisResult`;
* avoid Binance-specific knowledge;
* avoid execution;
* avoid reporting;
* avoid direct API responsibilities.

Analysis must not own orchestration logic.

---

# 14. Profile

Profile is an independent analytical result.

Target:

```text
MarketDataset + Indicators
        ↓
ProfileEngine
        ↓
ProfileResult
```

There must be one canonical Profile model.

Duplicated `MarketProfile` definitions must be consolidated.

Profile must not become another copy of `MarketDataset`.

---

# 15. Score

Target:

```text
AnalysisResult
      ↓
ScoreEngine
      ↓
ScoreResult
```

Score must not access external providers.

Score must not perform execution.

Score must not construct reports.

The Score contract must define:

```text
score
category
factors
warnings
```

or their final approved equivalents.

---

# 16. Decision

Target:

```text
AnalysisResult
+
ScoreResult
+
ProfileResult when actually required
        ↓
DecisionEngine
        ↓
DecisionResult
```

There must be exactly one canonical Decision Engine.

Legacy duplicate Decision Engines must be migrated and removed from active use after verification.

Decision is responsible for deciding what should happen.

It is not responsible for physically executing a trade.

---

# 17. Execution

Target:

```text
DecisionResult
      ↓
ExecutionPlan
      ↓
ExecutionEngine
      ↓
TradeExecutor
      ↓
ExecutionAdapter
      ↓
ExecutionResult
```

Execution must not depend on internal Orchestrator result types.

Execution contracts must be independent.

Existing Paper Execution infrastructure should be retained where compatible.

Execution state must not be confused with Decision state.

---

# 18. Reporting

Target:

```text
AnalysisResult
+
ProfileResult
+
ScoreResult
+
DecisionResult
+
ExecutionResult
        ↓
ReportBuilder
        ↓
ReportResult
        ↓
ReportExporter
      ├── JSON
      └── HTML
```

Report must not recalculate the analysis.

Report must consume canonical results.

There must be one canonical report model and one canonical report-engine path.

Duplicated report implementations must be consolidated.

---

# 19. Orchestrator

The current generic model:

```text
Every Engine
    ↓
.execute()
    ↓
MarketDataset
```

is not the target architecture.

The Orchestrator must understand the actual result contracts.

Target:

```text
MarketDataset
      ↓
Validation
      ↓
Indicators
      ↓
AnalysisResult
      +
ProfileResult
      ↓
ScoreResult
      ↓
DecisionResult
      ↓
ExecutionPlan / ExecutionResult
      ↓
ReportResult
```

The Orchestrator coordinates.

It must not contain domain business rules belonging to individual engines.

---

# 20. Pipeline

The Pipeline represents the application-level processing flow.

Its responsibility is to combine the canonical components into a coherent use case.

It must not duplicate the logic of:

```text
AnalysisEngine
ProfileEngine
ScoreEngine
DecisionEngine
ExecutionEngine
ReportEngine
```

---

# 21. Bootstrap and Dependency Injection

Bootstrap is responsible for constructing the system.

Target conceptual structure:

```text
Bootstrap
    ↓
Dependency Container
    ↓
Application
    ↓
Pipeline
```

The bootstrap layer must establish canonical implementations.

It must not contain analytical business rules.

---

# 22. Application Layer

Application coordinates use cases and lifecycle.

It must not depend on UI implementation details.

Target:

```text
API
GUI
Scheduler
    ↓
Application
    ↓
Pipeline
    ↓
Domain / Engines
```

---

# 23. API

API remains an interface boundary.

Target:

```text
Router
   ↓
Service
   ↓
Application
```

Business logic must not be implemented inside routers.

Report export functionality will be completed only after the canonical Report contract is stable.

---

# 24. Scheduler

Scheduler answers:

```text
WHEN?
```

It does not answer:

```text
HOW DOES ANALYSIS WORK?
```

Target:

```text
Scheduler
    ↓
Application
    ↓
Pipeline
```

Scheduler-specific market-processing duplication must be removed.

---

# 25. GUI

GUI remains an interface boundary.

Target:

```text
GUI
 ↓
Application
```

GUI must not directly access:

```text
Binance
Indicators
Decision rules
Storage internals
Execution internals
```

GUI implementation is intentionally downstream of Core stabilization.

---

# 26. Confirmed Duplications

The following areas require consolidation.

## Decision

```text
engines/decision_engine.py
decision_engine.py
```

One canonical implementation.

## Report

```text
models/report.py
engines/report_engine.py
reports/report_models.py
reports/report_engine.py
```

One canonical contract and execution path.

## Profile

Multiple Profile definitions must become one canonical model.

## Application

`app/` and `application/` must have explicitly separated responsibilities and must not duplicate the same runtime concept.

## Market Service

Multiple market-service implementations must be consolidated around one responsibility.

---

# 27. Confirmed Contract Problems

The following are known contract mismatches requiring correction:

```text
df
vs
dataframe
```

```text
set_dataframe()
vs
add_timeframe()
```

```text
MarketDataset
carrying downstream results
```

```text
Execution
depending on Core payloads
```

```text
Orchestrator
assuming universal .execute()
```

```text
Validation
running too late
```

```text
Report
depending on legacy dataset mutation
```

---

# 28. Components to Preserve

The following concepts contain reusable implementation value:

```text
BinanceClient
BinanceMapper
BinanceProvider
MarketRepository concept
Storage concept
IndicatorCalculator
IndicatorEngine concept
AnalysisEngine logic
ProfileBuilder logic
ScoreEngine logic
Decision logic
TradeExecutor
ExecutionAdapter
PaperExecutionAdapter
SchedulerEngine
JobRegistry
API boundary
GUI boundary
Report exporter concepts
```

Preservation does not mean preservation of the current contract.

The logic may be retained while the interface is reconstructed.

---

# 29. Components to Reconstruct

The following require architectural reconstruction:

```text
Market Models
Result Models
Validation Contracts
Provider Contracts
Repository Contracts
Storage Contracts
Profile Contract
Decision Contract
Report Contract
Execution Contract
Orchestrator
Pipeline
Dependency Wiring
Bootstrap Wiring
Application Runtime
```

---

# 30. Components to Merge

The following must be consolidated:

```text
Profile Models
Decision Engines
Report Models
Report Engines
Application runtime paths
Market Services
```

---

# 31. Legacy Policy

A component becomes Legacy when:

1. a canonical replacement exists;
2. all valid consumers have migrated;
3. tests pass;
4. integration verification passes;
5. no active architectural dependency remains.

Legacy code must not be deleted merely because it appears old.

It must be retired through controlled migration.

---

# 32. Implementation Phases

## Phase 1 — Contracts

```text
Enums
Domain Models
Result Models
Execution Contracts
Report Contracts
Validation Contracts
```

Status:

```text
READY
```

---

## Phase 2 — Market Foundation

```text
Client
Mapper
Provider
Repository
Storage
Market Service
```

Status:

```text
PENDING
```

---

## Phase 3 — Validation

```text
Data Validation
Indicator Preconditions
Result Validation
```

Status:

```text
PENDING
```

---

## Phase 4 — Intelligence

```text
Indicators
Analysis
Profile
Score
Decision
```

Status:

```text
PENDING
```

---

## Phase 5 — Execution and Reporting

```text
Execution Plan
Execution
Report
Export
```

Status:

```text
PENDING
```

---

## Phase 6 — Core Runtime

```text
Pipeline
Orchestrator
Dependency Container
Bootstrap
Application Runtime
```

Status:

```text
PENDING
```

---

## Phase 7 — Interfaces

```text
Scheduler
API
GUI
```

Status:

```text
PENDING
```

---

## Phase 8 — Integration

```text
Unit Tests
Contract Tests
Integration Tests
Pipeline Tests
Application Tests
Regression Tests
E2E Tests
```

Status:

```text
PENDING
```

---

# 33. Implementation State

This section is the authoritative execution state.

| Phase               | Status    | Last Completed              | Current Work | Next Step             |
| ------------------- | --------- | --------------------------- | ------------ | --------------------- |
| Architecture Review | COMPLETED | Target Architecture defined | —            | —                     |
| Contracts           | READY     | Architecture baseline       | —            | Domain Contracts      |
| Market Foundation   | PENDING   | —                           | —            | Provider/Repository   |
| Validation          | PENDING   | —                           | —            | Data Validation       |
| Indicators          | PENDING   | —                           | —            | Indicator Contract    |
| Analysis            | PENDING   | —                           | —            | Analysis Contract     |
| Profile             | PENDING   | —                           | —            | Profile Contract      |
| Score               | PENDING   | —                           | —            | Score Contract        |
| Decision            | PENDING   | —                           | —            | Decision Contract     |
| Execution           | PENDING   | —                           | —            | Execution Contract    |
| Report              | PENDING   | —                           | —            | Report Contract       |
| Core                | PENDING   | —                           | —            | Pipeline/Orchestrator |
| Interfaces          | PENDING   | —                           | —            | Scheduler/API/GUI     |
| Integration         | PENDING   | —                           | —            | Full Verification     |

---

# 34. Current Execution Point

The next implementation action is:

```text
PHASE 1 — CONTRACTS
        ↓
Canonical Domain Models
        ↓
Canonical Result Contracts
```

No implementation should jump directly to Orchestrator, API, GUI, or Scheduler before the foundational contracts are stabilized.

---

# 35. Definition of Done

A phase is not Complete merely because its files were edited.

A phase becomes:

```text
COMPLETED
```

only after:

```text
Implementation
+
Unit Tests
+
Contract Tests
+
Integration Verification
+
Review
+
No unresolved blocking issue
+
Baseline update
```

---

# 36. Reopening a Completed Phase

A completed phase may be reopened only when:

* a real contract conflict is discovered;
* a downstream dependency proves the contract invalid;
* a regression is discovered;
* an architectural decision changes.

When reopened, the reason must be recorded in this document.

---

# 37. Change Log

## 2026-08-08

### Baseline Established

Completed:

* architecture inventory;
* layer-by-layer review;
* target architecture;
* contract direction;
* duplication identification;
* legacy identification;
* implementation order;
* verification rules.

Current execution point:

```text
Phase 1 — Contracts
```

No code implementation has been approved as completed under this baseline yet.

---

# 38. Execution Rule

Every ORION implementation session must begin from this document.

The assistant must determine:

```text
Current Phase
Current Status
Last Completed Step
Current Work
Next Step
```

before proposing or performing implementation.

The assistant must not assume progress that is not recorded here.

The assistant must not skip ahead because a later component appears easier to fix.

The assistant must update this document after each approved implementation milestone.

---

# 39. Final Target

The final system must provide one coherent executable path:

```text
Configuration
    ↓
Bootstrap
    ↓
Dependency Injection
    ↓
Market Data
    ↓
Validation
    ↓
Indicators
    ↓
Analysis
    ↓
Profile
    ↓
Score
    ↓
Decision
    ↓
Paper Execution
    ↓
Report
    ↓
Application
```

with:

```text
API
GUI
Scheduler
```

as controlled entry points into Application.

No hidden legacy path, duplicate engine, incompatible contract, implicit cross-layer state, or workaround-based orchestration is acceptable in the final architecture.
