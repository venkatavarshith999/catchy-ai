@echo off
setlocal
cd /d "%~dp0"
echo Catchy AI - starting your local website
echo Keep this window open while using Catchy AI.
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
    if not errorlevel 1 (
        py -3 -m backend.launcher
        goto finished
    )
)
where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
    if not errorlevel 1 (
        python -m backend.launcher
        goto finished
    )
)
echo Python 3.11 or newer was not found.
echo Install Python from https://www.python.org/downloads/
echo Enable Add Python to PATH, then run this file again.
:finished
echo If startup failed, copy the error above when asking for help.
pause
