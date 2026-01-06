# FRCR Examiner - Professional Installer Guide

## What is the Professional Installer?

The **FRCR-Examiner-Installer-1.0.0.dmg** is a professional, automated installer that handles all setup for colleagues automatically. No technical knowledge required!

## Installer Contents

The DMG file contains:
- ✅ FRCR Examiner application (full bundled version)
- ✅ Automatic installation script (`install.sh`)
- ✅ One-click installer (`.command` file for non-technical users)
- ✅ Setup instructions and documentation

## Installation Methods

### Method 1: One-Click Installation (Easiest - No Terminal)

**Perfect for non-technical colleagues:**

1. Download `FRCR-Examiner-Installer-1.0.0.dmg`
2. Double-click to mount the DMG
3. **Double-click the file named "Install FRCR Examiner.command"**
4. Wait for the installer to complete (2-3 minutes)
5. The app automatically opens after installation
6. Done! ✨

**What happens automatically:**
- App is copied to Applications folder
- Security settings are configured
- No Gatekeeper warnings
- App launches ready to use

### Method 2: Terminal Installation (Technical users)

For users comfortable with Terminal:

```bash
# 1. Mount the DMG (double-click it)
# 2. Open Terminal
# 3. Drag the mounted folder into Terminal
# 4. Type: cd [folder path that appeared]
# 5. Type: bash install.sh
# 6. Press Enter
# 7. Follow prompts
```

Or in one command (if the DMG is mounted):
```bash
bash /Volumes/FRCR\ Examiner\ Installer/install.sh
```

### Method 3: Manual Installation (Last Resort)

1. Mount the DMG
2. Extract the app DMG inside
3. Double-click the extracted app DMG
4. Drag the app to Applications folder
5. Run normally

## Installation Script Features

The automatic `install.sh` script:

✅ **Detects installation file format** (DMG or ZIP)
✅ **Removes existing installation** (with backup)
✅ **Copies app to /Applications** (with sudo if needed)
✅ **Removes quarantine attribute** (no security warnings)
✅ **Configures app permissions** (makes it executable)
✅ **Offers to launch app** after installation
✅ **Displays colored status messages** (professional feedback)
✅ **Handles errors gracefully** (with helpful messages)

## What Colleagues See

### One-Click Installation Progress:
```
✓ Installing FRCR Examiner...
✓ Copying application files
✓ Configuring security settings
✓ Removing security warnings
✓ Application installed to: /Applications/FRCR Examiner.app

Would you like to launch FRCR Examiner now? (y/n) _
```

### After Installation:
- App is in Applications folder
- No configuration needed
- Ready to use immediately
- No technical skills required

## Distribution Instructions

### Share With Colleagues:

**For non-technical users:**
```
Hi! Please install FRCR Examiner using this simple process:

1. Download: FRCR-Examiner-Installer-1.0.0.dmg
2. Double-click the DMG
3. Double-click "Install FRCR Examiner.command"
4. Wait for completion
5. Done! The app will open automatically

That's it! No other steps needed.
```

**For technical users:**
```
Installation options:
1. One-click: Double-click "Install FRCR Examiner.command"
2. Terminal: bash install.sh
3. Manual: Follow the README.txt inside the DMG
```

## Troubleshooting

### "Permission denied" when running .command file

This is normal! The system is protecting the file. Solution:

1. Right-click the "Install FRCR Examiner.command" file
2. Select "Open"
3. Click "Open" in the security dialog
4. The installer will run
5. This only happens once

### Installation seems stuck

Wait! The installer is:
- Copying files (can take 1-2 minutes)
- Configuring security settings
- Setting up the app

Just be patient - it will complete.

### App doesn't launch after installation

The Flask server takes 5-10 seconds to start on first launch. Be patient and it will appear.

## Building the Installer

### For Developers:

To create a new installer after updates:

```bash
# 1. Build the app
npm run build-mac

# 2. Build the installer DMG
npm run build-installer

# Or do both in one command
npm run release
```

The installer will be created at: `dist/FRCR-Examiner-Installer-1.0.0.dmg`

### Publishing the Installer:

1. Create a GitHub Release
2. Upload the installer DMG
3. Share the release link with colleagues
4. Include the simple installation instructions above

## Technical Details

### Files Included in DMG:

```
FRCR Examiner Installer/
├── Install FRCR Examiner.command    ← One-click installer
├── install.sh                       ← Bash script (for Terminal)
├── README.txt                       ← Instructions
├── FRCR Examiner-1.0.0-arm64.dmg   ← The actual app
```

### What the Script Does:

1. **Detects file type** (DMG, ZIP, or .app)
2. **Mounts/extracts** the installer files
3. **Backs up existing** installation (if present)
4. **Copies app** to `/Applications`
5. **Removes quarantine** attribute (`com.apple.quarantine`)
6. **Sets permissions** (makes executable)
7. **Offers to launch** the app
8. **Cleans up** temporary files

### System Requirements:

- macOS 10.12 or later
- ~500 MB free space
- Write access to `/Applications` folder
- No admin account needed for new installations
- May need password for sudo (existing installation replacement)

## Installation Statistics

### File Sizes:
- **Installer DMG:** ~108 MB
- **Installed Size:** ~300-400 MB (fully unpacked)

### Installation Time:
- **One-click:** 2-3 minutes
- **Terminal:** 1-2 minutes
- **Manual:** 5 minutes

### First Launch:
- **App startup:** 5-10 seconds
- **Database creation:** Automatic
- **Ready to use:** Immediately after launch

## Security

### What the Script Does:
- ✅ Removes quarantine attribute (allows launch without warnings)
- ✅ Sets executable permissions
- ✅ Validates installation files
- ✅ Creates safe backups of existing installations
- ✅ No admin required for initial installation

### What the Script Does NOT Do:
- ✅ Does NOT require Apple Developer subscription
- ✅ Does NOT modify system files (only /Applications)
- ✅ Does NOT require code signing
- ✅ Does NOT call home or phone home
- ✅ Does NOT collect any telemetry

## Advanced Usage

### Silent Installation (No Prompts):

```bash
bash install.sh "~/Downloads/FRCR Examiner-1.0.0-arm64.dmg" < /dev/null
```

### Batch Installation (Multiple Machines):

Create a script that installs for all users:

```bash
#!/bin/bash
for user in $(dscl . list /Users | grep -v '^_'); do
    sudo -u $user bash install.sh
done
```

### Uninstallation:

```bash
rm -rf /Applications/FRCR\ Examiner.app
rm -rf ~/Library/Application\ Support/FRCR\ Examiner
```

## Support

For installation issues:
1. Check the troubleshooting section above
2. Run the Terminal method: `bash install.sh`
3. Report issues with the full terminal output at: https://github.com/visit-www/Frcr-examiner/issues

## License

The installer script is MIT licensed, same as the application.

---

**Questions?** See the full documentation at: https://github.com/visit-www/Frcr-examiner
