@echo off
setlocal EnableExtensions

title ORION Repository Restore

set "ORION_ROOT=C:\Users\badee\Desktop\ORION_NEXT"
set "ORIGIN=origin"
set "BRANCH=main"

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
echo Source:
echo %ORIGIN%/%BRANCH%
echo.
echo Direction:
echo GitHub ^> Git ^> Local
echo.

echo [1/7] Checking Git repository...
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

echo [2/7] Checking remote origin...
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

echo [3/7] Fetching latest GitHub main...
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
for /f "delims=" %%R in ('git rev-parse %ORIGIN%/%BRANCH%') do set "REMOTE_COMMIT=%%R"

echo Current local commit:
echo %LOCAL_COMMIT%
echo.
echo GitHub main commit:
echo %REMOTE_COMMIT%
echo.

if "%LOCAL_COMMIT%"=="%REMOTE_COMMIT%" (
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
echo The local tracked project will be restored to:
echo.
echo %ORIGIN%/%BRANCH%
echo.
echo Local tracked modifications may be replaced.
echo The Git working tree will be reset to the
echo exact state of the fetched GitHub commit.
echo.
echo NOTE:
echo Untracked local files are NOT deleted by this
echo first version of the restore tool.
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
echo [4/7] Restoring tracked project files...
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

echo [5/7] Synchronizing submodules, if any...
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

echo [6/7] Verifying final repository state...
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
    echo ERROR: Final commit does not match GitHub main.
    echo.
    pause
    exit /b 1
)

echo [7/7] Final verification...
git diff --quiet %ORIGIN%/%BRANCH% HEAD

if errorlevel 1 (
    echo.
    echo ERROR: Local files do not exactly match origin/main.
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
