@echo off
setlocal EnableExtensions

title ORION Repository Restore

set "ORION_ROOT=C:\Users\badee\Desktop\ORION_NEXT"
set "ORIGIN=origin"
set "BRANCH=%~1"
if "%BRANCH%"=="" set "BRANCH=phase2/core-intelligence-hardening"

cd /d "%ORION_ROOT%"

if errorlevel 1 (
    echo.
    echo ================================================
    echo ORION RESTORE - ERROR
    echo ================================================
    echo.
    echo ERROR: ORION project root was not found.
    echo.
    echo Expected:
    echo %ORION_ROOT%
    echo.
    pause
    exit /b 1
)

echo.
echo ==================================================
echo              ORION REPOSITORY RESTORE
echo ==================================================
echo.
echo Local project:
echo %ORION_ROOT%
echo.
echo Target branch:
echo %BRANCH%
echo Source:
echo %ORIGIN%/%BRANCH%
echo.
echo Direction:
echo GitHub ^> Git ^> Local
echo.

echo [1/8] Checking Git repository...
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: This directory is not a Git repository.
    echo.
    pause
    exit /b 1
)
echo OK.
echo.

echo [2/8] Checking remote origin...
git remote get-url %ORIGIN% >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Git remote "origin" is not configured.
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%R in ('git remote get-url %ORIGIN%') do set "REMOTE_URL=%%R"

echo Remote:
echo %REMOTE_URL%
echo OK.
echo.

echo [3/8] Fetching latest GitHub %BRANCH%...
git fetch %ORIGIN% %BRANCH%
if errorlevel 1 (
    echo.
    echo ERROR: Could not fetch the latest GitHub state.
    echo.
    pause
    exit /b 1
)
echo Fetch completed.
echo.

for /f "delims=" %%L in ('git rev-parse HEAD') do set "LOCAL_COMMIT=%%L"
for /f "delims=" %%B in ('git branch --show-current') do set "CURRENT_BRANCH=%%B"
for /f "delims=" %%R in ('git rev-parse --verify %ORIGIN%/%BRANCH%') do set "REMOTE_COMMIT=%%R"

echo Current local branch:
echo %CURRENT_BRANCH%
echo.
echo Target branch:
echo %BRANCH%
echo.
echo Current local commit:
echo %LOCAL_COMMIT%
echo.
echo GitHub target commit:
echo %REMOTE_COMMIT%
echo.

if "%LOCAL_COMMIT%"=="%REMOTE_COMMIT%" if /I "%CURRENT_BRANCH%"=="%BRANCH%" (
    echo ==================================================
    echo PROJECT ALREADY SYNCHRONIZED
    echo ==================================================
    echo.
    git status
    echo.
    echo No restoration is required.
    echo.
    pause
    exit /b 0
)

echo ==================================================
echo              RESTORE CONFIRMATION
echo ==================================================
echo.
echo The local working tree will be restored to:
echo.
echo %ORIGIN%/%BRANCH%
echo.
echo The local checkout will be switched to branch:
echo %BRANCH%
echo.
echo Local tracked modifications may be replaced.
echo The Git working tree will be reset to the
necho exact state of the fetched GitHub commit.
echo.
echo NOTE:
echo Untracked local files are NOT deleted.
echo.

choice /C YN /N /M "Continue with GitHub -> Local restore? [Y/N]: "
if errorlevel 2 (
    echo.
    echo Restore cancelled.
    echo.
    pause
    exit /b 0
)

echo.
echo [4/8] Switching to target branch...
if /I not "%CURRENT_BRANCH%"=="%BRANCH%" (
    git show-ref --verify --quiet "refs/heads/%BRANCH%"
    if errorlevel 1 (
        git switch -c "%BRANCH%" --track "%ORIGIN%/%BRANCH%"
    ) else (
        git switch "%BRANCH%"
    )
    if errorlevel 1 (
        echo.
        echo ERROR: Could not switch to target branch.
        echo Local uncommitted changes may be blocking the switch.
        echo Save or move those changes and try again.
        echo.
        pause
        exit /b 1
    )
)

echo [5/8] Restoring tracked project files...
git reset --hard %ORIGIN%/%BRANCH%
if errorlevel 1 (
    echo.
    echo ERROR: Git restore failed.
    echo.
    pause
    exit /b 1
)
echo Restore completed.
echo.

echo [6/8] Synchronizing submodules, if any...
git submodule update --init --recursive
if errorlevel 1 (
    echo.
    echo ERROR: Submodule synchronization failed.
    echo.
    pause
    exit /b 1
)
echo Submodules OK.
echo.

echo [7/8] Verifying final repository state...
git status --short
if errorlevel 1 (
    echo.
    echo ERROR: Git status verification failed.
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%F in ('git rev-parse HEAD') do set "FINAL_COMMIT=%%F"
echo.
echo Final local commit:
echo %FINAL_COMMIT%
echo.
if not "%FINAL_COMMIT%"=="%REMOTE_COMMIT%" (
    echo.
    echo ERROR: Final commit does not match GitHub target branch.
    echo.
    pause
    exit /b 1
)

echo [8/8] Final verification...
git diff --quiet %ORIGIN%/%BRANCH% HEAD
if errorlevel 1 (
    echo.
    echo ERROR: Local files do not exactly match the target branch.
    echo.
    pause
    exit /b 1
)

echo.
echo ==================================================
echo          ORION RESTORE COMPLETED SUCCESSFULLY
echo ==================================================
echo.
echo GitHub -> Git -> Local
echo.
echo The tracked local project now matches:
echo %ORIGIN%/%BRANCH%
echo.
echo Commit:
echo %FINAL_COMMIT%
echo.
echo Untracked local files were preserved.
echo.
echo ==================================================
echo.

pause
endlocal
