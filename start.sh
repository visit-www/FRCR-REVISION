#!/bin/bash
# FRCR Examiner - Start Server (macOS/Linux)

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  FRCR Examiner - Local Server"
echo "=========================================="
echo ""

# Create venv if needed
if [ ! -d "venv" ]; then
    echo "Creating Python environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Run server
echo ""
echo "Starting server..."
echo "Access at: http://localhost:5000"
echo "Press Ctrl+C to stop"
echo ""

python3 app.py
