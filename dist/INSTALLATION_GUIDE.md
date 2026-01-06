# FRCR Examiner Tool - Installation Guide

## Overview
Welcome to the FRCR Examiner Tool! This guide will help you install and set up the application on your computer.

## System Requirements

### Windows
- **Operating System**: Windows 10 or later
- **Python**: Version 3.8 or higher
- **RAM**: 4GB minimum (8GB recommended)
- **Storage**: 500MB free space
- **Browser**: Chrome, Firefox, Edge, or Safari

### macOS
- **Operating System**: macOS 10.14 (Mojave) or later
- **Python**: Version 3.8 or higher
- **RAM**: 4GB minimum (8GB recommended)
- **Storage**: 500MB free space
- **Browser**: Chrome, Firefox, or Safari

---

## Installation Instructions

### Windows Installation

1. **Download the Package**
   - Download `FRCR-Examiner-Windows.zip` from the GitHub releases page
   - Extract the ZIP file to a temporary location

2. **Install Python (if not already installed)**
   - Download Python from https://www.python.org/downloads/
   - **IMPORTANT**: During installation, check "Add Python to PATH"
   - Verify installation by opening Command Prompt and typing: `python --version`

3. **Run the Installer**
   - Navigate to the extracted folder
   - Find `dist/windows` folder
   - **Right-click** on `install.bat` and select **"Run as administrator"**
   - Follow the on-screen instructions

4. **Launch the Application**
   - After installation, you'll find "FRCR Examiner" icon on your Desktop
   - Double-click the icon to launch the application
   - The app will open in your default web browser at `http://127.0.0.1:5000`

### macOS Installation

1. **Download the Package**
   - Download `FRCR-Examiner-macOS.zip` from the GitHub releases page
   - Extract the ZIP file (double-click in Finder)

2. **Install Python (if not already installed)**
   - Download Python from https://www.python.org/downloads/
   - Or install using Homebrew: `brew install python@3.11`
   - Verify installation by opening Terminal and typing: `python3 --version`

3. **Run the Installer**
   - Open Terminal
   - Navigate to the extracted folder: `cd ~/Downloads/FRCR-Examiner-macOS`
   - Run: `cd dist/macos && ./install.sh`
   - Follow the on-screen instructions

4. **Handle macOS Security Warning**
   
   When you first try to open the app, macOS will block it because it's not from the App Store.
   
   **Method 1: Using System Preferences**
   - Try to open "FRCR Examiner" from Applications
   - macOS will show a warning
   - Go to **System Preferences > Security & Privacy**
   - Click **"Open Anyway"** button
   - Confirm by clicking **"Open"** in the dialog
   
   **Method 2: Using Right-Click**
   - Right-click (or Control+click) on "FRCR Examiner" app
   - Select **"Open"** from the menu
   - Click **"Open"** in the security dialog
   
   **You only need to do this once!** After the first time, you can open the app normally.

5. **Launch the Application**
   - Open "FRCR Examiner" from your Applications folder
   - The app will open in your default web browser at `http://127.0.0.1:5000`

---

## Where is My Data Stored?

All your data is stored **locally on your computer** for privacy and security.

### Windows
```
C:\Users\YourUsername\FRCR_Examiner\instance\
```

### macOS
```
/Users/YourUsername/Applications/FRCR_Examiner/instance/
```

Your database file is: `frcr_examiner.db`

---

## Using the Application

1. **First Time Setup**
   - When you first open the app, you'll see the home page
   - Click on "Prepare for Exam" to create your first exam session

2. **Creating Exam Sessions**
   - Navigate to "Manage Sessions"
   - Set up exam date, time, and details
   - Add packets and cases
   - Register candidates

3. **Starting an Exam**
   - Go to "Start Exam"
   - Select the exam session
   - Choose a candidate
   - Begin the examination

4. **Admin Dashboard**
   - Access backup and restore features
   - View system information
   - Manage database

---

## Troubleshooting

### Application Won't Start

**Windows:**
- Ensure Python is installed and in PATH
- Try running as administrator
- Check antivirus isn't blocking the app

**macOS:**
- Verify Python 3 is installed: `python3 --version`
- Check you've allowed the app in Security & Privacy settings
- View logs at: `~/Library/Logs/FRCR_Examiner.log`

### Browser Doesn't Open

- Manually open your browser
- Navigate to: `http://127.0.0.1:5000`
- Bookmark this address for easy access

### Port Already in Use

If port 5000 is already in use:
- Close other applications using port 5000
- Or edit `app.py` to use a different port

### Database Issues

- Backups are stored in the `backups/` folder
- Use the Admin Dashboard to restore from a backup
- Or manually copy your database file

---

## Updating the Application

1. **Backup Your Data**
   - Use the Admin Dashboard to create a backup
   - Or manually copy your `instance/` folder

2. **Download New Version**
   - Download the latest release from GitHub
   - Run the installer again
   - Your data will be preserved

---

## Uninstalling

### Windows
1. Delete the installation folder: `C:\Users\YourUsername\FRCR_Examiner`
2. Delete the desktop shortcut
3. Delete Start Menu entry

### macOS
1. Delete the app from Applications folder
2. Delete the installation folder: `~/Applications/FRCR_Examiner`

**Note:** Your data will be removed. Create a backup first if you want to keep it!

---

## Support

**Developer:** Dr Gaurav S.P Gupta, MBBS, MD, FRCR  
**Email:** lotusheart2016@gmail.com  
**GitHub:** https://github.com/visit-www/Frcr-examiner

For issues, please create a GitHub issue or contact via email.

---

## License

© 2026 FRCR Examiner Tool. All rights reserved.
