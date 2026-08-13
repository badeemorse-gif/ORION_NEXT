@echo off
setlocal
cd /d "%~dp0.."
python tools\orion_sync_safe.py all
exit /b %ERRORLEVEL%
