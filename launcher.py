#!/usr/bin/env python3
"""
FRCR Examiner - Robust App Launcher
This launcher safely starts the Flask server and opens the browser
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
import logging

# Setup logging
logging.basicConfig(
    filename=str(Path.home() / "Library/Logs/FRCR-Examiner.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FRCRExaminerApp:
    def __init__(self):
        self.server_process = None
        self.app_dir = Path.home() / "Applications" / "FRCR-Examiner"
        logger.info("FRCR Examiner Launcher started")
        logger.info(f"App directory: {self.app_dir}")
        
    def ensure_app_dir(self):
        """Ensure app directory exists and is accessible"""
        try:
            if not self.app_dir.exists():
                logger.error(f"App directory does not exist: {self.app_dir}")
                print(f"Error: Application directory not found at {self.app_dir}")
                sys.exit(1)
            logger.info(f"App directory verified: {self.app_dir}")
            return True
        except Exception as e:
            logger.error(f"Error checking app directory: {e}")
            print(f"Error accessing app directory: {e}")
            sys.exit(1)
    
    def ensure_dependencies(self):
        """Install Python dependencies if needed"""
        try:
            req_file = self.app_dir / "requirements.txt"
            if req_file.exists():
                logger.info("Installing dependencies...")
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-q", "-r", str(req_file)],
                    check=False,
                    capture_output=True,
                    timeout=60
                )
                if result.returncode == 0:
                    logger.info("Dependencies installed successfully")
                else:
                    logger.warning(f"Pip returned code {result.returncode}")
            else:
                logger.warning("requirements.txt not found")
        except subprocess.TimeoutExpired:
            logger.warning("Dependency installation timed out")
        except Exception as e:
            logger.warning(f"Error installing dependencies: {e}")
    
    def start_server(self):
        """Start Flask server safely"""
        try:
            os.chdir(str(self.app_dir))
            logger.info(f"Changed to directory: {os.getcwd()}")
            
            # Check if app.py exists
            app_file = self.app_dir / "app.py"
            if not app_file.exists():
                logger.error(f"app.py not found at {app_file}")
                print(f"Error: app.py not found")
                sys.exit(1)
            
            logger.info("Starting Flask server...")
            self.server_process = subprocess.Popen(
                [sys.executable, "app.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            logger.info(f"Server process started with PID: {self.server_process.pid}")
            
        except Exception as e:
            logger.error(f"Error starting server: {e}")
            print(f"Error starting application: {e}")
            sys.exit(1)
    
    def open_browser(self):
        """Open application in default browser"""
        try:
            time.sleep(4)  # Wait for server to start
            logger.info("Opening browser to http://localhost:5000")
            webbrowser.open("http://localhost:5000")
        except Exception as e:
            logger.error(f"Error opening browser: {e}")
    
    def cleanup(self):
        """Clean up on exit"""
        try:
            if self.server_process:
                logger.info(f"Terminating server process {self.server_process.pid}")
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(self.server_process.pid), signal.SIGTERM)
                else:
                    self.server_process.terminate()
                
                try:
                    self.server_process.wait(timeout=5)
                    logger.info("Server terminated gracefully")
                except:
                    self.server_process.kill()
                    logger.info("Server killed forcefully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def monitor_server(self):
        """Monitor server and log any crashes"""
        if self.server_process:
            returncode = self.server_process.wait()
            if returncode != 0:
                stderr = self.server_process.stderr.read().decode('utf-8', errors='ignore')
                logger.error(f"Server crashed with code {returncode}")
                logger.error(f"Server stderr: {stderr}")
    
    def run(self):
        """Main run loop"""
        try:
            # Register cleanup
            atexit.register(self.cleanup)
            signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
            
            # Verify app directory
            self.ensure_app_dir()
            
            # Install dependencies
            self.ensure_dependencies()
            
            # Start server
            self.start_server()
            
            # Open browser in separate thread
            browser_thread = threading.Thread(target=self.open_browser, daemon=True)
            browser_thread.start()
            
            # Monitor server in separate thread
            monitor_thread = threading.Thread(target=self.monitor_server, daemon=True)
            monitor_thread.start()
            
            # Keep running
            logger.info("Launcher is running. Waiting for server...")
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Launcher interrupted by user")
        except Exception as e:
            logger.error(f"Unexpected error in launcher: {e}")
            print(f"Error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    try:
        app = FRCRExaminerApp()
        app.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"Fatal error: {e}")
        sys.exit(1)

