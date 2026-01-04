"""
FRCR EXAMINER - Desktop App Launcher
This creates a proper desktop application with a native window
"""

import os
import sys
import webbrowser
import threading
import time
from app import app

def open_browser():
    """Open browser after Flask server starts"""
    time.sleep(2)  # Wait for server to start
    webbrowser.open('http://localhost:5000')

def run_app():
    """Run the Flask application"""
    # Run in main thread
    app.run(debug=False, host='localhost', port=5000, use_reloader=False)

if __name__ == '__main__':
    print("═" * 60)
    print("🏥 FRCR EXAMINER - Desktop Application")
    print("═" * 60)
    print("")
    print("Starting application...")
    print("Opening browser window...")
    print("")
    
    # Start browser in separate thread
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # Run Flask app
    run_app()
