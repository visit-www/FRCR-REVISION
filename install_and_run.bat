@echo off
REM FRCR Examiner - Windows Installer & Launcher
REM This script sets up and runs FRCR Examiner with minimal user interaction

setlocal enabledelayedexpansion

REM Colors won't work in standard cmd.exe, but let's make it user-friendly anyway
title FRCR Examiner - Installation & Launch

echo ===================================================================
echo   FRCR Examiner - Medical Exam Management System
echo ===================================================================

REM Get script directory
set SCRIPT_DIR=%~dp0
set VENV_DIR=%SCRIPT_DIR%.venv
set DATABASE=%SCRIPT_DIR%frcr_examiner.db
set PORT=5000
set HOST=127.0.0.1

REM Check Python installation
echo.
echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION% found

REM Create virtual environment if it doesn't exist
if not exist "%VENV_DIR%" (
    echo.
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
    echo [OK] Virtual environment created
)

REM Activate virtual environment
echo.
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
echo [OK] Virtual environment activated

REM Install dependencies
echo.
echo Installing dependencies (this may take a minute)...
python -m pip install --upgrade pip setuptools wheel >nul 2>&1
pip install -r "%SCRIPT_DIR%requirements.txt" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed

REM Initialize database if needed
if not exist "%DATABASE%" (
    echo.
    echo Initializing database...
    python << 'EOF'
import sys
sys.path.insert(0, r'%SCRIPT_DIR%')
from app import app, db
with app.app_context():
    db.create_all()
print("[OK] Database initialized")
EOF
)

REM Launch Flask app
echo.
echo ===================================================================
echo [OK] Starting FRCR Examiner...
echo ===================================================================
echo.
echo Opening browser: http://%HOST%:%PORT%
echo Press Ctrl+C to stop the server
echo.

REM Open browser (Windows specific)
timeout /t 2 /nobreak >nul 2>&1
start http://%HOST%:%PORT%

REM Run Flask
cd /d "%SCRIPT_DIR%"
python app.py

pause
