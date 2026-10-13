@echo off
setlocal
cd /d "%~dp0"
echo Catchy AI - product launcher
if exist ".venv\Scripts\python.exe" goto dependencies
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -m venv .venv
    if not errorlevel 1 goto dependencies
)
where python >nul 2>&1
if not errorlevel 1 (
    python -m venv .venv
    if not errorlevel 1 goto dependencies
)
echo Install Python 3.11 or newer from https://www.python.org/downloads/
echo Enable Add Python to PATH, extract this ZIP fully, and try again.
goto finished
:dependencies
.venv\Scripts\python.exe -m pip --version >nul 2>&1
if errorlevel 1 .venv\Scripts\python.exe -m ensurepip --upgrade
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto finished
echo Keep this window open while using Catchy AI.
.venv\Scripts\python.exe -m backend.launcher
:finished
echo If startup failed, copy the error above when asking for help.
pause
