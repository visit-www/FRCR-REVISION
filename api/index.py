"""
Vercel Serverless Function Entry Point
This file handles all HTTP requests and routes them through the Flask app.

Vercel Python runtime automatically detects the 'app' variable as a WSGI application.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path so we can import app and models
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import and export Flask app for Vercel Python runtime
# The 'app' variable is detected by Vercel as the WSGI application
from app import app

# Explicit export (Vercel detects 'app' or 'application' at module level)
__all__ = ['app']
