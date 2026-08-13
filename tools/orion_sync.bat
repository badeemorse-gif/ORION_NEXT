@echo off
setlocal
cd /d "%~dp0.."

if /I "%~1"=="dev" goto DEV
if /I "%~1"=="main" goto MAIN
if /I "%~1"=="all" goto ALL
if /I "%~1"=="audit" goto AUDIT

echo ORION SYNCHRONIZATION
 echo.
echo Usage:
echo   orion_sync.bat dev    ^(commit/push CURRENT branch only^)
echo   orion_sync.bat main   ^(refresh isolated ORION_NEXT_MAIN only^)
echo   orion_sync.bat all    ^(refresh isolated branch mirrors only^)
echo   orion_sync.bat audit  ^(read-only synchronization safety audit^)
echo.
echo REFUSED: operation mode is required. There is no implicit DEV sync.
exit /b 2

:DEV
python tools\orion_sync_guard.py dev
set RC=%ERRORLEVEL%
goto END

:MAIN
python tools\orion_sync_guard.py main
set RC=%ERRORLEVEL%
goto END

:ALL
python tools\orion_sync_guard.py all
set RC=%ERRORLEVEL%
goto END

:AUDIT
python tools\orion_sync_guard.py audit
set RC=%ERRORLEVEL%
goto END

:END
if not "%RC%"=="0" (
  echo.
  echo ORION SYNCHRONIZATION FAILED / REFUSED.
)
exit /b %RC%
