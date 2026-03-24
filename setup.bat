@echo off
setlocal

REM Move to the folder where this script is located
cd /d "%~dp0"

set "VENV_DIR=.venv"

echo [1/4] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not available in PATH.
    echo Install Python 3.10+ and make sure "Add python.exe to PATH" is enabled.
    pause
    exit /b 1
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [2/4] Creating virtual environment in %VENV_DIR%...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [2/4] Virtual environment already exists.
)

echo [3/4] Upgrading pip...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    pause
    exit /b 1
)

echo [4/4] Installing required packages...
"%VENV_DIR%\Scripts\python.exe" -m pip install requests pymodbus
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

if not exist ".env" (
    echo Creating .env template...
    > ".env" (
        echo # Eneria / MEWS configuration
        echo # Fill these two required values before starting the app
        echo MEWS_CLIENT_TOKEN=
        echo MEWS_ACCESS_TOKEN=
        echo.
        echo # Optional values
        echo MEWS_BASE_URL=https://api.mews.com/api/connector/v1
        echo MODBUS_PORT=5020
        echo POLLING_INTERVAL=300
        echo SHOW_UI=true
        echo.
        echo # Test mode - mock data, no MEWS API call
        echo MOCK_MODE=false
        echo MOCK_ROOM_COUNT=10
    )
) else (
    echo .env already exists, keeping current values.
)

echo.
echo Setup complete.
echo If .env was just created, edit it and set MEWS_CLIENT_TOKEN and MEWS_ACCESS_TOKEN.
echo You can now run start.bat (visible logs) or start_silent.bat (hidden).
pause
exit /b 0
