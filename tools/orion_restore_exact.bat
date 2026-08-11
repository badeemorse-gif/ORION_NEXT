@echo off
setlocal EnableExtensions EnableDelayedExpansion

title ORION Exact Repository Restore

set "ORION_ROOT=C:\Users\badee\Desktop\ORION_NEXT"
set "ORIGIN=origin"
set "BRANCH=%~1"
if "%BRANCH%"=="" set "BRANCH=main"

cd /d "%ORION_ROOT%"
if errorlevel 1 goto :root_error

echo.
echo ==================================================
echo       ORION EXACT REPOSITORY RESTORE
echo ==================================================
echo.
echo Local : %ORION_ROOT%
echo Source: %ORIGIN%/%BRANCH%
echo.
echo This restore makes the tracked and untracked
necho working tree match the fetched GitHub branch.
echo.
echo WARNING: tracked local changes and untracked files
necho will be permanently removed after confirmation.
echo Ignored files are preserved for safety.
echo.

for /f "delims=" %%A in ('git rev-parse --is-inside-work-tree 2^>nul') do set "IS_REPO=%%A"
if /I not "%IS_REPO%"=="true" goto :not_repo

for /f "delims=" %%A in ('git remote get-url %ORIGIN% 2^>nul') do set "REMOTE_URL=%%A"
if not defined REMOTE_URL goto :remote_error

echo Remote: %REMOTE_URL%
echo.
echo [1/7] Fetching %ORIGIN%/%BRANCH%...
git fetch %ORIGIN% %BRANCH%
if errorlevel 1 goto :fetch_error
echo Fetch completed.
echo.

for /f "delims=" %%A in ('git rev-parse HEAD') do set "LOCAL_COMMIT=%%A"
for /f "delims=" %%A in ('git branch --show-current') do set "CURRENT_BRANCH=%%A"
for /f "delims=" %%A in ('git rev-parse --verify %ORIGIN%/%BRANCH% 2^>nul') do set "REMOTE_COMMIT=%%A"
if not defined REMOTE_COMMIT goto :target_error

set "HAS_CHANGES="
for /f "delims=" %%A in ('git status --porcelain --untracked-files=all') do set "HAS_CHANGES=1"

echo Local branch : %CURRENT_BRANCH%
echo Target branch: %BRANCH%
echo Local commit : %LOCAL_COMMIT%
echo GitHub commit: %REMOTE_COMMIT%
if defined HAS_CHANGES (echo Local working tree: CHANGED) else (echo Local working tree: CLEAN)
echo.

if /I "%CURRENT_BRANCH%"=="%BRANCH%" if "%LOCAL_COMMIT%"=="%REMOTE_COMMIT% if not defined HAS_CHANGES (
    echo ==================================================
    echo PROJECT ALREADY EXACTLY SYNCHRONIZED
    echo ==================================================
    git status --short
    pause
    exit /b 0
)

echo ==================================================
echo              DESTRUCTIVE RESTORE
echo ==================================================
echo.
echo Target: %ORIGIN%/%BRANCH%
echo.
echo This operation will remove/rewrite:
echo   - tracked local modifications
echo   - untracked files and directories
echo.
echo Ignored files are NOT removed by this tool.
echo.
choice /C YN /N /M "Continue with EXACT GitHub -> Local restore? [Y/N]: "
if errorlevel 2 goto :cancelled

echo.
echo [2/7] Clearing tracked local changes...
git reset --hard HEAD
if errorlevel 1 goto :error

echo.
echo [3/7] Removing untracked files/directories...
git clean -fd
if errorlevel 1 goto :error

echo.
echo [4/7] Switching to target branch...
git show-ref --verify --quiet "refs/heads/%BRANCH%"
if errorlevel 1 (git switch -c "%BRANCH%" --track "%ORIGIN%/%BRANCH%") else (git switch "%BRANCH%")
if errorlevel 1 goto :switch_error

echo.
echo [5/7] Resetting tracked files to GitHub target...
git reset --hard %ORIGIN%/%BRANCH%
if errorlevel 1 goto :error

echo.
echo [6/7] Synchronizing submodules, if any...
git submodule update --init --recursive
if errorlevel 1 goto :error

echo.
echo [7/7] Verifying final state...
for /f "delims=" %%A in ('git rev-parse HEAD') do set "FINAL_COMMIT=%%A"
if not "%FINAL_COMMIT%"=="%REMOTE_COMMIT%" goto :commit_error

git diff --quiet
if errorlevel 1 goto :tracked_error
git diff --cached --quiet
if errorlevel 1 goto :staged_error
set "REMAINING="
for /f "delims=" %%A in ('git status --porcelain --untracked-files=all') do set "REMAINING=1"
if defined REMAINING goto :remaining_error

echo.
echo ==================================================
echo       ORION EXACT RESTORE COMPLETED SUCCESSFULLY
echo ==================================================
echo.
echo GitHub -> Git -> Local
echo Branch : %BRANCH%
echo Commit : %FINAL_COMMIT%
echo.
echo Tracked and untracked local state matches Git.
echo Ignored files, if any, were preserved for safety.
echo ==================================================
echo.
pause
endlocal
exit /b 0

:cancelled
echo.
echo Restore cancelled. No destructive action was performed.
pause
exit /b 0

:root_error
echo ERROR: ORION project root was not found: %ORION_ROOT%
pause
exit /b 1

:not_repo
echo ERROR: This directory is not a Git repository.
pause
exit /b 1

:remote_error
echo ERROR: Git remote "origin" is not configured.
pause
exit /b 1

:fetch_error
echo ERROR: Could not fetch %ORIGIN%/%BRANCH%.
pause
exit /b 1

:target_error
echo ERROR: Target branch %ORIGIN%/%BRANCH% does not exist.
pause
exit /b 1

:switch_error
echo ERROR: Could not switch to %BRANCH%.
pause
exit /b 1

:commit_error
echo ERROR: Final commit does not match %ORIGIN%/%BRANCH%.
goto :error

:tracked_error
echo ERROR: Working tree has unstaged tracked differences.
goto :error

:staged_error
echo ERROR: Working tree has staged differences.
goto :error

:remaining_error
echo ERROR: Tracked/untracked working-tree entries remain:
git status --short --untracked-files=all
goto :error

:error
echo.
echo ==================================================
echo                 RESTORE FAILED
echo ==================================================
echo.
pause
endlocal
exit /b 1
