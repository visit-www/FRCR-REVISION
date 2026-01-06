#!/bin/bash
# Script to fix macOS Gatekeeper issue for unsigned apps
# This removes the quarantine attribute that macOS adds to downloaded apps

APP_NAME="FRCR Examiner.app"
APP_PATH="/Applications/${APP_NAME}"

echo "🔓 Fixing macOS Gatekeeper for ${APP_NAME}"
echo "=========================================="

# Check if app exists in Applications
if [ ! -d "$APP_PATH" ]; then
    echo "❌ Error: ${APP_NAME} not found in /Applications"
    echo "Please install the app first by dragging it from the DMG to Applications"
    exit 1
fi

# Remove quarantine attribute
echo "Removing quarantine attribute..."
sudo xattr -rd com.apple.quarantine "$APP_PATH"

if [ $? -eq 0 ]; then
    echo "✅ Success! The app should now open without Gatekeeper warnings."
    echo ""
    echo "You can now:"
    echo "1. Open the app normally from Applications"
    echo "2. Or right-click and select 'Open' if you still see a warning"
else
    echo "❌ Failed to remove quarantine attribute. You may need to:"
    echo "1. Right-click the app and select 'Open'"
    echo "2. Click 'Open' in the security dialog"
    echo "3. The app will be trusted for future launches"
fi

