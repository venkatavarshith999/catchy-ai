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
.venv\Scripts\python.exe scripts\check_runtime.py >nul 2>&1
if not errorlevel 1 goto launch
echo Preparing dependencies. This step needs internet on the first run.
.venv\Scripts\python.exe -m pip --version >nul 2>&1
if errorlevel 1 .venv\Scripts\python.exe -m ensurepip --upgrade
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe scripts\check_runtime.py
if errorlevel 1 goto failed
:launch
echo Keep this window open while using Catchy AI.
.venv\Scripts\python.exe -m backend.launcher %*
if errorlevel 1 goto failed
echo Catchy AI stopped.
pause
exit /b 0
:failed
echo Startup failed. Copy the error above when asking for help.
echo Run this file directly from Windows, not inside an isolated preview runner.
pause
exit /b 1
:finished
pause
exit /b 1
