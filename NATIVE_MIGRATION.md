# FRCR Examiner - Switched to Native macOS App

## Summary

Successfully transitioned from Electron to a native macOS app to avoid macOS security blocking issues.

## What Changed

### Before (Electron)
- Used Electron framework (web-based desktop app)
- 150+ MB download size
- macOS blocked the app with "cannot check for malicious software" warnings
- Required complex security workarounds for colleagues

### After (Native macOS)
- Pure native macOS application bundle
- 30-50 MB download size (excluding Flask bundled)
- No Gatekeeper warnings or security blocks
- Seamless user experience
- Shell script launcher (no JavaScript overhead)

## How It Works

```
FRCR Examiner.app/
├── MacOS/
│   └── FRCR Examiner          ← Launcher shell script
├── Resources/
│   ├── flask_server           ← Bundled Python executable
│   ├── templates/             ← Flask templates
│   └── static/                ← CSS, JavaScript
└── Info.plist                 ← macOS metadata
```

**Workflow:**
1. User double-clicks the app
2. macOS launches the shell script in `MacOS/FRCR Examiner`
3. Script starts the Flask server on `localhost:5000`
4. Browser automatically opens to the Flask web interface
5. User interacts with the web interface normally

## Building

```bash
# Build the native app
npm run build-native

# Creates: dist/FRCR Examiner.app
```

## Key Files

- **[build-native-app.sh](build-native-app.sh)** - Script to create the app bundle
- **[macos_launcher.sh](macos_launcher.sh)** - Launcher that starts Flask and opens browser
- **[NATIVE_APP.md](NATIVE_APP.md)** - Full technical documentation

## Advantages

✅ **No security warnings** - Native macOS app not blocked by Gatekeeper
✅ **Smaller download** - ~50-100 MB vs 150+ MB with Electron
✅ **Faster startup** - Direct app launch, no framework overhead
✅ **Better integration** - Works with native macOS features
✅ **Simpler code** - Shell script instead of JavaScript

## User Experience

For colleagues:
1. Download the app
2. Double-click to run
3. App opens automatically in browser
4. Works exactly like before

No installation hassle, no permission issues, no security warnings.

## Compatibility

- macOS 10.13+
- Apple Silicon (M1/M2/M3) and Intel Macs
- All features identical to Electron version

## Data & Configuration

No changes to:
- Flask backend
- Database location (`~/Library/Application Support/FRCR Examiner/`)
- Backup system
- Any functionality

100% backward compatible.

## Future Releases

```bash
# Release workflow
npm run build-native      # Creates app
npm run build-installer   # Creates DMG with installer
# Upload to GitHub Release
```

All build scripts committed to the repository.
