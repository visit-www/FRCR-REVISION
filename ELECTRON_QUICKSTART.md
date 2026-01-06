# 🚀 Quick Start: Electron Desktop App

## Installation

### 1. Prerequisites
- **Node.js** v16+ → https://nodejs.org/
- **Python** 3.8+ → Already installed on macOS

### 2. Install Dependencies
```bash
cd /path/to/FRCR_EXAMINER
npm install
```

## Running

### Development (with hot reload)
```bash
npm run dev
```
This starts Flask + Electron together. Changes are auto-reloaded.

### Production (standalone)
```bash
npm start
```
Launches the Electron app without the Flask console.

## Building Installers

### macOS (.dmg file)
```bash
./build-electron.sh
```
Creates `dist/FRCR Examiner-1.0.0.dmg`

Users install by: **Double-click the .dmg** → Drag app to Applications

### Windows (.exe file)
```bash
build-electron.bat
```
Creates `dist/FRCR Examiner Setup 1.0.0.exe`

Users install by: **Double-click the .exe** → Follow wizard

## Distribution

1. Build the app: `./build-electron.sh`
2. Find installers in `dist/` folder
3. Upload to GitHub Releases (or your website)
4. Users download and install like any other app

## Troubleshooting

**"command not found: npm"**
→ Install Node.js from https://nodejs.org/

**Flask won't start**
→ Make sure port 5000 is available: `lsof -i :5000`

**App crashes on startup**
→ Try: `npm run dev` to see error logs

## See Also
- [ELECTRON.md](ELECTRON.md) - Full documentation
- [HYBRID_DEPLOYMENT.md](HYBRID_DEPLOYMENT.md) - Architecture overview
