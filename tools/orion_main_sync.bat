@echo off
setlocal
cd /d "%~dp0.."
python tools\orion_sync_safe.py main
exit /b %ERRORLEVEL%
