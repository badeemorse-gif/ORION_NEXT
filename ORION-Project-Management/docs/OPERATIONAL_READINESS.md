# ORION — Operational Readiness

## Verified Gap

**Requirements / CI dependency alignment — CLOSED**

The verification workflow previously installed NumPy, pandas, pandas-ta, and python-binance outside `requirements.txt`. That meant the repository's declared dependency contract did not fully reproduce the environment required by `verify.py` and the test suite.

The canonical requirements file now declares the verification/runtime dependencies, and GitHub Actions installs only from `requirements.txt` before running `verify.py`.

This change is operational-only. It does not alter the Analysis → Profile → Score → Decision → Execution → Report contracts or Core Intelligence behavior.
