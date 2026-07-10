@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Sight-Singing Studio -- one-click dev setup ^& launch
echo ============================================================
echo.

set PYTHONNOUSERSITE=1
rem The bundled portable Python uses a custom ._pth file, which disables
rem the usual "-m adds the current directory to sys.path" behavior -- so
rem "app" wouldn't be importable without this.
set "PYTHONPATH=%~dp0"

if exist "offline-sdk\portable-python\python.exe" (
    echo Using the bundled portable Python in offline-sdk\ -- all dependencies
    echo are already installed in it, so no install step, no internet, and no
    echo system Python required.
    echo.
    set "PYEXE=offline-sdk\portable-python\python.exe"
    goto :run
)

echo No bundled offline-sdk\portable-python found -- falling back to a
echo system Python install.
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH, and there is no bundled
    echo offline-sdk\portable-python to fall back to.
    echo.
    echo Either install Python 3.10+ from https://python.org, or ask
    echo whoever set up offline-sdk\ to include portable-python\.
    echo.
    pause
    exit /b 1
)

python -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] "python" was found on PATH but doesn't actually run --
    echo this is usually the Windows Store's placeholder python.exe, not a
    echo real Python install. Install Python 3.10+ from https://python.org
    echo ^(check "Add python.exe to PATH" during setup^), or ask whoever set
    echo up offline-sdk\ to include portable-python\.
    echo.
    pause
    exit /b 1
)

set "PYEXE=python"

if exist "offline-sdk\python-wheels" (
    echo Installing dependencies from local offline-sdk wheels ^(no internet needed^)...
    %PYEXE% -m pip install --no-index --find-links offline-sdk\python-wheels -r requirements.txt
) else (
    echo offline-sdk not found -- installing dependencies from PyPI ^(internet required^)...
    %PYEXE% -m pip install -r requirements.txt
)

if errorlevel 1 (
    echo.
    echo [ERROR] Dependency installation failed -- see the errors above.
    echo.
    pause
    exit /b 1
)

echo.
echo Dependencies ready.

:run
echo Starting the dev server -- your browser will open automatically at
echo http://127.0.0.1:8000
echo.
echo Press Ctrl+C in this window to stop the server.
echo ============================================================
echo.

%PYEXE% -m app.main

echo.
echo Server stopped.
pause
