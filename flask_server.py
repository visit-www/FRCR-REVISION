#!/usr/bin/env python3
"""
Flask Server Entry Point for PyInstaller
This is a standalone entry point that can be bundled with PyInstaller
"""
import sys
import os

# Handle paths for both bundled and development modes
if getattr(sys, 'frozen', False):
    # Running as a bundled executable (PyInstaller)
    # sys._MEIPASS is the temp folder where PyInstaller extracts files
    base_path = sys._MEIPASS
    # Get the directory where the executable is located
    app_dir = os.path.dirname(sys.executable)
    # For bundled app, instance folder should be in the app directory, not temp
    instance_path = os.path.join(app_dir, 'instance')
else:
    # Running as a normal Python script (development)
    base_path = os.path.dirname(os.path.abspath(__file__))
    app_dir = base_path
    instance_path = os.path.join(app_dir, 'instance')

# Add app directory to path so imports work
sys.path.insert(0, base_path)

# Set instance path for Flask
os.environ['INSTANCE_PATH'] = instance_path
os.makedirs(instance_path, exist_ok=True)

# Now import and run Flask app
from app import app

# Update Flask instance path if needed
if getattr(sys, 'frozen', False):
    app.instance_path = instance_path

if __name__ == '__main__':
    # Run Flask on localhost:5000
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

