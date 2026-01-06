# Distribution Package for Colleagues

## Share Link
Send your colleagues this link to download and install the app:

```
https://github.com/visit-www/Frcr-examiner/releases/tag/v1.0.0
```

## What They Download
Two options available:

1. **FRCR Examiner-1.0.0-arm64.dmg** (106 MB) - Recommended
   - Standard macOS installer
   - Drag-and-drop to Applications
   - Easiest installation method

2. **FRCR Examiner-1.0.0-arm64-mac.zip** (103 MB) - Alternative
   - Portable ZIP archive
   - Can run from any location
   - Useful for USB installation

## Installation Instructions (Simple Version)

### For Colleagues:
```
1. Download DMG from Release Page
2. Double-click to mount
3. Drag app to Applications folder
4. Double-click to run
5. Done! (No other setup needed)
```

### If They Get a Security Warning:
```
1. Right-click the app
2. Select "Open"
3. Click "Open" again
4. App launches normally
```

## Verification

After installation, colleagues should:
1. Launch the app
2. See a browser window open with the FRCR Examiner interface
3. Be able to navigate to Dashboard/Setup sections
4. No Python installation or command-line needed

## What's Different from Developer Version

| Aspect | Colleague Version | Developer Version |
|--------|------------------|-------------------|
| Python Required | ❌ No | ✅ Yes (venv) |
| Node.js Required | ❌ No | ✅ Yes |
| Dependencies | 🔧 Bundled | 📦 Via pip |
| Start Method | 🖱️ Click App | 💻 `npm start` |
| Setup Time | ⚡ 1 minute | 🔧 30 minutes |
| Port Config | Automatic | Manual |
| Database | Auto-setup | Auto-setup |

## Troubleshooting for Colleagues

### Common Issues:

**"Cannot connect to Flask server"**
- Wait 10 seconds for app to fully start
- Check if port 5000 is available
- Try restarting the app

**"Database error on launch"**
- Delete ~/Library/Application Support/FRCR Examiner/instance/
- Relaunch the app (will recreate database)

**"Permission denied"**
- Right-click app → Open
- This is macOS security, not an app issue

## Key Differences from Development

The distributed version:
- ✅ Has Flask pre-built as standalone executable
- ✅ No Python dependencies to install
- ✅ No node_modules needed (packaged by electron-builder)
- ✅ All database/backup code included
- ✅ Works immediately after mounting DMG

## Version Info

- **App Version:** 1.0.0
- **Electron:** 27.0.0
- **Flask:** 2.3.3
- **Python Bundled:** 3.14.2
- **Platform:** macOS ARM64 (Apple Silicon M1/M2/M3/etc)

## Update Process

When releasing a new version:

1. **Developer**: 
   - Make code changes
   - Test locally with `npm start`
   - Build: `npm run build-mac`
   - Create release on GitHub

2. **Colleagues**:
   - Download new DMG
   - Replace old app in Applications
   - Done! Settings preserved

## Support Resources

**For Colleagues:**
- [Colleague Setup Guide](./COLLEAGUE_SETUP.md) - Detailed installation
- [Release Page](https://github.com/visit-www/Frcr-examiner/releases) - Downloads
- [Issues](https://github.com/visit-www/Frcr-examiner/issues) - Bug reports

**For Developers:**
- [README](./README.md) - Project overview
- [SETUP.md](./SETUP.md) - Development setup
- [ELECTRON.md](./ELECTRON.md) - Electron details

## Notes

- No Apple Developer subscription required
- App is unsigned (normal for independent distribution)
- First launch shows security warning (user-approved installation)
- All data stored locally, no cloud sync
- Suitable for small teams and local use

---

**Ready to share!** Just send colleagues the release link and point them to the [Colleague Setup Guide](./COLLEAGUE_SETUP.md)
