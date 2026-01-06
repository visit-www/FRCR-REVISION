#!/bin/bash
# Build macOS PKG Installer for FRCR Examiner
# Professional installer that auto-runs when user double-clicks

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../.."
VERSION="${1:-1.0.2}"
BUILD_DIR="/tmp/frcr-pkg-build-$$"
PKG_OUTPUT="$PROJECT_ROOT/dist/FRCR-Examiner-macOS-v${VERSION}.pkg"

echo "=========================================="
echo "Building macOS PKG Installer"
echo "Version: $VERSION"
echo "=========================================="
echo ""

# Create build structure
mkdir -p "$BUILD_DIR/payload"
mkdir -p "$BUILD_DIR/scripts"

echo "[1/4] Preparing application files..."
cd "$PROJECT_ROOT"

# Create installation directory structure
APP_INSTALL_DIR="$BUILD_DIR/payload/opt/FRCR-Examiner"
mkdir -p "$APP_INSTALL_DIR"

# Copy core application files
cp app.py "$APP_INSTALL_DIR/"
cp models.py "$APP_INSTALL_DIR/"
cp backup_*.py "$APP_INSTALL_DIR/"
cp requirements.txt "$APP_INSTALL_DIR/"
cp Procfile "$APP_INSTALL_DIR/"
cp README.md "$APP_INSTALL_DIR/"
cp HOW_TO_USE.md "$APP_INSTALL_DIR/"
cp CHANGELOG.md "$APP_INSTALL_DIR/"
cp CONTRIBUTING.md "$APP_INSTALL_DIR/"

# Copy directories
cp -r templates "$APP_INSTALL_DIR/"
cp -r static "$APP_INSTALL_DIR/"
cp -r dist "$APP_INSTALL_DIR/"

echo "[2/4] Creating installer scripts..."

# Create preinstall script (check Python)
cat > "$BUILD_DIR/scripts/preinstall" << 'PREINSTALL_SCRIPT'
#!/bin/bash
# Pre-installation checks

echo "Checking system requirements..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "WARNING: Python 3 not found"
    echo "Installing Python is required to use FRCR Examiner"
    echo "Please install Python 3.8+ from https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $PYTHON_VERSION"

PREINSTALL_SCRIPT

chmod +x "$BUILD_DIR/scripts/preinstall"

# Create postinstall script (setup app, install deps, create shortcuts)
cat > "$BUILD_DIR/scripts/postinstall" << 'POSTINSTALL_SCRIPT'
#!/bin/bash
# Post-installation setup

INSTALL_DIR="/opt/FRCR-Examiner"
APP_DIR="$HOME/Applications/FRCR-Examiner.app"
BIN_DIR="$HOME/.local/bin"

echo "================================================"
echo "FRCR Examiner - Installation in Progress"
echo "================================================"
echo ""

# Create bin directory for launcher
mkdir -p "$BIN_DIR"

# Create launcher script
cat > "$BIN_DIR/frcr-examiner" << 'LAUNCHER'
#!/bin/bash
cd "$INSTALL_DIR"
python3 app.py
LAUNCHER

chmod +x "$BIN_DIR/frcr-examiner"

# Install Python dependencies
echo "Installing Python dependencies..."
echo "This may take 2-3 minutes..."
echo ""

cd "$INSTALL_DIR"
python3 -m pip install --upgrade pip --quiet 2>/dev/null || true
python3 -m pip install -r requirements.txt --quiet 2>/dev/null

if [ $? -ne 0 ]; then
    echo "Warning: Some dependencies may not have installed correctly"
    echo "The application may still work, but some features might be unavailable"
fi

echo ""
echo "Creating application shortcuts..."

# Create macOS Application Bundle
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# Create launcher for app bundle
cat > "$APP_DIR/Contents/MacOS/FRCR-Examiner" << 'BUNDLELAUNCHER'
#!/bin/bash
cd /opt/FRCR-Examiner
python3 app.py
BUNDLELAUNCHER

chmod +x "$APP_DIR/Contents/MacOS/FRCR-Examiner"

# Create Info.plist
cat > "$APP_DIR/Contents/Info.plist" << 'PLIST'
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
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
PLIST

echo ""
echo "================================================"
echo "✓ Installation Complete!"
echo "================================================"
echo ""
echo "FRCR Examiner has been installed successfully!"
echo ""
echo "To launch:"
echo "  1. Open Applications folder"
echo "  2. Find FRCR-Examiner.app"
echo "  3. Double-click to launch"
echo ""
echo "Or use Spotlight:"
echo "  Press Cmd+Space and type 'FRCR'"
echo ""

POSTINSTALL_SCRIPT

chmod +x "$BUILD_DIR/scripts/postinstall"

echo "[3/4] Creating PKG file..."

# Create the package
pkgbuild --root "$BUILD_DIR/payload" \
         --scripts "$BUILD_DIR/scripts" \
         --identifier com.frcr.examiner \
         --version "$VERSION" \
         --ownership preserve \
         "$PKG_OUTPUT" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "[4/4] Cleaning up..."
    rm -rf "$BUILD_DIR"
    
    echo ""
    echo "=========================================="
    echo "✓ PKG Created Successfully!"
    echo "=========================================="
    echo ""
    echo "Installer: $PKG_OUTPUT"
    echo "Size: $(du -h "$PKG_OUTPUT" | awk '{print $1}')"
    echo ""
    echo "Installation Instructions:"
    echo "  1. Double-click FRCR-Examiner-macOS-v${VERSION}.pkg"
    echo "  2. macOS Installer opens automatically"
    echo "  3. Click 'Install' to proceed"
    echo "  4. Enter your password when prompted"
    echo "  5. Installation completes automatically"
    echo ""
    echo "That's it! No additional steps needed."
    echo ""
else
    echo "❌ Failed to create PKG"
    rm -rf "$BUILD_DIR"
    exit 1
fi
