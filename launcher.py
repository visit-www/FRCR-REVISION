#!/usr/bin/env python3
"""
FRCR Examiner - macOS App Launcher
This creates a standalone .app bundle that runs the Flask server
"""

import sys
import os
import subprocess
import webbrowser
import time
import signal
import atexit
from pathlib import Path
import threading

class FRCRExaminerApp:
    def __init__(self):
        self.server_process = None
        self.app_dir = Path.home() / "Applications" / "FRCR-Examiner"
        
    def ensure_dependencies(self):
        """Install Python dependencies if needed"""
        req_file = self.app_dir / "requirements.txt"
        if req_file.exists():
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-q", "-r", str(req_file)],
                    check=False,
                    capture_output=True
                )
            except:
                pass
    
    def start_server(self):
        """Start Flask server"""
        try:
            os.chdir(str(self.app_dir))
            self.server_process = subprocess.Popen(
                [sys.executable, "app.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except Exception as e:
            print(f"Error starting server: {e}")
    
    def open_browser(self):
        """Open application in default browser"""
        time.sleep(3)  # Wait for server to start
        webbrowser.open("http://localhost:5000")
    
    def cleanup(self):
        """Clean up on exit"""
        if self.server_process:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except:
                self.server_process.kill()
    
    def run(self):
        """Main run loop"""
        # Register cleanup
        atexit.register(self.cleanup)
        signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
        
        # Install dependencies
        self.ensure_dependencies()
        
        # Start server
        self.start_server()
        
        # Open browser in separate thread
        browser_thread = threading.Thread(target=self.open_browser)
        browser_thread.daemon = True
        browser_thread.start()
        
        # Keep running
        try:
            if self.server_process:
                self.server_process.wait()
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    app = FRCRExaminerApp()
    app.run()
