@echo off
setlocal
cd /d "%~dp0.."
if /I "%~1"=="main" goto MAIN
if /I "%~1"=="all" goto ALL
if /I "%~1"=="dev" goto DEV
echo ORION SAFE SYNC
echo Usage: orion_sync.bat dev ^| main ^| all
echo Default: DEV sync for the currently checked-out branch.
goto DEV
:DEV
python tools\orion_sync_safe.py dev
set RC=%ERRORLEVEL%
goto END
:MAIN
python tools\orion_sync_safe.py main
set RC=%ERRORLEVEL%
goto END
:ALL
python tools\orion_sync_safe.py all
set RC=%ERRORLEVEL%
goto END
:END
if not "%RC%"=="0" echo ORION SAFE SYNC FAILED / REFUSED.
exit /b %RC%
