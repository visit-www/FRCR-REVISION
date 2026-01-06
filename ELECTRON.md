# 🖥️ Electron Desktop Application Setup

This guide explains how to build and distribute the FRCR Examiner as a native desktop application using Electron.

## Overview

The Electron app packages the Flask backend and Vercel frontend into a single native application for Windows, macOS, and Linux.

### What is Electron?
Electron is a framework that lets you build desktop apps with web technologies (HTML, CSS, JavaScript). It powers apps like VS Code, Slack, and Discord.

### Architecture

```
┌─────────────────────────────────────────────┐
│  FRCR Examiner Desktop App (Electron)       │
├─────────────────────────────────────────────┤
│  • Electron Main Process (Node.js)          │
│    - Spawns Flask backend                   │
│    - Manages window/menu                    │
│    - Handles IPC communication              │
├─────────────────────────────────────────────┤
│  • Frontend (Vercel or local)               │
│    - HTML/CSS/JS templates                  │
│    - Calls http://localhost:5000            │
├─────────────────────────────────────────────┤
│  • Backend (Flask)                          │
│    - Runs on localhost:5000                 │
│    - Handles all API requests               │
├─────────────────────────────────────────────┤
│  • Database (SQLite)                        │
│    - ~/Library/Application Support/...      │
│    - User's computer (100% private)         │
└─────────────────────────────────────────────┘
```

---

## Installation & Development

### Prerequisites

- **Node.js** v16+ (includes npm)
  - Download: https://nodejs.org/
- **Python** 3.8+ (for Flask backend)
- **Git** (already installed on macOS/Linux)

### 1. Install Electron Dependencies

```bash
cd /path/to/FRCR_EXAMINER
npm install
```

This installs:
- `electron` - The framework
- `electron-builder` - Creates installers
- `concurrently` - Runs multiple processes

### 2. Test Electron App Locally

```bash
# Run Flask backend + Electron in development
npm run dev
```

This will:
1. Start Flask on http://localhost:5000
2. Launch Electron window showing the app
3. Auto-reload on file changes

**Or manually:**

```bash
# Terminal 1: Start Flask
python -m flask run --port=5000

# Terminal 2: Start Electron
npm start
```

---

## Building Installers

### Build for macOS

```bash
./build-electron.sh
# or
npm run build-mac
```

Creates:
- `dist/FRCR Examiner-1.0.0.dmg` - macOS installer
- `dist/FRCR Examiner-1.0.0-mac.zip` - Portable version

**Install:** Double-click the `.dmg` file

### Build for Windows

```bash
build-electron.bat
# or
npm run build-win
```

Creates:
- `dist/FRCR Examiner Setup 1.0.0.exe` - Windows installer
- `dist/FRCR Examiner 1.0.0.exe` - Portable version

**Install:** Double-click the `.exe` file

### Build for All Platforms

```bash
npm run build-all
```

Creates installers for Windows, macOS, and Linux.

---

## Distributing Your App

### File Sizes

- **macOS DMG**: ~150-200 MB
- **Windows EXE**: ~180-250 MB
- **Linux AppImage**: ~160-200 MB

### Distribution Options

#### 1. GitHub Releases (Recommended)
```bash
# After building, create a GitHub release
git tag v1.0.0
git push origin v1.0.0

# Then upload dist/* files to GitHub Releases
# Users can download and install directly
```

#### 2. Direct Download
Host `dist/` files on your website:
```
https://yoursite.com/downloads/FRCR-Examiner-1.0.0.dmg
https://yoursite.com/downloads/FRCR-Examiner-Setup-1.0.0.exe
```

#### 3. Auto-Updates (Advanced)
The `electron-builder.yml` is configured for GitHub releases:
```yaml
publish:
  provider: github
  owner: visit-www
  repo: Frcr-examiner
```

When you release on GitHub, the app can auto-update!

---

## File Structure

```
FRCR_EXAMINER/
├── electron/                 # Electron-specific code
│   ├── main.js              # Main process (starts Flask)
│   └── preload.js           # IPC bridge for security
├── templates/               # Flask HTML templates
├── static/                  # CSS, JS, images
├── instance/                # Database directory
│   └── frcr_examiner.db     # SQLite database
├── app.py                   # Flask application
├── requirements.txt         # Python dependencies
├── package.json             # Node.js dependencies
├── electron-builder.yml     # Build configuration
├── build-electron.sh        # Build script (macOS/Linux)
└── build-electron.bat       # Build script (Windows)
```

---

## How It Works

### Startup Process

1. **User launches the app** → macOS/Windows starts Electron
2. **Electron main process** spawns Flask backend on localhost:5000
3. **Electron window opens** → shows the frontend UI
4. **Frontend makes API calls** → calls http://localhost:5000
5. **Flask handles requests** → reads/writes local SQLite database

### Data Storage

- **Database location**: `~/.frcr-examiner/` (hidden folder)
  - Windows: `C:\Users\YourName\AppData\Roaming\FRCR Examiner\`
  - macOS: `~/Library/Application Support/FRCR Examiner/`
  - Linux: `~/.config/FRCR Examiner/`

- **User data accessible via**:
  ```javascript
  // In Electron renderer process:
  const dataPath = await window.electron.openDatabaseFolder();
  ```

---

## Troubleshooting

### "Command not found: npm"
Install Node.js from https://nodejs.org/

### "Flask failed to start"
- Check Python is installed: `python --version`
- Check Flask installed: `pip install flask`
- Ensure port 5000 is not in use

### "App won't start on Windows"
- Try rebuilding: `npm run build-win`
- Check Visual C++ Runtime is installed
- Try running as Administrator

### Large file size?
Electron bundles Chromium (~150 MB) + Python (~100 MB). This is unavoidable but you can:
- Compress the installer with 7-Zip
- Use delta updates for subsequent versions
- Host on CDN for faster downloads

---

## Development Tips

### Enable Developer Tools
```javascript
// In electron/main.js, uncomment:
if (process.env.DEBUG_ELECTRON === 'true') {
  mainWindow.webContents.openDevTools();
}

// Then run:
DEBUG_ELECTRON=true npm start
```

### Hot Reload Frontend
Edit templates or static files and reload the window (Cmd+R).

### Debug Flask
Add print statements to `app.py` - they'll appear in the Electron console.

### Change Flask Port
Edit `electron/main.js`:
```javascript
const FLASK_PORT = 5001;  // Change from 5000
```

---

## Version Updates

### Update the Version

Edit `package.json`:
```json
{
  "version": "1.0.1"
}
```

Then rebuild:
```bash
npm run build-mac  # or build-win
```

The new installer will have version `1.0.1`.

---

## Security Considerations

✅ **Good Practices Used**:
- Preload script restricts IPC access
- No `nodeIntegration` enabled
- No `enableRemoteModule`
- Context isolation enabled

⚠️ **For Production**:
- Sign macOS app (requires developer certificate)
- Sign Windows installer (requires code signing certificate)
- Use HTTPS for any external APIs
- Keep dependencies updated: `npm audit`

---

## Next Steps

1. **Build the app**: `./build-electron.sh` (or `.bat` on Windows)
2. **Test the installer**: Download and install like a user would
3. **Gather feedback**: Ask users to test
4. **Release on GitHub**: Push to releases and share link
5. **Track issues**: Monitor for bugs and performance issues

---

## Support

For issues or questions:
- Check [Electron documentation](https://www.electronjs.org/docs)
- Review [electron-builder docs](https://www.electron.build/)
- Open an issue on GitHub: https://github.com/visit-www/Frcr-examiner/issues
