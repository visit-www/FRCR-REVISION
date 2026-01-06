# FRCR Examiner - Native macOS App (Platypus Alternative)

## Overview

This is the native macOS version of FRCR Examiner, built without Electron to avoid macOS security blocking issues.

## How It Works

Instead of using Electron (which is sometimes blocked by macOS security policies), this version:

1. **Launches as a native macOS app** - Creates a standard macOS application bundle
2. **Starts the Flask server** - Runs the bundled Python Flask server in the background
3. **Opens in your browser** - Automatically opens http://localhost:5000 in your default browser
4. **Seamless experience** - Feels like a native app while using the web interface

## Building

### Build the native app:

```bash
npm run build-native
```

This creates: `dist/FRCR Examiner.app`

### Create installer DMG:

```bash
npm run build-installer
```

This creates the installer with the native app.

## File Structure

```
FRCR Examiner.app/
├── Contents/
│   ├── MacOS/
│   │   └── FRCR Examiner          (launcher script)
│   ├── Resources/
│   │   ├── flask_server           (Python executable)
│   │   ├── templates/             (Flask templates)
│   │   └── static/                (CSS, JS files)
│   └── Info.plist                 (macOS metadata)
```

## Advantages Over Electron

✅ **No security warnings** - Native macOS apps aren't blocked by Gatekeeper
✅ **Smaller download** - No Electron framework included  
✅ **Faster startup** - Direct app launch, no framework overhead
✅ **Better integration** - Works with native macOS features
✅ **Simpler code** - Pure shell script launcher, no JavaScript framework

## Technical Details

- **Launcher**: `macos_launcher.sh` - Shell script that starts Flask and opens browser
- **Backend**: Bundled `flask_server` executable (created by PyInstaller)
- **Framework**: Uses native macOS app bundle structure
- **Port**: Flask runs on localhost:5000 (configurable)

## Troubleshooting

### App won't open
```bash
# Remove quarantine attribute
xattr -d com.apple.quarantine "/Applications/FRCR Examiner.app"
```

### Flask already running
```bash
# Kill Flask process
pkill -f flask_server
```

### Can't connect to localhost:5000
```bash
# Check if Flask is running
lsof -i :5000

# Check logs
tail -f /tmp/frcr_flask.log
```

## Migration from Electron

This native app is a drop-in replacement for the Electron version. All Flask backends and data remain the same. Simply:

1. Build: `npm run build-native`
2. Install: Copy the .app to /Applications
3. Run: Double-click to launch

No configuration changes needed!
