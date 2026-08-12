@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ORION_SYNC_VERSION=3.0.0"
set "ORION_SYNC_SCRIPT=%~f0"
set "ORION_TOOLS_DIR=%~dp0"
for %%I in ("%ORION_TOOLS_DIR%..") do set "ORION_ROOT=%%~fI"
set "ORIGIN=origin"
set "BRANCH=%~1"
if "%BRANCH%"=="" set "BRANCH=phase2/core-intelligence-hardening"

if /I "%BRANCH%"=="ALL" goto :all_not_supported

cd /d "%ORION_ROOT%"
if errorlevel 1 goto :root_error

for /f "delims=" %%A in ('git rev-parse --is-inside-work-tree 2^>nul') do set "IS_REPO=%%A"
if /I not "%IS_REPO%"=="true" goto :not_repo

for /f "delims=" %%A in ('git remote get-url %ORIGIN% 2^>nul') do set "REMOTE_URL=%%A"
if not defined REMOTE_URL goto :remote_error

if /I not "%REMOTE_URL:https://github.com/badeemorse-gif/ORION_NEXT=%"=="%REMOTE_URL%" goto :remote_ok
if /I not "%REMOTE_URL:git@github.com:badeemorse-gif/ORION_NEXT=%"=="%REMOTE_URL%" goto :remote_ok
goto :remote_mismatch
:remote_ok

for /f "delims=" %%A in ('git fetch %ORIGIN% %BRANCH% 2^>^&1') do echo %%A
if errorlevel 1 goto :fetch_error

for /f "delims=" %%A in ('git rev-parse --verify %ORIGIN%/%BRANCH% 2^>nul') do set "REMOTE_COMMIT=%%A"
if not defined REMOTE_COMMIT goto :target_error

for /f "delims=" %%A in ('git rev-parse HEAD') do set "LOCAL_COMMIT=%%A"
for /f "delims=" %%A in ('git branch --show-current') do set "CURRENT_BRANCH=%%A"

set "HAS_CHANGES="
for /f "delims=" %%A in ('git status --porcelain --untracked-files=all') do set "HAS_CHANGES=1"
set "EXTRA_COUNT=0"
for /f "delims=" %%A in ('git clean -fdxn') do set /a EXTRA_COUNT+=1

set "LOCAL_TOOL_BLOB="
set "REMOTE_TOOL_BLOB="
for /f "delims=" %%A in ('git rev-parse HEAD:tools/orion_sync.bat 2^>nul') do set "LOCAL_TOOL_BLOB=%%A"
for /f "delims=" %%A in ('git rev-parse %ORIGIN%/%BRANCH%:tools/orion_sync.bat 2^>nul') do set "REMOTE_TOOL_BLOB=%%A"
if not defined REMOTE_TOOL_BLOB goto :tool_missing_remote

set "TOOL_REFRESH_REQUIRED="
if /I not "%LOCAL_TOOL_BLOB%"=="%REMOTE_TOOL_BLOB%" set "TOOL_REFRESH_REQUIRED=1"

if /I "%CURRENT_BRANCH%"=="%BRANCH%" if "%LOCAL_COMMIT%"=="%REMOTE_COMMIT%" if not defined HAS_CHANGES if "%EXTRA_COUNT%"=="0" if not defined TOOL_REFRESH_REQUIRED (
    echo.
    echo ==================================================
    echo       ALREADY SYNCHRONIZED WITH GITHUB
    echo ==================================================
    echo.
    echo Version: %ORION_SYNC_VERSION%
    echo Branch : %BRANCH%
    echo Commit : %LOCAL_COMMIT%
    echo Root   : %ORION_ROOT%
    echo.
    exit /b 0
)

echo.
echo ==================================================
echo           ORION GITHUB -^> LOCAL SYNC
echo ==================================================
echo.
echo Tool version         : %ORION_SYNC_VERSION%
echo Local root           : %ORION_ROOT%
echo GitHub source        : %ORIGIN%/%BRANCH%
echo Remote               : %REMOTE_URL%
echo Current local branch : %CURRENT_BRANCH%
echo Current local commit : %LOCAL_COMMIT%
echo GitHub target commit : %REMOTE_COMMIT%
if defined HAS_CHANGES (echo Working tree         : CHANGED) else (echo Working tree         : CLEAN)
echo Extra paths to remove: %EXTRA_COUNT%
if defined TOOL_REFRESH_REQUIRED (echo Sync tool status      : UPDATE REQUIRED FROM GITHUB) else (echo Sync tool status      : CURRENT)
echo.
echo GitHub is the source of truth.
echo This operation is GitHub -^> Local only.
echo No local commit or push is ever created by this tool.
echo The .git directory is preserved.
echo.

if defined ORION_SYNC_CONFIRMED goto :confirmed
choice /C YN /N /M "Continue and make local project an exact copy of GitHub? [Y/N]: "
if errorlevel 2 goto :cancelled
:confirmed

if defined HAS_CHANGES if not defined ORION_SYNC_BACKED_UP call :backup_local_state
if errorlevel 1 goto :backup_error
if "%EXTRA_COUNT%" GTR "0" if not defined ORION_SYNC_BACKED_UP call :backup_local_state
if errorlevel 1 goto :backup_error

if defined TOOL_REFRESH_REQUIRED if not defined ORION_SYNC_BOOTSTRAP (
    echo.
    echo [BOOTSTRAP] Refreshing synchronization tool from GitHub...
    set "LATEST_SYNC=%TEMP%\ORION_SYNC_%RANDOM%_%RANDOM%.bat"
    git show %ORIGIN%/%BRANCH%:tools/orion_sync.bat > "%LATEST_SYNC%"
    if errorlevel 1 goto :tool_refresh_error
    if not exist "%LATEST_SYNC%" goto :tool_refresh_error
    for %%Z in ("%LATEST_SYNC%") do if %%~zZ LSS 100 goto :tool_refresh_error
    echo [BOOTSTRAP] Running GitHub version of orion_sync.bat...
    set "ORION_SYNC_BOOTSTRAP=1"
    set "ORION_SYNC_CONFIRMED=1"
    set "ORION_SYNC_BACKED_UP=1"
    call "%LATEST_SYNC%" "%BRANCH%"
    set "SYNC_RC=!ERRORLEVEL!"
    del /q "%LATEST_SYNC%" >nul 2>&1
    exit /b !SYNC_RC!
)

if defined HAS_CHANGES (
    echo.
    echo [1/7] Clearing tracked local changes...
    git reset --hard HEAD
    if errorlevel 1 goto :reset_error
)

echo.
echo [2/7] Removing local files outside the Git target...
git clean -fdx
if errorlevel 1 goto :clean_error

echo.
echo [3/7] Switching to target branch...
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
echo [4/7] Resetting project to the exact GitHub target...
git reset --hard %ORIGIN%/%BRANCH%
if errorlevel 1 goto :reset_target_error

echo.
echo [5/7] Synchronizing submodules...
git submodule update --init --recursive
if errorlevel 1 goto :submodule_error
git submodule foreach --recursive git reset --hard
if errorlevel 1 goto :submodule_error
git submodule foreach --recursive git clean -fdx
if errorlevel 1 goto :submodule_error

echo.
echo [6/7] Verifying final GitHub parity...
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
echo [7/7] Final synchronization result...
echo.
echo ==================================================
echo        ORION GITHUB -^> LOCAL SYNC SUCCESS
echo ==================================================
echo.
echo Branch : %BRANCH%
echo Commit : %FINAL_COMMIT%
echo Root   : %ORION_ROOT%
echo Tool   : %ORION_SYNC_VERSION%
echo.
echo FINAL REPOSITORY STATE: EXACT MATCH
echo .git preserved.
echo No local commit created.
echo No GitHub push performed.
if defined ORION_SYNC_BACKUP_PATH (
    echo Safety backup: %ORION_SYNC_BACKUP_PATH%
)
echo.
exit /b 0

:backup_local_state
set "ORION_SYNC_BACKED_UP=1"
for /f "delims=" %%A in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%A"
set "SAFE_BRANCH=%BRANCH:/=_%"
set "ORION_SYNC_BACKUP_PATH=%USERPROFILE%\Desktop\ORION_SYNC_BACKUPS\%STAMP%_%SAFE_BRANCH%"
mkdir "%ORION_SYNC_BACKUP_PATH%" >nul 2>&1
if errorlevel 1 exit /b 1
robocopy "%ORION_ROOT%" "%ORION_SYNC_BACKUP_PATH%" /E /R:1 /W:1 /XJ /XD ".git" "ORION_SYNC_BACKUPS" >nul
set "ROBO_RC=%ERRORLEVEL%"
if %ROBO_RC% GEQ 8 exit /b 1
(
    echo ORION synchronization safety backup
    echo Created: %STAMP%
    echo Source: %ORION_ROOT%
    echo Target: %ORIGIN%/%BRANCH%
    echo Local branch: %CURRENT_BRANCH%
    echo Local commit: %LOCAL_COMMIT%
    echo GitHub commit: %REMOTE_COMMIT%
    echo This backup was created before destructive GitHub -^> Local synchronization.
    echo The backup is outside the project repository and is not part of Git.
) > "%ORION_SYNC_BACKUP_PATH%\SYNC_BACKUP_INFO.txt"
echo.
echo [BACKUP] Local safety copy created:
echo          %ORION_SYNC_BACKUP_PATH%
exit /b 0

:cancelled
echo.
echo Synchronization cancelled. No destructive action was performed.
exit /b 0

:root_error
echo ERROR: ORION project root could not be resolved from this tool location: %ORION_ROOT%
exit /b 1
:not_repo
echo ERROR: The resolved ORION root is not a Git repository: %ORION_ROOT%
exit /b 1
:remote_error
echo ERROR: Git remote "origin" is not configured.
exit /b 1
:remote_mismatch
echo ERROR: Unexpected origin remote: %REMOTE_URL%
echo Expected repository: github.com/badeemorse-gif/ORION_NEXT
exit /b 1
:fetch_error
echo ERROR: Could not fetch %ORIGIN%/%BRANCH%.
exit /b 1
:target_error
echo ERROR: Target branch %ORIGIN%/%BRANCH% does not exist.
exit /b 1
:tool_missing_remote
echo ERROR: Target branch does not contain tools/orion_sync.bat.
exit /b 1
:tool_refresh_error
echo ERROR: Could not materialize the GitHub synchronization tool.
exit /b 1
:backup_error
echo ERROR: Local safety backup could not be created. Synchronization stopped before destructive reset.
if defined ORION_SYNC_BACKUP_PATH echo Backup path: %ORION_SYNC_BACKUP_PATH%
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
