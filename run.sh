#!/bin/bash

# FRCR Examiner - Quick Start Script for macOS

echo "=========================================="
echo "FRCR Examiner - Starting Application"
echo "=========================================="
echo ""

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

echo ""
echo "=========================================="
echo "Application ready!"
echo "Starting Flask server..."
echo "=========================================="
echo ""
echo "Open your browser and go to: http://localhost:5000"
echo "Press Ctrl+C to stop the server"
echo ""

# Run the application
python app.py
