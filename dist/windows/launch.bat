@echo off
:: FRCR Examiner Tool - Launcher
:: This script starts the FRCR Examiner application

:: Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%..\.."

:: Change to application directory
cd /d "%APP_DIR%"

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not found!
    echo Please reinstall the application.
    pause
    exit /b 1
)

:: Start the application
echo Starting FRCR Examiner Tool...
echo Please wait while the application loads...
echo.
echo The application will open in your web browser.
echo.
echo To stop the application, close this window.
echo ============================================
echo.

:: Run Flask application and open browser
start http://127.0.0.1:5000
python app.py

pause
