#!/bin/bash

###############################################################################
# Build FRCR Examiner as Native macOS App
# Creates a native macOS application bundle without Electron
###############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="FRCR Examiner"
FLASK_EXECUTABLE="$SCRIPT_DIR/resources/flask_server/flask_server"
OUTPUT_DIR="$SCRIPT_DIR/dist"
VERSION="1.0.0"
BUNDLE_ID="com.frcr.examiner"

echo "Building $PROJECT_NAME as native macOS app..."
echo

# Create app bundle structure
APP_PATH="$OUTPUT_DIR/$PROJECT_NAME.app"
CONTENTS_DIR="$APP_PATH/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

echo "Creating app bundle structure..."
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

# Copy Flask executable
echo "Copying Flask server..."
cp "$FLASK_EXECUTABLE" "$RESOURCES_DIR/"
chmod +x "$RESOURCES_DIR/flask_server"

# Copy app resources
if [ -d "$SCRIPT_DIR/templates" ]; then
    echo "Copying templates..."
    cp -r "$SCRIPT_DIR/templates" "$RESOURCES_DIR/"
fi

if [ -d "$SCRIPT_DIR/static" ]; then
    echo "Copying static files..."
    cp -r "$SCRIPT_DIR/static" "$RESOURCES_DIR/"
fi

# Create launcher script
echo "Creating launcher script..."
cat > "$MACOS_DIR/$PROJECT_NAME" << 'LAUNCHER_EOF'
#!/bin/bash

# Get the directory where this executable is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESOURCES_DIR="$SCRIPT_DIR/../Resources"
FLASK_BIN="$RESOURCES_DIR/flask_server"

# Check if Flask is already running
if lsof -i :5000 > /dev/null 2>&1; then
    echo "Flask is already running"
else
    # Start Flask server in background
    "$FLASK_BIN" > /tmp/frcr_flask.log 2>&1 &
    sleep 2
fi

# Open in browser
open "http://localhost:5000"

# Keep the script running
wait
LAUNCHER_EOF

chmod +x "$MACOS_DIR/$PROJECT_NAME"

# Create Info.plist
echo "Creating Info.plist..."
cat > "$CONTENTS_DIR/Info.plist" << 'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>FRCR Examiner</string>
    <key>CFBundleIdentifier</key>
    <string>com.frcr.examiner</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>FRCR Examiner</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSHumanReadableCopyright</key>
    <string>FRCR Examiner</string>
</dict>
</plist>
PLIST_EOF

echo
echo "✓ App bundle created successfully!"
echo
echo "Location: $APP_PATH"
echo

# Test the app
echo "Opening app..."
open "$APP_PATH"

echo "Done!"
