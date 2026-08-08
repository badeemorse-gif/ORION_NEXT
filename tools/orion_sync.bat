@echo off
setlocal

cd /d "C:\Users\badee\Desktop\ORION_NEXT"

if errorlevel 1 (
    echo.
    echo ========================================
    echo ORION SYNC ERROR
    echo ========================================
    echo.
    echo ERROR: ORION_NEXT root directory not found.
    echo.
    exit /b 1
)

echo.
echo ========================================
echo ORION ONE-STEP SYNC
echo ========================================
echo.
echo Repository:
echo C:\Users\badee\Desktop\ORION_NEXT
echo.

echo [1] Checking repository status...
git status --short

echo.
echo [2] Staging all project changes...
git add -A

if errorlevel 1 (
    echo.
    echo ERROR: Git add failed.
    echo.
    exit /b 1
)

echo.
echo [3] Checking staged changes...
git diff --cached --quiet

if %errorlevel%==0 (
    echo.
    echo No changes detected.
    echo Repository is already synchronized.
    echo.
    git status
    echo.
    echo ========================================
    echo ORION SYNC COMPLETED - NO CHANGES
    echo ========================================
    echo.
    exit /b 0
)

echo.
echo Changes detected.
echo.

echo [4] Creating commit...
git commit -m "sync: update ORION project"

if errorlevel 1 (
    echo.
    echo ERROR: Commit failed.
    echo.
    exit /b 1
)

echo.
echo [5] Pushing to GitHub...
git push -u origin main

if errorlevel 1 (
    echo.
    echo ERROR: Push failed.
    echo.
    exit /b 1
)

echo.
echo [6] Final repository status...
git status

echo.
echo ========================================
echo ORION ONE-STEP SYNC COMPLETED
echo ========================================
echo.
echo Local -> Git -> GitHub
echo.

endlocal