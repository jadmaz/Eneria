@echo off
setlocal

cd /d "%~dp0"
set "VENV_PYTHON=.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo Virtual environment not found. Running setup first...
    call "%~dp0setup.bat"
    if errorlevel 1 exit /b 1
)

echo Starting Eneria server...
echo Press Ctrl+C to stop.
echo.
"%VENV_PYTHON%" "%~dp0program.py"

echo.
echo Program stopped.
pause
exit /b 0
