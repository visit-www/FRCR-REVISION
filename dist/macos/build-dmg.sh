#!/bin/bash
# Build macOS DMG Installer for FRCR Examiner

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../.."
VERSION="${1:-1.0.2}"
DMG_TEMP="/tmp/frcr-dmg-build-$$"
DMG_OUTPUT="$PROJECT_ROOT/dist/FRCR-Examiner-macOS-v${VERSION}.dmg"

echo "=========================================="
echo "Building macOS DMG Installer"
echo "Version: $VERSION"
echo "=========================================="
echo ""

# Create temporary build directory
mkdir -p "$DMG_TEMP/FRCR Examiner"

echo "[1/5] Copying application files..."
cd "$PROJECT_ROOT"

# Copy Python app files
cp app.py "$DMG_TEMP/FRCR Examiner/"
cp models.py "$DMG_TEMP/FRCR Examiner/"
cp backup_*.py "$DMG_TEMP/FRCR Examiner/"
cp requirements.txt "$DMG_TEMP/FRCR Examiner/"
cp Procfile "$DMG_TEMP/FRCR Examiner/"
cp README.md "$DMG_TEMP/FRCR Examiner/"
cp HOW_TO_USE.md "$DMG_TEMP/FRCR Examiner/"
cp CHANGELOG.md "$DMG_TEMP/FRCR Examiner/"
cp CONTRIBUTING.md "$DMG_TEMP/FRCR Examiner/"

# Copy folders
cp -r templates "$DMG_TEMP/FRCR Examiner/"
cp -r static "$DMG_TEMP/FRCR Examiner/"
cp -r dist "$DMG_TEMP/FRCR Examiner/"

echo "[2/5] Creating installation script..."
cat > "$DMG_TEMP/FRCR Examiner/INSTALL.command" << 'INSTALL_SCRIPT'
#!/bin/bash
# FRCR Examiner Installation Script for macOS

set -e

APP_NAME="FRCR Examiner"
INSTALL_DIR="$HOME/Applications/FRCR-Examiner"
APP_DIR="$INSTALL_DIR/app"

clear
echo "=========================================="
echo "FRCR Examiner Tool - macOS Installation"
echo "=========================================="
echo ""

# Check if Python 3 is installed
echo "Checking Python 3 installation..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed!"
    echo ""
    echo "Please install Python 3 from:"
    echo "  https://www.python.org/downloads/"
    echo ""
    read -p "Press Enter to open Python website..."
    open "https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Found Python $PYTHON_VERSION"
echo ""

# Create installation directory
echo "Setting up installation directory..."
mkdir -p "$APP_DIR"

# Copy application files
echo "Installing application files..."
cp -r "$(dirname "$0")"/* "$APP_DIR/" 2>/dev/null || true
cd "$APP_DIR"

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
echo "This may take a few minutes..."
python3 -m pip install --upgrade pip --quiet
python3 -m pip install -r requirements.txt --quiet

# Create launcher script
echo ""
echo "Creating application launcher..."
mkdir -p "$INSTALL_DIR/bin"

cat > "$INSTALL_DIR/bin/frcr-examiner" << 'LAUNCHER'
#!/bin/bash
cd "$(dirname "$0")/../app"
python3 app.py
LAUNCHER

chmod +x "$INSTALL_DIR/bin/frcr-examiner"

# Create macOS Application Bundle
echo "Creating macOS application bundle..."
APP_BUNDLE="$HOME/Applications/FRCR-Examiner.app"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

# Create launcher for app bundle
cat > "$APP_BUNDLE/Contents/MacOS/FRCR-Examiner" << 'BUNDLELAUNCHER'
#!/bin/bash
cd "$(dirname "$0")/../../app"
python3 app.py
BUNDLELAUNCHER

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
    <string>1.0.2</string>
    <key>CFBundleVersion</key>
    <string>1</string>
</dict>
</plist>
PLIST

# Installation complete
clear
echo "=========================================="
echo "✓ Installation Complete!"
echo "=========================================="
echo ""
echo "FRCR Examiner has been installed to:"
echo "  $HOME/Applications/FRCR-Examiner.app"
echo ""
echo "How to Launch:"
echo "  Option 1: Open Applications folder → FRCR-Examiner.app"
echo "  Option 2: Use Spotlight (Cmd+Space) → Type 'FRCR'"
echo ""
echo "On first launch, macOS may ask for permission."
echo "Click 'Open' when prompted."
echo ""
read -p "Press Enter to open the Applications folder..."
open "$HOME/Applications/"

INSTALL_SCRIPT

chmod +x "$DMG_TEMP/FRCR Examiner/INSTALL.command"

echo "[3/5] Creating DMG background..."
# Create a simple background image directory
mkdir -p "$DMG_TEMP/.background"

cat > "$DMG_TEMP/.background/background.pdf" << 'PDF_HEADER'
%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 300] /Contents 4 0 R >>
endobj
4 0 obj
<< >>
stream
BT
/F1 24 Tf
50 250 Td
(FRCR Examiner) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000214 00000 n 
trailer
<< /Size 5 /Root 1 0 R >>
startxref
313
%%EOF
PDF_HEADER

echo "[4/5] Creating DMG file..."
# Remove old DMG if exists
rm -f "$DMG_OUTPUT"

# Create DMG
hdiutil create -volname "FRCR Examiner" \
    -srcfolder "$DMG_TEMP" \
    -ov \
    -format UDZO \
    "$DMG_OUTPUT" 2>/dev/null

echo "[5/5] Cleaning up..."
rm -rf "$DMG_TEMP"

echo ""
echo "=========================================="
echo "✓ DMG Created Successfully!"
echo "=========================================="
echo ""
echo "DMG Location: $DMG_OUTPUT"
echo "File Size: $(du -h "$DMG_OUTPUT" | awk '{print $1}')"
echo ""
echo "Users can now:"
echo "  1. Double-click the DMG file"
echo "  2. Double-click INSTALL.command"
echo "  3. Follow the installation prompts"
echo ""
