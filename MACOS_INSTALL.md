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

### Step 4: Handle macOS Security (Gatekeeper) ⚠️ CRITICAL

**macOS WILL block this app** because it's not code-signed. You MUST complete this step before the app will work.

#### Option 1: Right-Click Method (Easiest) ⭐ RECOMMENDED

**This is the most reliable method:**

1. Open **Finder** and navigate to **Applications** folder
2. **Find** `FRCR Examiner.app`
3. **RIGHT-CLICK** (or Control+Click) on the app icon
4. Select **"Open"** from the context menu (NOT double-click!)
5. A security dialog will appear saying the app is from an unidentified developer
6. Click **"Open"** in the dialog
7. The app will launch and be trusted for all future launches

**Important**: You MUST use right-click → Open the FIRST time. Double-clicking won't work!

#### Option 2: Terminal Command (If Option 1 Doesn't Work)

If the right-click method doesn't work, use Terminal:

1. Open **Terminal** (Applications > Utilities > Terminal, or press Cmd+Space and type "Terminal")
2. Copy and paste this EXACT command:
   ```bash
   sudo xattr -rd com.apple.quarantine "/Applications/FRCR Examiner.app"
   ```
3. Press **Enter**
4. Enter your **Mac password** (you won't see it as you type - this is normal)
5. Press **Enter** again
6. Now try opening the app normally

#### Option 3: Use the Fix Script

1. Download `fix-and-open.sh` from the GitHub release
2. Open Terminal
3. Navigate to Downloads:
   ```bash
   cd ~/Downloads
   ```
4. Make it executable:
   ```bash
   chmod +x fix-and-open.sh
   ```
5. Run it:
   ```bash
   ./fix-and-open.sh
   ```
6. Enter your password when prompted

#### Option 4: System Settings (Last Resort)

1. Go to **System Settings** (or System Preferences on older macOS)
2. Click **Privacy & Security**
3. Scroll down to the **Security** section
4. Look for a message about "FRCR Examiner was blocked" or "FRCR Examiner.app cannot be opened"
5. Click **"Open Anyway"** or **"Allow"**
6. Confirm by clicking **"Open"** in the dialog

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

**This is a Gatekeeper issue, not actual damage.** Try these steps in order:

1. **Remove quarantine (try multiple methods):**
   ```bash
   sudo xattr -rd com.apple.quarantine "/Applications/FRCR Examiner.app"
   sudo xattr -rc "/Applications/FRCR Examiner.app"
   ```

2. **Fix permissions:**
   ```bash
   sudo chmod -R 755 "/Applications/FRCR Examiner.app"
   ```

3. **Right-click and Open** (don't double-click the first time)

4. **Check System Settings:**
   - Go to System Settings > Privacy & Security
   - Look for any blocked app messages
   - Click "Open Anyway" if present

### "You don't have permission to open this application"

1. Right-click the app → **Get Info**
2. Under **Sharing & Permissions**, check your access
3. If you don't have "Read & Write":
   - Click the **lock icon** (bottom right)
   - Enter your password
   - Change your permissions to **Read & Write**
   - Click the **gear icon** → **Apply to enclosed items**

### App won't launch after removing quarantine

1. **Check if the app actually exists:**
   ```bash
   ls -la "/Applications/FRCR Examiner.app"
   ```

2. **Try opening from Terminal to see errors:**
   ```bash
   "/Applications/FRCR Examiner.app/Contents/MacOS/FRCR Examiner"
   ```

3. **Check Console for errors:**
   - Open Console.app (Applications > Utilities > Console)
   - Look for errors related to "FRCR Examiner"

4. **Verify Python is bundled:**
   ```bash
   ls -la "/Applications/FRCR Examiner.app/Contents/Resources/flask_server"
   ```

### "The application can't be opened" - Still blocked after all steps

If you've tried everything and it's still blocked:

1. **Temporarily disable Gatekeeper** (NOT RECOMMENDED, but works):
   ```bash
   sudo spctl --master-disable
   ```
   Then open the app, and re-enable:
   ```bash
   sudo spctl --master-enable
   ```

2. **Check macOS version:**
   - The app requires macOS 10.12 or later
   - Check: Apple menu → About This Mac

3. **Re-download and reinstall:**
   - Delete the app from Applications
   - Download a fresh copy from GitHub
   - Follow installation steps again

### Still having issues?

1. Make sure you're on **macOS 10.12 or later**
2. Check that you have **enough disk space** (app needs ~300 MB)
3. Try **reinstalling** the app completely
4. **Open an issue on GitHub** with:
   - Your macOS version
   - Exact error message
   - Steps you've tried
   - Terminal output (if any)

## Security Note

This app is **open source** and you can review the code on GitHub. The app:
- ✅ Runs entirely on your local machine
- ✅ Doesn't require internet connection
- ✅ Doesn't collect or transmit any data
- ✅ All data is stored locally in your `instance` folder

## Future Updates

For future versions, you'll need to repeat the Gatekeeper fix (Option 1 or 2) after updating. This is a one-time process per installation.

