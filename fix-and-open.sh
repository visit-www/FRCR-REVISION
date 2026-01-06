#!/bin/bash
# Comprehensive fix script for macOS Gatekeeper
# This script removes quarantine and opens the app

APP_NAME="FRCR Examiner.app"
APP_PATH="/Applications/${APP_NAME}"

echo "🔓 Fixing macOS Gatekeeper for ${APP_NAME}"
echo "=========================================="

# Check if app exists
if [ ! -d "$APP_PATH" ]; then
    echo "❌ Error: ${APP_NAME} not found in /Applications"
    echo ""
    echo "Please:"
    echo "1. Download the DMG from GitHub releases"
    echo "2. Open the DMG"
    echo "3. Drag the app to Applications"
    echo "4. Run this script again"
    exit 1
fi

# Remove all quarantine attributes
echo "Step 1: Removing quarantine attributes..."
sudo xattr -rd com.apple.quarantine "$APP_PATH" 2>/dev/null
xattr -rd com.apple.quarantine "$APP_PATH" 2>/dev/null

# Remove other security attributes
echo "Step 2: Removing security attributes..."
sudo xattr -rc "$APP_PATH" 2>/dev/null
xattr -rc "$APP_PATH" 2>/dev/null

# Fix permissions
echo "Step 3: Fixing permissions..."
sudo chmod -R 755 "$APP_PATH"

# Verify the fix
if xattr -l "$APP_PATH" 2>/dev/null | grep -q "com.apple.quarantine"; then
    echo "⚠️  Warning: Quarantine attribute still present"
    echo "Trying alternative method..."
    
    # Alternative: Use spctl to add exception (requires user interaction)
    echo ""
    echo "Please approve the app in System Settings:"
    echo "1. Go to System Settings > Privacy & Security"
    echo "2. Look for a message about ${APP_NAME}"
    echo "3. Click 'Open Anyway' or 'Allow'"
else
    echo "✅ Quarantine removed successfully!"
fi

# Try to open the app
echo ""
echo "Step 4: Opening the app..."
if [ -d "$APP_PATH" ]; then
    open "$APP_PATH"
    echo "✅ App launch attempted!"
    echo ""
    echo "If the app still doesn't open:"
    echo "1. Right-click the app in Applications"
    echo "2. Select 'Open'"
    echo "3. Click 'Open' in the security dialog"
else
    echo "❌ App not found at $APP_PATH"
fi

echo ""
echo "Done! The app should now work."

