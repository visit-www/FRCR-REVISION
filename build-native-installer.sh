#!/bin/bash

###############################################################################
# Build FRCR Examiner - Native App Installer DMG
# Creates a DMG with the native macOS app and install script
###############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="FRCR Examiner"
APP_SOURCE="$SCRIPT_DIR/dist/FRCR Examiner.app"
OUTPUT_DIR="$SCRIPT_DIR/dist"
INSTALLER_SCRIPT="$SCRIPT_DIR/install.sh"
TEMP_STAGING="/tmp/frcr_installer_build_$$"

echo
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     FRCR Examiner - Native App Installer Builder               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo

# Cleanup function
cleanup() {
    rm -rf "$TEMP_STAGING"
    if [ -n "$DMG_MOUNT" ] && [ -d "$DMG_MOUNT" ]; then
        hdiutil unmount "$DMG_MOUNT" 2>/dev/null || true
    fi
}

trap cleanup EXIT

# Check for required files
if [ ! -d "$APP_SOURCE" ]; then
    echo "✗ Native app not found at: $APP_SOURCE"
    echo "  Please run: bash build-native-app.sh"
    exit 1
fi

if [ ! -f "$INSTALLER_SCRIPT" ]; then
    echo "✗ Installer script not found at: $INSTALLER_SCRIPT"
    exit 1
fi

echo "✓ Creating installer DMG..."
echo

# Create staging directory
mkdir -p "$TEMP_STAGING"

# Copy the app
echo "  Copying app..."
cp -r "$APP_SOURCE" "$TEMP_STAGING/"

# Copy installer script
echo "  Copying installer script..."
cp "$INSTALLER_SCRIPT" "$TEMP_STAGING/"

# Create a .command file for one-click installation
echo "  Creating one-click installer..."
cat > "$TEMP_STAGING/Install FRCR Examiner.command" << 'COMMAND_EOF'
#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$DIR/install.sh" "$DIR/FRCR Examiner.app"
COMMAND_EOF

chmod +x "$TEMP_STAGING/Install FRCR Examiner.command"

# Create README
cat > "$TEMP_STAGING/README.txt" << 'README_EOF'
FRCR Examiner - Native macOS Application
=========================================

QUICK START:
1. Double-click "Install FRCR Examiner.command"
2. Wait 2-3 minutes for installation
3. The app will launch automatically

OR manually:
1. Drag "FRCR Examiner.app" to the Applications folder
2. Open Applications folder and double-click to launch

The app will open in your default web browser.
Database and settings are stored in: ~/Library/Application Support/FRCR Examiner/

For support: https://github.com/visit-www/Frcr-examiner
EOF

# Create DMG
DMG_NAME="FRCR-Examiner-Installer-1.0.0.dmg"
DMG_PATH="$OUTPUT_DIR/$DMG_NAME"

echo "  Creating DMG volume..."

# Remove existing DMG if present
if [ -f "$DMG_PATH" ]; then
    rm "$DMG_PATH"
fi

# Create temporary DMG
hdiutil create -volname "FRCR Examiner Installer" \
    -srcfolder "$TEMP_STAGING" \
    -ov -format UDZO \
    "$DMG_PATH"

# Verify
if [ -f "$DMG_PATH" ]; then
    SIZE=$(du -h "$DMG_PATH" | cut -f1)
    echo
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║              ✓ Installer DMG Created Successfully              ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo
    echo "Location: $DMG_PATH"
    echo "Size: $SIZE"
    echo
    echo "The installer DMG includes:"
    echo "  • FRCR Examiner native app"
    echo "  • Automatic installation script"
    echo "  • One-click installer (.command file)"
    echo "  • Comprehensive README"
    echo
    echo "ℹ Sharing Instructions:"
    echo "  1. Send the DMG file to colleagues:"
    echo "     $DMG_NAME"
    echo ""
    echo "  2. They can either:"
    echo "     a) Double-click 'Install FRCR Examiner.command' for one-click install"
    echo "     b) Follow the README.txt for manual or Terminal installation"
    echo ""
    echo "  3. The app will be automatically installed to /Applications"
    echo
    echo "✓ Ready for distribution!"
else
    echo "✗ Failed to create installer DMG"
    exit 1
fi
