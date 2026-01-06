#!/bin/bash
# Start FRCR Examiner backend server

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create venv if needed
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
fi

# Activate venv
source "$SCRIPT_DIR/venv/bin/activate"

# Install/update dependencies
echo "Installing dependencies..."
pip install -q -r "$SCRIPT_DIR/requirements.txt"

# Run the app
cd "$SCRIPT_DIR"
python3 run.py
