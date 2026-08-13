# ORION_NEXT — Central Integration Package Snapshot

This integration branch combines the leadership-approved Core Intelligence, Execution Fail-Closed, and Future Opportunity package snapshots without modifying the developer branches.

Approved package heads:
- Core: `3b37ad94d3440463f4e440c7e46ca0380d7ce900`
- Execution: `1ae3cca91f7b58e221e7e005f7949aceb1e96b02`
- Opportunity: `4975292572a8446a178a5d1afe708792082767a1`

Integration policy:
- GitHub remains the source of truth.
- No local materialization is performed by this integration commit.
- Sync/Restore infrastructure is excluded from package import unless explicitly approved by leadership.
- Full verification remains a later integration gate.
