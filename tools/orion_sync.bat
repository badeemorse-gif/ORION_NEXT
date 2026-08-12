@echo off
setlocal EnableExtensions EnableDelayedExpansion

title ORION GitHub to Local Sync

set "ORION_ROOT=C:\Users\badee\Desktop\ORION_NEXT"
set "ORIGIN=origin"
set "BRANCH=%~1"
if "%BRANCH%"=="" set "BRANCH=phase2/core-intelligence-hardening"

cd /d "%ORION_ROOT%"
if errorlevel 1 goto :root_error

if /I "%BRANCH%"=="ALL" goto :all_not_supported

for /f "delims=" %%A in ('git rev-parse --is-inside-work-tree 2^>nul') do set "IS_REPO=%%A"
if /I not "%IS_REPO%"=="true" goto :not_repo

for /f "delims=" %%A in ('git remote get-url %ORIGIN% 2^>nul') do set "REMOTE_URL=%%A"
if not defined REMOTE_URL goto :remote_error

echo.
echo ==================================================
echo           ORION GITHUB -> LOCAL SYNC
echo ==================================================
echo.
echo Local : %ORION_ROOT%
echo Source: %ORIGIN%/%BRANCH%
echo Remote: %REMOTE_URL%
echo.
echo IMPORTANT: GitHub is the source of truth.
echo This tool NEVER commits or pushes local changes.
echo .git is preserved; project files are synchronized.
echo.

echo [1/8] Fetching GitHub target...
git fetch %ORIGIN% %BRANCH%
if errorlevel 1 goto :fetch_error

echo.
for /f "delims=" %%A in ('git rev-parse HEAD') do set "LOCAL_COMMIT=%%A"
for /f "delims=" %%A in ('git branch --show-current') do set "CURRENT_BRANCH=%%A"
for /f "delims=" %%A in ('git rev-parse --verify %ORIGIN%/%BRANCH% 2^>nul') do set "REMOTE_COMMIT=%%A"
if not defined REMOTE_COMMIT goto :target_error

set "HAS_CHANGES="
for /f "delims=" %%A in ('git status --porcelain --untracked-files=all') do set "HAS_CHANGES=1"

set "EXTRA_COUNT=0"
for /f "delims=" %%A in ('git clean -fdxn') do set /a EXTRA_COUNT+=1

echo Current local branch : %CURRENT_BRANCH%
echo Target branch        : %BRANCH%
echo Current local commit : %LOCAL_COMMIT%
echo GitHub target commit : %REMOTE_COMMIT%
if defined HAS_CHANGES (echo Local working tree    : CHANGED) else (echo Local working tree    : CLEAN)
echo Extra paths to remove: %EXTRA_COUNT%
echo.

if /I "%CURRENT_BRANCH%"=="%BRANCH%" if "%LOCAL_COMMIT%"=="%REMOTE_COMMIT% if not defined HAS_CHANGES if "%EXTRA_COUNT%"=="0" (
    echo ==================================================
    echo       ALREADY SYNCHRONIZED WITH GITHUB
    echo ==================================================
    git status --short
    echo.
    echo GitHub -> Local synchronization is already complete.
    echo.
    exit /b 0
)

echo ==================================================
echo             SYNC CONFIRMATION REQUIRED
echo ==================================================
echo.
echo The local project will be made identical to:
echo %ORIGIN%/%BRANCH%
echo.
echo The following local state may be replaced:
echo   - tracked modifications
necho   - staged changes
necho   - untracked files/directories
necho   - ignored files/directories not present in GitHub
necho.
echo The .git directory itself is NOT deleted.
echo No commit or push will be performed.
echo.
choice /C YN /N /M "Continue GitHub -> Local synchronization? [Y/N]: "
if errorlevel 2 goto :cancelled

if defined HAS_CHANGES (
    echo.
    echo [2/8] Clearing tracked local changes...
    git reset --hard HEAD
    if errorlevel 1 goto :reset_error
)

 echo.
echo [3/8] Removing local files outside the Git target...
git clean -fdx
if errorlevel 1 goto :clean_error

echo.
echo [4/8] Switching to target branch...
if /I not "%CURRENT_BRANCH%"=="%BRANCH%" (
    git show-ref --verify --quiet "refs/heads/%BRANCH%"
    if errorlevel 1 (
        git switch -c "%BRANCH%" --track "%ORIGIN%/%BRANCH%"
    ) else (
        git switch "%BRANCH%"
    )
    if errorlevel 1 goto :switch_error
)

echo.
echo [5/8] Resetting project to the exact GitHub target...
git reset --hard %ORIGIN%/%BRANCH%
if errorlevel 1 goto :reset_target_error

echo.
echo [6/8] Synchronizing submodules...
git submodule update --init --recursive
if errorlevel 1 goto :submodule_error

git submodule foreach --recursive git reset --hard
if errorlevel 1 goto :submodule_error

git submodule foreach --recursive git clean -fdx
if errorlevel 1 goto :submodule_error

echo.
echo [7/8] Verifying commit and tracked tree...
for /f "delims=" %%A in ('git rev-parse HEAD') do set "FINAL_COMMIT=%%A"
if not "%FINAL_COMMIT%"=="%REMOTE_COMMIT%" goto :commit_error

git diff --quiet %ORIGIN%/%BRANCH% HEAD
if errorlevel 1 goto :tracked_error

git diff --cached --quiet
if errorlevel 1 goto :staged_error

set "REMAINING="
for /f "delims=" %%A in ('git status --porcelain --ignored') do set "REMAINING=1"
if defined REMAINING goto :remaining_error

echo.
echo [8/8] Final synchronization result...
echo.
echo ==================================================
echo        ORION GITHUB -> LOCAL SYNC SUCCESS
 eecho ==================================================
echo.
echo Branch : %BRANCH%
echo Commit : %FINAL_COMMIT%
echo.
echo FINAL REPOSITORY STATE: EXACT MATCH
echo .git preserved.
echo No local commit created.
echo No GitHub push performed.
echo.
exit /b 0

:cancelled
echo.
echo Synchronization cancelled. No destructive action was performed.
exit /b 0

:root_error
echo ERROR: ORION project root was not found: %ORION_ROOT%
exit /b 1

:not_repo
echo ERROR: This directory is not a Git repository.
exit /b 1

:remote_error
echo ERROR: Git remote "origin" is not configured.
exit /b 1

:fetch_error
echo ERROR: Could not fetch %ORIGIN%/%BRANCH%.
exit /b 1

:target_error
echo ERROR: Target branch %ORIGIN%/%BRANCH% does not exist.
exit /b 1

:reset_error
echo ERROR: Could not clear tracked local changes.
exit /b 1

:clean_error
echo ERROR: Could not remove local files outside the Git target.
exit /b 1

:switch_error
echo ERROR: Could not switch to target branch %BRANCH%.
exit /b 1

:reset_target_error
echo ERROR: Could not reset local project to %ORIGIN%/%BRANCH%.
exit /b 1

:submodule_error
echo ERROR: Submodule synchronization failed.
exit /b 1

:commit_error
echo ERROR: Final commit does not match %ORIGIN%/%BRANCH%.
exit /b 1

:tracked_error
echo ERROR: Local tracked files do not exactly match GitHub target.
exit /b 1

:staged_error
echo ERROR: Local staged changes remain after synchronization.
exit /b 1

:remaining_error
echo ERROR: Local files remain after synchronization:
git status --short --ignored
exit /b 1

:all_not_supported
echo ERROR: ALL is not a working-tree synchronization target.
echo Use a specific branch such as phase2/core-intelligence-hardening.
exit /b 1
