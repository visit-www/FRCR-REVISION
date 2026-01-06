# 📦 FRCR Examiner v3.1.0 Release

**Professional Electron Desktop Application**

---

## 🎉 What's New

### ✨ Desktop Application
- **Native installers** for Windows, macOS, and Linux
- **One-click installation** - no technical knowledge required
- **Professional app experience** - feels like any native app
- **Auto-launches** Flask backend automatically

### 🔒 Complete Privacy
- ✅ SQLite database stored **100% locally** on your computer
- ✅ **No data** sent to cloud servers
- ✅ Database stays in `~/Library/Application Support/FRCR Examiner/`
- ✅ Auto-backup every 24 hours
- ✅ Export/import your data anytime

### 🚀 Easy Distribution
- **Single executable file** - no dependencies
- **Professional installer** - users can install like any other app
- **Cross-platform** - works on Windows, macOS, Linux
- **Portable version** included - use without installing

---

## 📥 Installation

### **macOS**

1. **Download:** `FRCR Examiner-3.1.0.dmg`
2. **Install:**
   - Double-click the `.dmg` file
   - Drag "FRCR Examiner" to Applications folder
   - Done!
3. **Launch:**
   - Open Applications folder
   - Double-click "FRCR Examiner"
   - App starts automatically with Flask backend

### **Windows**

1. **Download:** `FRCR Examiner Setup 3.1.0.exe`
2. **Install:**
   - Double-click the `.exe` file
   - Click "Install"
   - Choose installation location (optional)
   - Click "Finish"
3. **Launch:**
   - Find "FRCR Examiner" in Start Menu
   - Click to launch
   - App starts automatically

### **Linux**

1. **Download:** `FRCR-Examiner-3.1.0.AppImage`
2. **Install:**
   - Make executable: `chmod +x FRCR-Examiner-3.1.0.AppImage`
   - Double-click to run
   - Or install: `./FRCR-Examiner-3.1.0.AppImage --appimage-extract`
3. **Launch:**
   - Double-click the AppImage file
   - App starts automatically

---

## 💻 System Requirements

| Platform | Requirement |
|----------|------------|
| **macOS** | 10.13+ (Intel or Apple Silicon) |
| **Windows** | Windows 7+ (32-bit or 64-bit) |
| **Linux** | Ubuntu 16.04+, Fedora 21+ |
| **RAM** | 512 MB minimum (1 GB recommended) |
| **Disk** | 500 MB free space |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│   FRCR Examiner Desktop App         │
│   (Single executable file)          │
├─────────────────────────────────────┤
│   Electron Window                   │
│   (Native macOS/Windows/Linux UI)   │
├─────────────────────────────────────┤
│   Flask Backend                     │
│   (localhost:5000)                  │
│   Runs automatically on startup     │
├─────────────────────────────────────┤
│   SQLite Database                   │
│   (User's computer)                 │
│   100% private - never leaves PC    │
└─────────────────────────────────────┘
```

---

## 📚 Documentation

- **[ELECTRON.md](ELECTRON.md)** - Complete setup guide
- **[ELECTRON_QUICKSTART.md](ELECTRON_QUICKSTART.md)** - Quick start
- **[HYBRID_DEPLOYMENT.md](HYBRID_DEPLOYMENT.md)** - Architecture overview

---

## 🔄 Updates

### Check for Updates
The app will notify you when a new version is available.

### Manual Update
1. Download the latest version from GitHub Releases
2. Install like above
3. Old version is automatically replaced

---

## 🐛 Troubleshooting

### "App won't start"
- **macOS:** Open Applications > FRCR Examiner
- **Windows:** Check Start Menu > FRCR Examiner
- **Linux:** Run from terminal: `./FRCR-Examiner-3.1.0.AppImage`

### "Database not found"
- First launch creates database automatically
- Check: `~/Library/Application Support/FRCR Examiner/` (macOS)
- Or: `C:\Users\YourName\AppData\Roaming\FRCR Examiner\` (Windows)

### "Port 5000 in use"
- Another app is using port 5000
- Try restarting your computer
- Or build custom version with different port

### "Permission denied" (Linux)
```bash
chmod +x FRCR-Examiner-3.1.0.AppImage
./FRCR-Examiner-3.1.0.AppImage
```

---

## 💾 Backup & Export

### Backup Database
```bash
# macOS/Linux
cp ~/Library/Application\ Support/FRCR\ Examiner/frcr_examiner.db ~/Desktop/frcr_backup.db

# Windows
copy "%AppData%\FRCR Examiner\frcr_examiner.db" "%USERPROFILE%\Desktop\frcr_backup.db"
```

### Restore Database
Copy backup file to FRCR Examiner folder and restart app.

---

## 🔐 Security

✅ **Data stays on your computer**
- No cloud syncing
- No data collection
- No telemetry
- Completely private

✅ **Secure communication**
- All API calls use localhost
- No external network access
- Isolated process

---

## 📞 Support

Having issues? 

1. **Check documentation:** See [ELECTRON.md](ELECTRON.md)
2. **Report bug:** Open issue on [GitHub](https://github.com/visit-www/Frcr-examiner/issues)
3. **Feature request:** [GitHub Discussions](https://github.com/visit-www/Frcr-examiner/discussions)

---

## 🎓 For Developers

Want to build from source? See [ELECTRON_QUICKSTART.md](ELECTRON_QUICKSTART.md)

```bash
# Install dependencies
npm install

# Run in development
npm run dev

# Build installers
./build-electron.sh    # macOS/Linux
build-electron.bat     # Windows
```

---

## 📊 Version History

- **v3.1.0** - Electron desktop app release
- **v3.0.0** - Hybrid Vercel + local backend
- **v2.0.0** - Major refactor
- **v1.0.0** - Initial release

---

## 📄 License

MIT License - See LICENSE file in repository

---

**🚀 Ready to use?**

1. Download your platform's installer from [Releases](https://github.com/visit-www/Frcr-examiner/releases)
2. Install (follow steps above)
3. Launch the app
4. Start using FRCR Examiner!

**Questions?** Open an issue on GitHub or check the documentation.

Thank you for using FRCR Examiner! 🎉
