#!/bin/bash

###############################################################################
# FRCR Examiner - Installer DMG Builder
#
# Creates a professional installer DMG with automatic installation
# This script bundles the app with the installer script
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/dist"
INSTALLER_STAGING="$SCRIPT_DIR/.installer-staging"
INSTALLER_DMG_NAME="FRCR-Examiner-Installer-1.0.0.dmg"
APP_DMG="FRCR Examiner-1.0.0-arm64.dmg"

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║        FRCR Examiner - Professional Installer Builder         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Function to display messages
status() { echo -e "${GREEN}✓${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1" >&2; exit 1; }
info() { echo -e "${BLUE}ℹ${NC} $1"; }

# Check if app DMG exists
if [ ! -f "$BUILD_DIR/$APP_DMG" ]; then
    error "App DMG not found at: $BUILD_DIR/$APP_DMG"
    error "Please run 'npm run build-mac' first"
fi

status "Found app DMG: $APP_DMG"

# Clean up any previous staging
if [ -d "$INSTALLER_STAGING" ]; then
    info "Cleaning up previous build..."
    rm -rf "$INSTALLER_STAGING"
fi

# Create staging directory
mkdir -p "$INSTALLER_STAGING/FRCR Examiner Installer"

info "Setting up installer package..."

# Copy the app DMG to installer
cp "$BUILD_DIR/$APP_DMG" "$INSTALLER_STAGING/FRCR Examiner Installer/"
status "Copied app DMG"

# Copy the install script
cp "$SCRIPT_DIR/install.sh" "$INSTALLER_STAGING/FRCR Examiner Installer/"
chmod +x "$INSTALLER_STAGING/FRCR Examiner Installer/install.sh"
status "Included installer script"

# Create a README for the installer
cat > "$INSTALLER_STAGING/FRCR Examiner Installer/README.txt" << 'EOF'
================================================================================
FRCR Examiner 1.0.0 - Professional Installer
================================================================================

INSTALLATION OPTIONS:

Option 1: Automatic Installation (Recommended)
─────────────────────────────────────────────────
1. Open Terminal (Applications → Utilities → Terminal)
2. Drag this folder into Terminal
3. Type: cd [then paste folder path from previous step]
4. Press Enter
5. Type: bash install.sh
6. Press Enter
7. Follow the prompts

The app will be automatically installed to your Applications folder!


Option 2: Manual Installation
─────────────────────────────
1. Double-click "FRCR Examiner-1.0.0-arm64.dmg"
2. Drag the app to your Applications folder
3. Run the app

Installation Complete! The app will be in your Applications folder.

Enjoy using FRCR Examiner!
================================================================================
EOF

status "Created installer README"

# Create a .command file for one-click installation (doesn't need Terminal)
cat > "$INSTALLER_STAGING/FRCR Examiner Installer/Install FRCR Examiner.command" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
bash install.sh "FRCR Examiner-1.0.0-arm64.dmg"
read -p "Press Enter to close this window..."
EOF

chmod +x "$INSTALLER_STAGING/FRCR Examiner Installer/Install FRCR Examiner.command"
status "Created one-click installer (.command file)"

# Create the installer DMG
info "Creating installer DMG..."

# Remove old DMG if exists
rm -f "$BUILD_DIR/$INSTALLER_DMG_NAME"

# Use hdiutil to create the DMG
if hdiutil create -volname "FRCR Examiner Installer" \
                  -srcfolder "$INSTALLER_STAGING/FRCR Examiner Installer" \
                  -ov -format UDZO \
                  "$BUILD_DIR/$INSTALLER_DMG_NAME" >/dev/null 2>&1; then
    status "Installer DMG created successfully"
else
    error "Failed to create installer DMG using hdiutil"
fi

# Verify DMG was created
if [ ! -f "$BUILD_DIR/$INSTALLER_DMG_NAME" ]; then
    error "Failed to create installer DMG"
fi

# Get DMG size
DMG_SIZE=$(ls -lh "$BUILD_DIR/$INSTALLER_DMG_NAME" | awk '{print $5}')

# Clean up staging
rm -rf "$INSTALLER_STAGING"

echo
echo -e "${GREEN}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           Installer Created Successfully!                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo
echo "Installer Details:"
echo "  File: $INSTALLER_DMG_NAME"
echo "  Location: $BUILD_DIR/"
echo "  Size: $DMG_SIZE"
echo
echo "The installer DMG includes:"
echo "  • FRCR Examiner application"
echo "  • Automatic installation script"
echo "  • One-click installer (.command file)"
echo "  • Comprehensive documentation"
echo

info "Sharing Instructions:"
echo "  1. Send the DMG file to colleagues:"
echo "     $INSTALLER_DMG_NAME"
echo
echo "  2. They can either:"
echo "     a) Double-click 'Install FRCR Examiner.command' for one-click install"
echo "     b) Follow the README.txt for manual or Terminal installation"
echo
echo "  3. The app will be automatically installed to /Applications"
echo

status "Ready for distribution!"
