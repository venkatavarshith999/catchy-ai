@echo off
setlocal
cd /d "%~dp0"
echo.
echo Catchy AI - choose how to start
echo 1. Gemini - enter your key privately
echo 2. Rules only - no key required
echo 3. OpenAI - enter your key privately
echo.
choice /C 123 /N /M "Choose 1, 2, or 3: "
if errorlevel 255 exit /b 1
if errorlevel 3 goto openai
if errorlevel 2 goto rules
if errorlevel 1 goto gemini
exit /b 1
:gemini
call "%~dp0START-WINDOWS.bat" --gemini
exit /b %errorlevel%
:rules
call "%~dp0START-WINDOWS.bat" --rules
exit /b %errorlevel%
:openai
call "%~dp0START-WINDOWS.bat" --openai
exit /b %errorlevel%
