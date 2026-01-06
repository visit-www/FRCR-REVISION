#!/bin/bash

###############################################################################
# Build FRCR Examiner with Platypus
# Creates a native macOS application using Platypus
###############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="FRCR Examiner"
LAUNCHER_SCRIPT="$SCRIPT_DIR/macos_launcher.sh"
FLASK_EXECUTABLE="$SCRIPT_DIR/resources/flask_server/flask_server"
OUTPUT_DIR="$SCRIPT_DIR/dist-platypus"
APP_NAME="FRCR Examiner"

echo "Building $PROJECT_NAME with Platypus..."
echo

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check for required files
if [ ! -f "$LAUNCHER_SCRIPT" ]; then
    echo "Error: Launcher script not found at $LAUNCHER_SCRIPT"
    exit 1
fi

if [ ! -f "$FLASK_EXECUTABLE" ]; then
    echo "Error: Flask executable not found at $FLASK_EXECUTABLE"
    echo "Please run: npm run build-standalone-flask"
    exit 1
fi

# Build the app with Platypus
echo "Creating Platypus application..."

platypus \
    --name "$APP_NAME" \
    --interface "Progress Bar" \
    --background \
    --quit-message "Quit FRCR Examiner?" \
    --app-icon "$SCRIPT_DIR/icon.icns" \
    --bundle-identifier "com.frcr.examiner" \
    --author "Your Name" \
    --help "FRCR Examiner - Professional Radiology Exam Management" \
    --declare-uti "com.frcr.examiner.data" \
    --version "1.0.0" \
    --load-segments \
    --keep-open \
    "$LAUNCHER_SCRIPT" \
    "$OUTPUT_DIR/$APP_NAME.app"

# Copy Flask executable to app resources
mkdir -p "$OUTPUT_DIR/$APP_NAME.app/Contents/Resources"
cp "$FLASK_EXECUTABLE" "$OUTPUT_DIR/$APP_NAME.app/Contents/Resources/"
chmod +x "$OUTPUT_DIR/$APP_NAME.app/Contents/Resources/flask_server"

# Copy other resources if needed
if [ -d "$SCRIPT_DIR/templates" ]; then
    cp -r "$SCRIPT_DIR/templates" "$OUTPUT_DIR/$APP_NAME.app/Contents/Resources/"
fi

if [ -d "$SCRIPT_DIR/static" ]; then
    cp -r "$SCRIPT_DIR/static" "$OUTPUT_DIR/$APP_NAME.app/Contents/Resources/"
fi

echo
echo "✓ Platypus app created successfully!"
echo
echo "Location: $OUTPUT_DIR/$APP_NAME.app"
echo

# Test the app
echo "Testing app..."
open "$OUTPUT_DIR/$APP_NAME.app"

echo "Done!"
