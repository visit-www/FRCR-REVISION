#!/bin/bash

###############################################################################
# FRCR Examiner - Professional Installer Script
# 
# This script automates the installation of FRCR Examiner
# Usage: bash install.sh [DMG_or_ZIP_path]
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Paths
APP_NAME="FRCR Examiner"
APP_PATH="/Applications/FRCR Examiner.app"
APPS_FOLDER="/Applications"
TEMP_DIR="/tmp/frcr_installer_$$"

# Display header
echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          ${APP_NAME} - Professional Installer              ║"
echo "║                  Version 1.0.0                                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Function to display status messages
status() {
    echo -e "${GREEN}✓${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Function to cleanup on exit
cleanup() {
    if [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
    if [ -n "$DMG_MOUNT" ] && [ -d "$DMG_MOUNT" ]; then
        hdiutil unmount "$DMG_MOUNT" 2>/dev/null || true
    fi
}

trap cleanup EXIT

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    error "This installer only works on macOS"
    exit 1
fi

# Check if Xcode Command Line Tools are available (for hdiutil, etc.)
if ! command -v hdiutil &> /dev/null; then
    warning "Some tools may not be available, but installation will continue..."
fi

info "Starting ${APP_NAME} installation..."
echo

# Check for argument (DMG or ZIP file path)
if [ -n "$1" ]; then
    SOURCE_FILE="$1"
    if [ ! -f "$SOURCE_FILE" ]; then
        error "File not found: $SOURCE_FILE"
        exit 1
    fi
    info "Installing from: $SOURCE_FILE"
else
    # Try to find DMG in common locations
    info "Looking for installation file..."
    
    if [ -f "$HOME/Downloads/FRCR Examiner-1.0.0-arm64.dmg" ]; then
        SOURCE_FILE="$HOME/Downloads/FRCR Examiner-1.0.0-arm64.dmg"
        info "Found DMG in Downloads folder"
    elif [ -f "$HOME/Downloads/FRCR Examiner.app" ]; then
        SOURCE_FILE="$HOME/Downloads/FRCR Examiner.app"
        info "Found app in Downloads folder"
    else
        error "Could not find FRCR Examiner installer"
        error "Please provide the path to the DMG or ZIP file:"
        error "  bash install.sh ~/Downloads/FRCR\ Examiner-1.0.0-arm64.dmg"
        exit 1
    fi
fi

# Create temp directory
mkdir -p "$TEMP_DIR"

# Handle different file types
if [[ "$SOURCE_FILE" == *.dmg ]]; then
    info "Mounting DMG installer..."
    
    # Mount DMG
    DMG_MOUNT=$(mktemp -d)
    if ! hdiutil mount "$SOURCE_FILE" -nobrowse -mountpoint "$DMG_MOUNT" >/dev/null 2>&1; then
        error "Failed to mount DMG file"
        exit 1
    fi
    status "DMG mounted successfully"
    
    # Find the app in the mounted DMG
    if [ -d "$DMG_MOUNT/FRCR Examiner.app" ]; then
        SOURCE_APP="$DMG_MOUNT/FRCR Examiner.app"
    else
        error "Could not find ${APP_NAME} in DMG"
        exit 1
    fi
    
elif [[ "$SOURCE_FILE" == *.zip ]]; then
    info "Extracting ZIP file..."
    
    # Unzip
    if ! unzip -q "$SOURCE_FILE" -d "$TEMP_DIR"; then
        error "Failed to extract ZIP file"
        exit 1
    fi
    status "ZIP extracted successfully"
    
    # Find the app
    if [ -d "$TEMP_DIR/FRCR Examiner.app" ]; then
        SOURCE_APP="$TEMP_DIR/FRCR Examiner.app"
    else
        error "Could not find ${APP_NAME} in ZIP"
        exit 1
    fi
    
elif [[ "$SOURCE_FILE" == *.app ]]; then
    SOURCE_APP="$SOURCE_FILE"
    info "Using application directly from: $SOURCE_FILE"
else
    error "Unsupported file format. Please use .dmg or .zip"
    exit 1
fi

# Check if app exists at source
if [ ! -d "$SOURCE_APP" ]; then
    error "Application not found at: $SOURCE_APP"
    exit 1
fi

# Step 1: Remove existing installation if present
if [ -d "$APP_PATH" ]; then
    warning "Existing installation found, backing up..."
    BACKUP_PATH="/Applications/FRCR Examiner Backup.app"
    if [ -d "$BACKUP_PATH" ]; then
        rm -rf "$BACKUP_PATH"
    fi
    mv "$APP_PATH" "$BACKUP_PATH"
    status "Existing installation backed up to: $BACKUP_PATH"
fi

echo

# Step 2: Copy app to Applications folder
info "Installing ${APP_NAME} to Applications folder..."

if ! cp -r "$SOURCE_APP" "$APP_PATH"; then
    error "Failed to copy app to Applications folder"
    error "You may need to enter your password to complete installation"
    
    # Try with sudo
    if sudo cp -r "$SOURCE_APP" "$APP_PATH" 2>/dev/null; then
        status "Application installed (required admin access)"
    else
        error "Installation failed. Please ensure you have permission to write to Applications folder"
        exit 1
    fi
else
    status "Application installed to: $APP_PATH"
fi

echo

# Step 3: Remove quarantine attribute (allow app to run without security warnings)
info "Configuring security settings..."

if [ -d "$APP_PATH" ]; then
    # Try to remove quarantine attribute
    if xattr -d com.apple.quarantine "$APP_PATH" 2>/dev/null; then
        status "Security attribute removed (app will open without warnings)"
    else
        # If not quarantined, that's fine
        status "Security settings configured"
    fi
    
    # Make executable
    chmod +x "$APP_PATH/Contents/MacOS"/* 2>/dev/null || true
fi

echo

# Step 4: Create alias in Applications if needed
info "Setting up application shortcuts..."
status "Application ready to use"

echo
echo -e "${GREEN}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              Installation Complete!                             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Offer to launch the app
echo
read -p "Would you like to launch ${APP_NAME} now? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    info "Launching ${APP_NAME}..."
    open "$APP_PATH"
    status "Application launched!"
    
    echo
    info "Tip: On first launch, the app may take 5-10 seconds to fully start"
    info "The Flask server is initializing and creating the database"
else
    info "To launch ${APP_NAME}, double-click it in the Applications folder"
    info "Or run: open /Applications/FRCR\ Examiner.app"
fi

echo
echo "Installation Summary:"
echo "  Location: $APP_PATH"
echo "  Database: ~/Library/Application Support/FRCR Examiner/"
echo "  Backups: ~/Library/Application Support/FRCR Examiner/backups/"
echo

info "For help and documentation, visit:"
echo "  https://github.com/visit-www/Frcr-examiner"

echo
status "Installation finished successfully!"
