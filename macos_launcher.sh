#!/bin/bash

###############################################################################
# FRCR Examiner - macOS Launcher Script for Platypus
# 
# This script launches the Flask server and opens the app in the default browser
###############################################################################

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR"

# Try to find the bundled Flask executable
if [ -f "$APP_DIR/Contents/Resources/flask_server" ]; then
    FLASK_BIN="$APP_DIR/Contents/Resources/flask_server"
elif [ -f "$APP_DIR/flask_server" ]; then
    FLASK_BIN="$APP_DIR/flask_server"
else
    echo "Error: Flask executable not found"
    exit 1
fi

# Check if Flask is already running
if lsof -i :5000 > /dev/null 2>&1; then
    echo "Flask is already running on port 5000"
else
    echo "Starting Flask server..."
    # Run Flask server in background
    "$FLASK_BIN" > /tmp/frcr_flask.log 2>&1 &
    FLASK_PID=$!
    
    # Wait for Flask to start
    sleep 2
fi

# Open the app in default browser
echo "Opening FRCR Examiner in browser..."
open "http://localhost:5000"

# Keep this script running to maintain the Flask process
echo "FRCR Examiner is running"
echo "Close this window to stop the app"

# Wait indefinitely
wait
