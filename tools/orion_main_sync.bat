@echo off
setlocal
cd /d "%~dp0.."
python tools\orion_sync_guard.py main
exit /b %ERRORLEVEL%
