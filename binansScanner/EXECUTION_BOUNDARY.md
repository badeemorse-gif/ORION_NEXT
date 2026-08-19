# Execution Boundary

Decision intent is translated into an ExecutionPlan and validated before an ExecutionRequest reaches the adapter.

The boundary rejects non-finite confidence, price, and quantity; invalid execution state; invalid quantity overrides; and mismatched decision intent. Failed execution results are also rejected by the report boundary.
