#!/bin/bash

###############################################################################
# FRCR Examiner - macOS Installer & Launcher
# This script sets up and runs FRCR Examiner with minimal user interaction
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/.venv"
DATABASE="$SCRIPT_DIR/frcr_examiner.db"
PORT=5000
HOST="127.0.0.1"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  FRCR Examiner - Medical Exam Management System${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# Check Python version
echo -e "\n${YELLOW}Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 is not installed.${NC}"
    echo "Please install Python 3.9+ from https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✓ Python ${PYTHON_VERSION} found${NC}"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo -e "\n${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "\n${YELLOW}Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Install dependencies
echo -e "\n${YELLOW}Installing dependencies...${NC}"
pip install --upgrade pip setuptools wheel -q
pip install -r "$SCRIPT_DIR/requirements.txt" -q
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Initialize database if needed
if [ ! -f "$DATABASE" ]; then
    echo -e "\n${YELLOW}Initializing database...${NC}"
    python3 << 'EOF'
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from app import app, db
with app.app_context():
    db.create_all()
    print("✓ Database initialized")
EOF
fi

# Launch Flask app
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Starting FRCR Examiner...${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "\n${YELLOW}Opening in browser: ${BLUE}http://${HOST}:${PORT}${NC}"
echo -e "${YELLOW}Press ${BLUE}Ctrl+C${YELLOW} to stop the server${NC}\n"

# Open browser (macOS specific)
sleep 2 && open "http://${HOST}:${PORT}" &

# Run Flask
cd "$SCRIPT_DIR"
python3 app.py
