@echo off
setlocal

title ORION CLEAN

cd /d "%~dp0\.."

echo.
echo ============================================================
echo                       ORION CLEAN
echo ============================================================
echo.
echo Project:
echo %CD%
echo.
echo Safe cleanup only:
echo   - __pycache__
echo   - *.pyc
echo   - *.pyo
echo.
echo No Git commands will be executed.
echo No source code or project data will be modified.
echo.
echo ============================================================
echo.

python "%~dp0orion_clean_gui.py"

if errorlevel 1 (
    echo.
    echo ============================================================
    echo ORION CLEAN encountered an error.
    echo ============================================================
    echo.
    pause
)

endlocal