@echo off
REM FRCR Examiner Windows Installer
REM For doctors - simple and professional

setlocal enabledelayedexpansion

title FRCR Examiner - Installation

echo.
echo ==========================================
echo FRCR Examiner Tool - Windows Installation
echo ==========================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed!
    echo.
    echo FRCR Examiner requires Python 3.8 or higher.
    echo.
    echo Please install Python from:
    echo   https://www.python.org/downloads/
    echo.
    echo After installing Python, run this installer again.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Found Python %PYTHON_VERSION%
echo.

REM Get installation directory
set INSTALL_DIR=%PROGRAMFILES%\FRCR-Examiner
echo Installation directory: %INSTALL_DIR%
echo.

REM Create installation directory
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
)

REM Copy application files
echo Installing application files...
cd /d "%~dp0"

copy app.py "%INSTALL_DIR%\" >nul 2>&1
copy models.py "%INSTALL_DIR%\" >nul 2>&1
copy backup_database.py "%INSTALL_DIR%\" >nul 2>&1
copy backup_manager.py "%INSTALL_DIR%\" >nul 2>&1
copy backup_scheduler.py "%INSTALL_DIR%\" >nul 2>&1
copy requirements.txt "%INSTALL_DIR%\" >nul 2>&1
copy Procfile "%INSTALL_DIR%\" >nul 2>&1
copy README.md "%INSTALL_DIR%\" >nul 2>&1
copy HOW_TO_USE.md "%INSTALL_DIR%\" >nul 2>&1
copy CHANGELOG.md "%INSTALL_DIR%\" >nul 2>&1
copy CONTRIBUTING.md "%INSTALL_DIR%\" >nul 2>&1

REM Copy directories
if exist templates (
    xcopy templates "%INSTALL_DIR%\templates\" /E /I /Q >nul 2>&1
)
if exist static (
    xcopy static "%INSTALL_DIR%\static\" /E /I /Q >nul 2>&1
)
if exist dist (
    xcopy dist "%INSTALL_DIR%\dist\" /E /I /Q >nul 2>&1
)

echo [OK] Application files installed

REM Install Python dependencies
echo.
echo Installing Python dependencies...
echo This may take a few minutes...
echo.

cd /d "%INSTALL_DIR%"
python -m pip install --upgrade pip -q >nul 2>&1
python -m pip install -r requirements.txt -q >nul 2>&1

if errorlevel 1 (
    echo.
    echo WARNING: Some dependencies may not have installed correctly.
    echo The application may still work, but some features might be unavailable.
    echo.
)

echo [OK] Python dependencies installed
echo.

REM Create launcher script
echo Creating application launcher...
(
    echo @echo off
    echo cd /d "%INSTALL_DIR%"
    echo python app.py
) > "%INSTALL_DIR%\launch.bat"

REM Create Start Menu shortcut
echo Creating Start Menu shortcut...
powershell -Command "
$TargetPath = '%INSTALL_DIR%\launch.bat'
$ShortcutPath = '%APPDATA%\Microsoft\Windows\Start Menu\Programs\FRCR Examiner.lnk'
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.WorkingDirectory = '%INSTALL_DIR%'
$Shortcut.Save()
" 2>nul

REM Create Desktop shortcut
echo Creating Desktop shortcut...
powershell -Command "
$TargetPath = '%INSTALL_DIR%\launch.bat'
$ShortcutPath = '%USERPROFILE%\Desktop\FRCR Examiner.lnk'
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.WorkingDirectory = '%INSTALL_DIR%'
$Shortcut.Save()
" 2>nul

echo [OK] Shortcuts created
echo.

REM Success message
cls
echo.
echo ==========================================
echo INSTALLATION COMPLETE!
echo ==========================================
echo.
echo FRCR Examiner has been installed successfully!
echo.
echo Location: %INSTALL_DIR%
echo.
echo You can now launch FRCR Examiner by:
echo   - Double-clicking "FRCR Examiner" on your Desktop
echo   - Or searching for "FRCR Examiner" in Start Menu
echo.
echo.
pause
