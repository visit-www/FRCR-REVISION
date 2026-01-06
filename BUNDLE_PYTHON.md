# 🐍 Bundling Python with Electron App

This guide explains how to build the FRCR Examiner with Python bundled, so users don't need to install Python separately.

## Overview

The app uses **PyInstaller** to create a standalone executable of the Flask backend, which is then bundled with the Electron app. This creates a completely self-contained application.

## Prerequisites

1. **Python 3.8+** installed on your build machine
2. **Virtual environment** with all dependencies installed
3. **PyInstaller** (will be installed automatically if missing)

## Build Process

### Quick Start

```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies if needed
pip install -r requirements.txt

# Build with bundled Python
./build-with-python.sh
```

Or use npm:

```bash
npm run build-with-python
```

### Manual Build Steps

If you prefer to build manually:

1. **Build Flask executable with PyInstaller:**
   ```bash
   pyinstaller flask_server.spec --clean --noconfirm
   ```

2. **Copy executable to resources folder:**
   ```bash
   mkdir -p resources
   cp -r dist/flask_server resources/
   ```

3. **Build Electron app:**
   ```bash
   npm run build-mac    # macOS
   npm run build-win    # Windows
   npm run build        # Linux
   ```

## File Structure

After building, the structure should be:

```
FRCR_EXAMINER/
├── resources/
│   └── flask_server/
│       └── flask_server          # Bundled Python executable (or .exe on Windows)
├── dist/
│   └── FRCR Examiner-*.dmg      # Final installer
└── ...
```

## How It Works

1. **PyInstaller** bundles Python, Flask, and all dependencies into a single executable
2. **Electron** packages this executable along with the frontend
3. **main.js** detects if the app is packaged and uses the bundled executable instead of system Python

## Development vs Production

- **Development**: Uses system Python (`python3 app.py`)
- **Production**: Uses bundled executable (`resources/flask_server/flask_server`)

The app automatically detects which mode it's in using `app.isPackaged`.

## Troubleshooting

### PyInstaller build fails

- Make sure all dependencies are installed: `pip install -r requirements.txt`
- Check that you're in a virtual environment
- Try building with verbose output: `pyinstaller flask_server.spec --log-level=DEBUG`

### Executable not found in packaged app

- Check that `resources/flask_server/` exists after PyInstaller build
- Verify the executable has execute permissions: `chmod +x resources/flask_server/flask_server`
- Check the build logs for any errors

### Flask server doesn't start

- Check console output for error messages
- Verify the executable works standalone: `./resources/flask_server/flask_server`
- Make sure templates and static folders are included in the PyInstaller bundle

## File Sizes

Bundling Python significantly increases the app size:
- **Without Python**: ~100-150 MB
- **With Python**: ~200-300 MB (depending on dependencies)

This is expected and normal for apps that bundle Python.

## Platform-Specific Notes

### macOS
- The executable will be `flask_server` (no extension)
- May need to handle code signing for distribution

### Windows
- The executable will be `flask_server.exe`
- Antivirus software may flag PyInstaller executables (false positive)

### Linux
- The executable will be `flask_server`
- May need to set execute permissions: `chmod +x flask_server`

## Next Steps

After building, test the installer on a clean machine without Python installed to verify everything works correctly.

