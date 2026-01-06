#!/bin/bash
# Simple macOS Installer for FRCR Examiner
# Creates FRCR-Examiner.app in user's Applications folder
# No warnings, no scripts, just works!

clear

APP_NAME="FRCR Examiner"
APP_ID="com.frcr.examiner"
INSTALL_DIR="$HOME/Applications/FRCR-Examiner"
APP_BUNDLE="$HOME/Applications/FRCR-Examiner.app"

echo "=========================================="
echo "$APP_NAME - Installation Wizard"
echo "=========================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found"
    echo ""
    echo "Please install Python 3.8+ from:"
    echo "  https://www.python.org/downloads/"
    echo ""
    open "https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python $PYTHON_VERSION found"
echo ""

# Create app directories
echo "Setting up application..."
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"
mkdir -p "$INSTALL_DIR"

# Copy application files
echo "Installing files..."
SCRIPT_DIR="$(dirname "$0")"

# Find the source directory (could be in /Volumes for mounted DMG)
if [ -d "$SCRIPT_DIR/app.py" ]; then
    SOURCE_DIR="$SCRIPT_DIR"
elif [ -f "../app.py" ]; then
    SOURCE_DIR="../"
elif [ -f "../../app.py" ]; then
    SOURCE_DIR="../../"
else
    SOURCE_DIR="/tmp/frcr-source-$$"  # Fallback
fi

# Copy app files to installation directory
if [ -d "$SOURCE_DIR" ] && [ -f "$SOURCE_DIR/app.py" ]; then
    cp "$SOURCE_DIR"/app.py "$INSTALL_DIR/" 2>/dev/null
    cp "$SOURCE_DIR"/models.py "$INSTALL_DIR/" 2>/dev/null
    cp "$SOURCE_DIR"/backup_*.py "$INSTALL_DIR/" 2>/dev/null
    cp "$SOURCE_DIR"/requirements.txt "$INSTALL_DIR/" 2>/dev/null
    cp "$SOURCE_DIR"/Procfile "$INSTALL_DIR/" 2>/dev/null
    cp "$SOURCE_DIR"/README.md "$INSTALL_DIR/" 2>/dev/null
    
    # Copy directories
    cp -r "$SOURCE_DIR"/templates "$INSTALL_DIR/" 2>/dev/null
    cp -r "$SOURCE_DIR"/static "$INSTALL_DIR/" 2>/dev/null
fi

# Create the main executable script that launches the app
cat > "$APP_BUNDLE/Contents/MacOS/FRCR-Examiner" << 'LAUNCHER'
#!/bin/bash
# FRCR Examiner Main Launcher
# This script starts the Flask server and opens the browser

INSTALL_DIR="$HOME/Applications/FRCR-Examiner"

# Install dependencies silently
if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    python3 -m pip install -q -r "$INSTALL_DIR/requirements.txt" 2>/dev/null
fi

# Start Flask server
cd "$INSTALL_DIR"
python3 app.py &
SERVER_PID=$!

# Open browser after a short delay
sleep 3
open "http://localhost:5000"

# Keep running
wait $SERVER_PID

LAUNCHER

chmod +x "$APP_BUNDLE/Contents/MacOS/FRCR-Examiner"

# Create Info.plist
cat > "$APP_BUNDLE/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>FRCR-Examiner</string>
    <key>CFBundleIdentifier</key>
    <string>com.frcr.examiner</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>FRCR Examiner</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.3</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.14</string>
</dict>
</plist>
PLIST

# Install dependencies
echo "Installing Python dependencies..."
cd "$INSTALL_DIR"
python3 -m pip install -q -r requirements.txt 2>/dev/null

echo ""
echo "=========================================="
echo "✓ Installation Complete!"
echo "=========================================="
echo ""
echo "$APP_NAME is now ready to use!"
echo ""
echo "To launch:"
echo "  1. Open Finder → Applications"
echo "  2. Find FRCR-Examiner.app"
echo "  3. Double-click to launch"
echo ""
echo "Or use Spotlight:"
echo "  Cmd+Space → Type 'FRCR' → Press Enter"
echo ""
echo "On first launch, you may see a security prompt."
echo "Click 'Open' - you only need to do this once."
echo ""
