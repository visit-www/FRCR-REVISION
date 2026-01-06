@echo off
:: FRCR Examiner Tool - Windows Installer
:: This installer will set up FRCR Examiner on your Windows computer
echo ============================================
echo FRCR Examiner Tool - Installation Wizard
echo ============================================
echo.

:: Check for Python
echo [1/6] Checking for Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo.
    echo Please install Python 3.8 or higher from:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: During installation, check "Add Python to PATH"
    pause
    exit /b 1
)
echo Python found!
echo.

:: Set installation directory
set "INSTALL_DIR=%USERPROFILE%\FRCR_Examiner"
echo [2/6] Setting up installation directory...
echo Installation location: %INSTALL_DIR%
echo.

:: Create installation directory
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: Copy application files
echo [3/6] Copying application files...
xcopy /E /I /Y "..\..\" "%INSTALL_DIR%" /EXCLUDE:exclude.txt >nul 2>&1
if errorlevel 1 (
    echo Warning: Some files may not have been copied. Continuing...
)
echo Application files copied!
echo.

:: Install dependencies
echo [4/6] Installing Python dependencies...
echo This may take a few minutes...
cd "%INSTALL_DIR%"
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies!
    pause
    exit /b 1
)
echo Dependencies installed successfully!
echo.

:: Create desktop shortcut
echo [5/6] Creating desktop shortcut...
set "SHORTCUT=%USERPROFILE%\Desktop\FRCR Examiner.lnk"
set "LAUNCHER=%INSTALL_DIR%\dist\windows\launch.bat"

:: Create VBScript to create shortcut
echo Set oWS = WScript.CreateObject("WScript.Shell") > CreateShortcut.vbs
echo sLinkFile = "%SHORTCUT%" >> CreateShortcut.vbs
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> CreateShortcut.vbs
echo oLink.TargetPath = "%LAUNCHER%" >> CreateShortcut.vbs
echo oLink.WorkingDirectory = "%INSTALL_DIR%" >> CreateShortcut.vbs
echo oLink.Description = "FRCR Examiner Tool" >> CreateShortcut.vbs
echo oLink.IconLocation = "%INSTALL_DIR%\dist\icons\app_icon.ico" >> CreateShortcut.vbs
echo oLink.Save >> CreateShortcut.vbs

cscript CreateShortcut.vbs >nul
del CreateShortcut.vbs

echo Desktop shortcut created!
echo.

:: Create Start Menu entry
echo [6/6] Creating Start Menu entry...
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\FRCR Examiner.lnk"

echo Set oWS = WScript.CreateObject("WScript.Shell") > CreateShortcut.vbs
echo sLinkFile = "%STARTMENU%" >> CreateShortcut.vbs
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> CreateShortcut.vbs
echo oLink.TargetPath = "%LAUNCHER%" >> CreateShortcut.vbs
echo oLink.WorkingDirectory = "%INSTALL_DIR%" >> CreateShortcut.vbs
echo oLink.Description = "FRCR Examiner Tool" >> CreateShortcut.vbs
echo oLink.IconLocation = "%INSTALL_DIR%\dist\icons\app_icon.ico" >> CreateShortcut.vbs
echo oLink.Save >> CreateShortcut.vbs

cscript CreateShortcut.vbs >nul
del CreateShortcut.vbs

echo Start Menu entry created!
echo.

:: Success message
echo ============================================
echo Installation Complete!
echo ============================================
echo.
echo The FRCR Examiner Tool has been installed successfully!
echo.
echo You can now launch the application:
echo   - Double-click "FRCR Examiner" icon on your Desktop
echo   - Or find it in your Start Menu
echo.
echo The application will open in your default web browser.
echo Your data will be stored locally at:
echo %INSTALL_DIR%\instance
echo.
echo Thank you for installing FRCR Examiner Tool!
echo.
pause
