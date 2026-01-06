#!/bin/bash
# FRCR Examiner Tool - macOS Double-Click Installer
# Simply DOUBLE-CLICK this file to install!

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Clear screen
clear

echo "============================================"
echo "FRCR Examiner Tool - Installation Wizard"
echo "============================================"
echo ""
echo "Welcome! This installer will set up FRCR Examiner on your Mac."
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
echo "This may take a moment..."
rsync -av --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' --exclude='venv' --exclude='env' --exclude='node_modules' --exclude='.DS_Store' --exclude='dist' --exclude='build' --exclude='release-*' "$SCRIPT_DIR/../../" "$INSTALL_DIR/" > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "Warning: Some files may not have been copied. Continuing..."
fi
echo "Application files copied!"
echo ""

# Install dependencies
echo "[4/6] Installing Python dependencies..."
echo "This may take a few minutes..."
cd "$INSTALL_DIR"
python3 -m pip install --upgrade pip --quiet > /dev/null 2>&1
python3 -m pip install -r requirements.txt --quiet

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies!"
    echo "Please check your internet connection and try again."
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
# Double-click this file to start the application

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Clear screen
clear

echo "============================================"
echo "       FRCR Examiner Tool - Starting       "
echo "============================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    osascript -e 'display dialog "Python 3 is not found! Please reinstall the application." buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

echo "Starting FRCR Examiner Tool..."
echo "Please wait while the application loads..."
echo ""
echo "The application will open in your web browser."
echo ""
echo "To stop the application:"
echo "  - Close this window"
echo "  - Or press Ctrl+C"
echo ""
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

# Remove old app bundle if exists
if [ -d "$APP_BUNDLE" ]; then
    rm -rf "$APP_BUNDLE"
fi

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
    <string>1.0.1</string>
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

# Check Python
if ! command -v python3 &> /dev/null; then
    osascript -e 'display dialog "Python 3 is not installed!\n\nPlease install from:\nhttps://www.python.org/downloads/" buttons {"OK"} default button "OK" with icon stop with title "FRCR Examiner"'
    exit 1
fi

# Start app
(sleep 2 && open http://127.0.0.1:5000) &
python3 app.py 2>&1 | tee "$HOME/Library/Logs/FRCR_Examiner.log"
EOFLAUNCHER

chmod +x "$APP_BUNDLE/Contents/MacOS/launcher"

echo "Application Bundle created!"
echo ""

# Success message
clear
echo "============================================"
echo "        Installation Complete! 🎉         "
echo "============================================"
echo ""
echo "The FRCR Examiner Tool has been installed successfully!"
echo ""
echo "🚀 How to Launch the Application:"
echo ""
echo "Option 1 (Recommended):"
echo "  - Go to your Applications folder"
echo "  - Double-click 'FRCR Examiner'"
echo ""
echo "Option 2:"
echo "  - Double-click: $LAUNCHER_PATH"
echo ""
echo ""
echo "⚠️  IMPORTANT - macOS Security Notice:"
echo "============================================"
echo "When you first run the app, macOS will show a security warning"
echo "because the app is not downloaded from the App Store."
echo ""
echo "To allow the app to run:"
echo "  1. Try to open the app (it will be blocked)"
echo "  2. Go to: System Preferences → Security & Privacy"
echo "  3. Click 'Open Anyway' next to the blocked app message"
echo ""
echo "OR:"
echo "  1. Right-click (Control+click) the app"
echo "  2. Select 'Open' from the menu"
echo "  3. Click 'Open' in the security dialog"
echo ""
echo "You only need to do this ONCE!"
echo ""
echo "============================================"
echo ""
echo "📂 Your data will be stored at:"
echo "   $INSTALL_DIR/instance/"
echo ""
echo "📧 Support: lotusheart2016@gmail.com"
echo "🌐 GitHub: github.com/visit-www/Frcr-examiner"
echo ""
echo "Thank you for installing FRCR Examiner Tool!"
echo ""
echo "Press Enter to close this window..."
read
