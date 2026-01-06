#!/bin/bash
# FRCR Examiner Tool - macOS Installer
# This installer will set up FRCR Examiner on your Mac

echo "============================================"
echo "FRCR Examiner Tool - Installation Wizard"
echo "============================================"
echo ""

# Check for Python
echo "[1/6] Checking for Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed!"
    echo ""
    echo "Please install Python 3.8 or higher from:"
    echo "https://www.python.org/downloads/"
    echo ""
    echo "Or install using Homebrew:"
    echo "  brew install python@3.11"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi
echo "Python found: $(python3 --version)"
echo ""

# Set installation directory
INSTALL_DIR="$HOME/Applications/FRCR_Examiner"
echo "[2/6] Setting up installation directory..."
echo "Installation location: $INSTALL_DIR"
echo ""

# Create installation directory
mkdir -p "$INSTALL_DIR"

# Copy application files
echo "[3/6] Copying application files..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
rsync -av --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' --exclude='venv' --exclude='env' --exclude='node_modules' --exclude='.DS_Store' --exclude='dist' --exclude='build' "$SCRIPT_DIR/../../" "$INSTALL_DIR/" > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "Warning: Some files may not have been copied. Continuing..."
fi
echo "Application files copied!"
echo ""

# Install dependencies
echo "[4/6] Installing Python dependencies..."
echo "This may take a few minutes..."
cd "$INSTALL_DIR"
python3 -m pip install --upgrade pip > /dev/null 2>&1
python3 -m pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies!"
    read -p "Press Enter to exit..."
    exit 1
fi
echo "Dependencies installed successfully!"
echo ""

# Create launcher script
echo "[5/6] Creating launcher..."
LAUNCHER_PATH="$INSTALL_DIR/FRCR_Examiner_Launcher.command"
cat > "$LAUNCHER_PATH" << 'EOFLAUNCH'
#!/bin/bash
# FRCR Examiner Tool - Launcher

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    osascript -e 'display dialog "Python 3 is not found! Please reinstall the application." buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

# Start the application
echo "Starting FRCR Examiner Tool..."
echo "Please wait while the application loads..."
echo ""
echo "The application will open in your web browser."
echo ""
echo "To stop the application, close this window or press Ctrl+C."
echo "============================================"
echo ""

# Open browser after a short delay
(sleep 3 && open http://127.0.0.1:5000) &

# Run Flask application
python3 app.py
EOFLAUNCH

chmod +x "$LAUNCHER_PATH"
echo "Launcher created!"
echo ""

# Create Application Bundle
echo "[6/6] Creating Application Bundle..."
APP_BUNDLE="$HOME/Applications/FRCR Examiner.app"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

# Create Info.plist
cat > "$APP_BUNDLE/Contents/Info.plist" << 'EOFPLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>FRCR Examiner</string>
    <key>CFBundleDisplayName</key>
    <string>FRCR Examiner</string>
    <key>CFBundleIdentifier</key>
    <string>com.frcr.examiner</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>FRCR</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>app_icon</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOFPLIST

# Create launcher executable
cat > "$APP_BUNDLE/Contents/MacOS/launcher" << 'EOFLAUNCHER'
#!/bin/bash
INSTALL_DIR="$HOME/Applications/FRCR_Examiner"
cd "$INSTALL_DIR"
(sleep 2 && open http://127.0.0.1:5000) &
python3 app.py 2>&1 | tee "$HOME/Library/Logs/FRCR_Examiner.log"
EOFLAUNCHER

chmod +x "$APP_BUNDLE/Contents/MacOS/launcher"

echo "Application Bundle created!"
echo ""

# Success message
echo "============================================"
echo "Installation Complete!"
echo "============================================"
echo ""
echo "The FRCR Examiner Tool has been installed successfully!"
echo ""
echo "You can now launch the application:"
echo "  - Double-click 'FRCR Examiner' in your Applications folder"
echo "  - Or run: $LAUNCHER_PATH"
echo ""
echo ""
echo "IMPORTANT - macOS Security Notice:"
echo "============================================"
echo "When you first run the app, macOS may show a security warning"
echo "because the app is not downloaded from the App Store."
echo ""
echo "To allow the app to run:"
echo "  1. Try to open the app (it will be blocked)"
echo "  2. Go to: System Preferences > Security & Privacy"
echo "  3. Click 'Open Anyway' next to the blocked app message"
echo "  4. Or right-click the app and select 'Open'"
echo ""
echo "This is normal for apps distributed outside the App Store."
echo "Your data will be stored locally at:"
echo "$INSTALL_DIR/instance"
echo ""
echo "Thank you for installing FRCR Examiner Tool!"
echo ""
read -p "Press Enter to finish..."
