#!/usr/bin/env python3
"""FRCR Examiner - Web App Launcher"""
from app import app

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  FRCR Examiner is running at http://localhost:5000")
    print("="*60 + "\n")
    app.run(host='127.0.0.1', port=5000, debug=False)
