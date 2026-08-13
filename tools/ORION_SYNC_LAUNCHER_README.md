# ORION Safe Synchronization

Use `orion_sync.bat` or `orion_safe_sync_gui.vbs`.

- DEV: commits/pushes the currently checked-out branch only.
- MAIN: writes only to `../ORION_NEXT_MAIN`.
- ALL: writes only to `../ORION_NEXT_ALL_BRANCHES/__branches__/<branch>`.
- No mirror mode is allowed to switch/reset/clean or materialize files in `ORION_NEXT`.
