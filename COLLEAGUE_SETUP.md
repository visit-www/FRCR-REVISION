# FRCR Examiner - Setup Guide for Colleagues

## Quick Start (No Technical Knowledge Required)

The FRCR Examiner app is now fully self-contained and **does NOT require Python, Node.js, or any other software installation**. Just download and run!

### Installation Steps

#### Option 1: Using DMG Installer (Recommended)
1. Download `FRCR Examiner-1.0.0-arm64.dmg` from the [Release Page](https://github.com/visit-www/Frcr-examiner/releases)
2. Double-click the DMG file to mount it
3. Drag the **FRCR Examiner** icon to the **Applications** folder
4. Open **Applications** folder in Finder
5. Double-click **FRCR Examiner** to launch

#### Option 2: Using ZIP Archive
1. Download `FRCR Examiner-1.0.0-arm64-mac.zip` from the [Release Page](https://github.com/visit-www/Frcr-examiner/releases)
2. Unzip the file (double-click)
3. Drag **FRCR Examiner.app** to **Applications** folder (or anywhere you prefer)
4. Double-click to launch

### Troubleshooting

#### "The app can't be opened because Apple cannot check it for malicious software"

**Option 1: One-Time Approval (Easiest)**
1. Right-click the **FRCR Examiner** app in Applications
2. Select **Open** from the context menu
3. Click **Open** in the security dialog
4. The app will launch and remember your choice for all future launches
5. Done! You won't see this message again

**Option 2: Permanent Fix via Terminal (Technical Users)**

If you prefer, copy and paste this command in Terminal to permanently remove the security warning:

```bash
sudo xattr -rd com.apple.quarantine "/Applications/FRCR Examiner.app"
```

**Steps:**
1. Open Terminal (Applications → Utilities → Terminal)
2. Copy the command above (press Cmd+C)
3. Paste it in Terminal (press Cmd+V)
4. Press Enter
5. Enter your Mac password when prompted (it won't show as you type)
6. Press Enter
7. Close Terminal

After this, the app will open normally without any security warnings.

*No Apple Developer subscription needed!*

#### App takes a while to start on first launch
This is normal! The app is:
- Starting the embedded Flask server
- Creating the local database
- Initializing backup system

Just wait a moment and the interface will appear.

#### Port already in use (localhost:5000)
If another application is using port 5000:
1. Close that application first
2. Then launch FRCR Examiner

## What's Included

✅ **Everything bundled in one app:**
- Electron 27 desktop framework
- Flask web server (Python)
- SQLite database
- All required Python libraries
- Templates and static files
- Backup/restore functionality

✅ **No dependencies required:**
- No Python installation
- No Node.js installation
- No database server
- Everything is self-contained

## System Requirements

- **OS:** macOS 10.12 or later
- **Processor:** Apple Silicon (M1, M2, M3) or Intel Mac (with Rosetta 2)
- **Memory:** 2GB RAM minimum
- **Disk Space:** ~500 MB free space
- **Port:** 5000 (must be available)

## Usage

### Starting the App
Simply double-click the **FRCR Examiner** app in Applications

### Database
- Local SQLite database stored in: `~/Library/Application Support/FRCR Examiner/`
- Automatic daily backups created in `backups/` folder
- No cloud sync required (completely local)

### Data Location
- **Database files:** `~/Library/Application Support/FRCR Examiner/instance/`
- **Backups:** `~/Library/Application Support/FRCR Examiner/backups/`

All data is stored locally on your computer. No network connection required after app launch.

## Features

- 📋 Manage exam cases
- 👥 Setup candidates
- 📅 Organize exam sessions  
- 💾 Automatic database backups
- 📊 Dashboard and analytics
- 🔄 Restore from backups

## Updating the App

When a new version is released:
1. Download the new DMG file from the Release page
2. Repeat the installation steps above
3. The new version will replace the old one

Your database and settings will be preserved!

## Getting Help

If you encounter issues:
1. Check the troubleshooting section above
2. Try restarting the app
3. Check that port 5000 is not in use by another app
4. Contact the development team with the error message

## Technical Details (For IT/Admin)

### Installation via Script
System administrators can automate installation:

```bash
# Download and mount DMG
curl -L https://github.com/visit-www/Frcr-examiner/releases/download/v1.0.0/FRCR\ Examiner-1.0.0-arm64.dmg -o /tmp/FRCR.dmg
hdiutil mount /tmp/FRCR.dmg

# Copy to Applications
cp -r /Volumes/FRCR\ Examiner/FRCR\ Examiner.app /Applications/

# Unmount
hdiutil unmount /Volumes/FRCR\ Examiner
```

### Architecture
- **Frontend:** Electron + HTML/CSS/JavaScript
- **Backend:** Flask (Python) - runs locally
- **Database:** SQLite - local file storage
- **Port:** 5000 (localhost only)
- **Network:** None required (fully local)

### App Signing
- The app is not signed by an Apple Developer certificate (not required for local use)
- First launch requires user approval via Gatekeeper
- This is normal for open-source or independent applications

## License

MIT License - See LICENSE file in repository

## Support & Issues

Report issues on the GitHub repository:
https://github.com/visit-www/Frcr-examiner/issues
