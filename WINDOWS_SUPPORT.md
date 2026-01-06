# Windows Installer Support for FRCR Examiner

Yes! **Electron fully supports Windows installers.** Your app can run on Windows just like macOS and Linux.

## 📥 Installation on Windows

### Download the Installer
Go to: https://github.com/visit-www/Frcr-examiner/releases/tag/v3.1.0

**Look for:** `FRCR Examiner Setup X.X.X.exe`

### Install (3 Easy Steps)

1. **Download** the `.exe` file
2. **Double-click** to run installer
3. **Click "Install"** and follow prompts

That's it! The app will:
- ✅ Install to `Program Files`
- ✅ Create Start Menu shortcut
- ✅ Auto-launch Flask backend
- ✅ Be ready to use

## 🏗️ How It Works on Windows

```
┌─────────────────────────────────┐
│  FRCR Examiner.exe              │
│  (Single executable file)       │
├─────────────────────────────────┤
│  Electron Window (Native UI)    │
│  Shows your app interface       │
├─────────────────────────────────┤
│  Python + Flask (Background)    │
│  Runs on localhost:5000         │
├─────────────────────────────────┤
│  SQLite Database (Local)        │
│  C:\Users\YourName\AppData\...  │
│  (100% private, never cloud)    │
└─────────────────────────────────┘
```

## 💻 System Requirements

- **Windows Version:** Windows 7 SP1 or later (7, 8, 10, 11)
- **Architecture:** 32-bit or 64-bit
- **RAM:** 512 MB minimum (1 GB recommended)
- **Disk Space:** 500 MB free
- **Internet:** Not required (all data stays local)

## 🔄 Building Windows Installer Yourself

If you want to build the Windows installer on your own Windows machine:

### Prerequisites
- Node.js 16+ (https://nodejs.org/)
- Python 3.8+ (https://www.python.org/)

### Build Steps

```bash
# 1. Clone the repository
git clone https://github.com/visit-www/Frcr-examiner
cd Frcr-examiner

# 2. Install dependencies
npm install

# 3. Build Windows installer
npm run build-win
```

### Output
```
dist/
├── FRCR Examiner Setup X.X.X.exe    ← Installer (recommended)
└── FRCR Examiner X.X.X.exe          ← Portable (no installation)
```

**Share the `.exe` file with users!**

## 📊 File Sizes

| File | Size | Type |
|------|------|------|
| FRCR Examiner Setup X.X.X.exe | ~180-250 MB | Installer |
| FRCR Examiner X.X.X.exe | ~200 MB | Portable |

Large size because:
- Chromium browser engine: ~150 MB
- Python + Flask: ~100 MB
- Your app code: ~10 MB

## 🐛 Troubleshooting

### "Windows Defender blocked the installer"
- This is normal for unsigned apps
- Click "More info" → "Run anyway"
- Or get code signing certificate to avoid this

### "App won't start"
1. Open Task Manager (Ctrl+Shift+Esc)
2. Look for "FRCR Examiner" process
3. If missing, try reinstalling
4. Check Windows Event Viewer for errors

### "Database location?"
```
C:\Users\YourName\AppData\Roaming\FRCR Examiner\frcr_examiner.db
```

Backup this folder to keep your data safe!

### "Can't find Python?"
Electron bundles Python automatically. If issues:
- Reinstall the app
- Check logs: `C:\Users\YourName\AppData\Roaming\FRCR Examiner\logs`

## 🔄 Updates

### Auto-Updates
- App checks for updates on launch
- If new version available, notifies user
- User can accept or skip

### Manual Update
1. Download latest installer from releases
2. Run it (replaces old version)
3. Data is preserved

## 💾 Backup Your Data

**Important:** Back up your database regularly!

### Quick Backup
```
1. Go to: C:\Users\YourName\AppData\Roaming\FRCR Examiner
2. Right-click frcr_examiner.db
3. Copy → Paste to Desktop or USB
```

### Restore from Backup
```
1. Close FRCR Examiner app
2. Replace frcr_examiner.db with your backup
3. Restart the app
4. Data restored!
```

## 🔐 Security & Privacy

✅ **100% Local**
- Data never leaves your computer
- No cloud backup (you control backups)
- No telemetry or tracking
- No internet required

✅ **Secure**
- Flask only listens on localhost
- Can't be accessed from network (by default)
- SQLite encrypted at rest (optional)

## 🚀 Advanced: Command Line Options

### Run from Command Prompt

```batch
# Start normally
"C:\Program Files\FRCR Examiner\FRCR Examiner.exe"

# Disable GPU acceleration (if graphics issues)
"C:\Program Files\FRCR Examiner\FRCR Examiner.exe" --disable-gpu

# Debug mode (shows developer tools)
DEBUG_ELECTRON=true "C:\Program Files\FRCR Examiner\FRCR Examiner.exe"
```

## 📞 Support

Having issues on Windows?

1. Check [ELECTRON.md](ELECTRON.md) - General guide
2. Check Windows Event Viewer for error logs
3. Open issue on GitHub: https://github.com/visit-www/Frcr-examiner/issues

## 🎯 Summary

| Feature | Support |
|---------|---------|
| **Install** | ✅ One-click installer |
| **Portability** | ✅ Standalone .exe |
| **Data Storage** | ✅ 100% local |
| **Updates** | ✅ Auto-notify |
| **Uninstall** | ✅ Via Control Panel |
| **Cloud Sync** | ❌ (By design - data stays local) |

---

**Ready to use on Windows?**

👉 Download from: https://github.com/visit-www/Frcr-examiner/releases

Double-click the installer and you're done! 🎉
