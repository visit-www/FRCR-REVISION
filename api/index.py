"""
Vercel Serverless Function Entry Point
This file handles all HTTP requests and routes them through the Flask app
"""
import os
import sys
from pathlib import Path

# Add parent directory to path so we can import app and models
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app import app

# IMPORTANT: For Vercel, we need to export the Flask app as 'app'
# This is the handler that Vercel's Python runtime will call
