@echo off
REM FRCR Examiner - Start Server (Windows)

cls
echo ==========================================
echo   FRCR Examiner - Local Server
echo ==========================================
echo.

REM Create venv if needed
if not exist "venv" (
    echo Creating Python environment...
    python -m venv venv
)

REM Activate venv
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -q -r requirements.txt

REM Run server
echo.
echo Starting server...
echo Access at: http://localhost:5000
echo Press Ctrl+C to stop
echo.

python app.py
pause
