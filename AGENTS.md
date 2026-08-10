# ORION / binansScanner — Codex Engineering Contract

## Mission

Work on `binansScanner` as a production Python codebase. The goal is not merely to make tests pass; the goal is to complete the ORION architecture without breaking established contracts.

## Repository map

- Repository: `badeemorse-gif/ORION_NEXT`
- Main application: `binansScanner/`
- Tests: `binansScanner/tests/`
- Primary test framework: Python `unittest`
- Main integration/E2E coverage includes `tests/test_pipeline_integration.py` and `tests/test_pipeline_execution_e2e.py`.

## Mandatory work loop

1. Inspect the relevant implementation and tests before changing code.
2. Make a concrete code change when a defect, missing behavior, or architectural gap is identified.
3. Run the narrowest relevant test first.
4. If the test exposes a defect, diagnose the root cause and modify the implementation immediately.
5. Re-run the failed test, then run the full suite.
6. Do not replace development with repeated testing that produces no code or documentation improvement.

Classify work mentally as:
- 🟢 Modification: changes project files.
- 🔵 Test: executes/checks code only.
- 🟠 Failure found: modify the implementation, then retest.

## Canonical commands

From `binansScanner/`:

```text
python verify.py
```

Full suite directly:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```

Targeted E2E test:

```text
python -m unittest tests.test_pipeline_execution_e2e -v
```

## Test discipline

- Never claim success without actual test output.
- Preserve existing passing contracts unless the requested architecture explicitly changes them.
- Prefer deterministic tests and stdlib tooling already present in the repository.
- Do not add third-party dependencies merely to run the current test suite.
- When an external service is genuinely required, isolate that dependency and document the required environment variable/configuration.

## Git discipline

- Work on the current repository state; do not overwrite unrelated user changes.
- Keep changes focused and reviewable.
- Do not amend or rewrite existing commits.
- After modifications, inspect the diff and repository status.
- A task is complete only when the implementation and its relevant tests are both coherent.

## Codex operating principle

Codex is expected to behave as an engineering agent: inspect → modify → test → diagnose → modify → retest → full verification. It should not stop at the first failing test when the failure is actionable.

## Safety boundary

Never invent credentials, API keys, exchange secrets, or live-trading access. Never commit secrets. Do not enable live trading or destructive external actions merely to make a test pass.
