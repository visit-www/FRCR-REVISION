@echo off
REM Build script for FRCR Examiner Electron app on Windows

echo.
echo 🔨 Building FRCR Examiner Electron App
echo ======================================
echo.

REM Check if node_modules exists
if not exist "node_modules" (
  echo 📦 Installing dependencies...
  call npm install
  if errorlevel 1 goto error
)

echo 🪟 Building for Windows...
call npm run build-win
if errorlevel 1 goto error

echo.
echo ✅ Windows build complete!
echo 📦 Output: dist\FRCR Examiner-*.exe
echo.
echo 🎉 Installer ready for distribution!
pause
exit /b 0

:error
echo.
echo ❌ Build failed!
pause
exit /b 1
