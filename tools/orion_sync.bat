@echo off
setlocal

cd /d "C:\Users\badee\Desktop\ORION_NEXT\ORION-Project-Management"

if errorlevel 1 (
    echo ERROR: ORION repository not found.
    exit /b 1
)

echo ========================================
echo ORION RAPID SYNC
echo ========================================
echo.

echo [1/5] Git status
git status

echo.
echo [2/5] Git add
git add .

echo.
echo [3/5] Checking staged changes
git diff --cached --quiet

if %errorlevel%==0 (
    echo No changes detected.
    echo.
    echo Repository already synchronized.
    echo.
    git status
    exit /b 0
)

echo Changes detected.

echo.
echo [4/5] Git commit
git commit -m "update: ORION changes"

if errorlevel 1 (
    echo ERROR: Commit failed.
    exit /b 1
)

echo.
echo Git push
git push

if errorlevel 1 (
    echo ERROR: Push failed.
    exit /b 1
)

echo.
echo [5/5] Final Git status
git status

echo.
echo ========================================
echo ORION RAPID SYNC COMPLETED
echo ========================================
echo.

endlocal