# 🍎 macOS Installation Guide

## Installing FRCR Examiner on macOS

### Step 1: Download the App

1. Go to the [Releases page](https://github.com/visit-www/Frcr-examiner/releases)
2. Download `FRCR Examiner-1.0.0-arm64.dmg`

### Step 2: Open the DMG

1. Double-click the downloaded DMG file
2. A window will open showing the FRCR Examiner app

### Step 3: Install the App

1. **Drag** `FRCR Examiner.app` to the `Applications` folder in the DMG window
2. Wait for the copy to complete

### Step 4: Handle macOS Security (Gatekeeper)

Since this app is not code-signed by Apple, macOS will block it from opening. Here are **three ways** to fix this:

#### Option 1: Right-Click Method (Easiest) ⭐ Recommended

1. Open **Finder** and go to **Applications**
2. **Right-click** (or Control+Click) on `FRCR Examiner.app`
3. Select **"Open"** from the context menu
4. Click **"Open"** in the security dialog that appears
5. The app will launch and be trusted for future use

#### Option 2: Terminal Command (Quick Fix)

1. Open **Terminal** (Applications > Utilities > Terminal)
2. Run this command:
   ```bash
   sudo xattr -rd com.apple.quarantine "/Applications/FRCR Examiner.app"
   ```
3. Enter your password when prompted
4. Now you can open the app normally

#### Option 3: System Settings (One-Time)

1. Go to **System Settings** > **Privacy & Security**
2. Scroll down to the **Security** section
3. If you see a message about "FRCR Examiner was blocked", click **"Open Anyway"**
4. Confirm by clicking **"Open"**

### Step 5: Launch the App

After completing one of the methods above:
1. Open **Applications** folder
2. Double-click **FRCR Examiner**
3. The app should launch successfully!

## Why Does This Happen?

macOS Gatekeeper protects your Mac by blocking apps from unidentified developers. Since this app is distributed outside the Mac App Store and isn't code-signed with an Apple Developer certificate, macOS adds a "quarantine" attribute to it.

**This is normal and safe** - the app is not malicious, it's just not signed by Apple.

## Troubleshooting

### "App is damaged and can't be opened"

This usually means the quarantine attribute wasn't removed properly. Try:

```bash
sudo xattr -rd com.apple.quarantine "/Applications/FRCR Examiner.app"
sudo chmod -R 755 "/Applications/FRCR Examiner.app"
```

### App won't launch after removing quarantine

1. Check if Python is bundled (it should be)
2. Try opening from Terminal to see error messages:
   ```bash
   "/Applications/FRCR Examiner.app/Contents/MacOS/FRCR Examiner"
   ```
3. Check Console.app for error logs

### Still having issues?

1. Make sure you're on macOS 10.12 or later
2. Check that you have enough disk space
3. Try reinstalling the app
4. Open an issue on GitHub with error details

## Security Note

This app is **open source** and you can review the code on GitHub. The app:
- ✅ Runs entirely on your local machine
- ✅ Doesn't require internet connection
- ✅ Doesn't collect or transmit any data
- ✅ All data is stored locally in your `instance` folder

## Future Updates

For future versions, you'll need to repeat the Gatekeeper fix (Option 1 or 2) after updating. This is a one-time process per installation.

