#!/bin/bash
# Startup script that runs Flask server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure venv exists
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate and run
source venv/bin/activate
pip install -q -r requirements.txt 2>/dev/null
exec python3 run.py
