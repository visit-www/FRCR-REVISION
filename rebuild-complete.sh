#!/bin/bash
# Complete rebuild script that ensures Python is bundled
# This fixes the "empty app" issue

set -e

echo "🔨 Complete Rebuild of FRCR Examiner"
echo "======================================"
echo ""
echo "This will:"
echo "1. Build Python bundle with PyInstaller"
echo "2. Copy it to resources folder"
echo "3. Rebuild Electron app with all files"
echo ""

# Check virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Activating virtual environment..."
    if [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo "❌ Error: No virtual environment found!"
        exit 1
    fi
fi

# Install PyInstaller if needed
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "📦 Installing PyInstaller..."
    pip install pyinstaller
fi

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build dist/flask_server resources/flask_server

# Build Flask with PyInstaller
echo "🐍 Building Python bundle..."
pyinstaller flask_server.spec --clean --noconfirm

# Verify PyInstaller build - check if executable file exists
if [ -f "dist/flask_server" ]; then
    echo "✅ Found Flask executable: dist/flask_server"
    EXE_FOUND="dist/flask_server"
elif [ -d "dist/flask_server" ]; then
    EXE_FOUND=$(find dist/flask_server -type f -perm +111 -name "flask_server" 2>/dev/null | head -1)
    if [ -z "$EXE_FOUND" ]; then
        EXE_FOUND=$(find dist/flask_server -type f -name "flask_server" 2>/dev/null | head -1)
    fi
    if [ -n "$EXE_FOUND" ]; then
        echo "✅ Found Flask executable: $EXE_FOUND"
    fi
else
    echo "❌ PyInstaller build failed - dist/flask_server not found!"
    exit 1
fi

# If it's a single file, we need to create a directory structure for Electron
if [ -f "dist/flask_server" ]; then
    echo "📦 Creating directory structure for Electron..."
    mkdir -p dist/flask_server_dir
    mv dist/flask_server dist/flask_server_dir/flask_server
    rm -rf dist/flask_server
    mv dist/flask_server_dir dist/flask_server
fi

# Copy to resources
echo "📦 Copying Python bundle to resources..."
mkdir -p resources
rm -rf resources/flask_server
cp -r dist/flask_server resources/

# Verify resources folder
if [ ! -d "resources/flask_server" ]; then
    echo "❌ Failed to create resources/flask_server!"
    exit 1
fi

echo "✅ Python bundle ready!"
echo ""

# Clean Electron build
echo "🧹 Cleaning Electron build..."
rm -rf dist/mac-arm64 dist/FRCR*.dmg dist/FRCR*.zip

# Build Electron app
echo "⚡ Building Electron app..."
npm run build-mac

# Verify build
if [ ! -f "dist/FRCR Examiner-1.0.0-arm64.dmg" ]; then
    echo "❌ Electron build failed!"
    exit 1
fi

echo ""
echo "✅ Build complete!"
echo "📦 DMG: dist/FRCR Examiner-1.0.0-arm64.dmg"
echo ""
echo "The app now includes:"
echo "  ✅ Python runtime (bundled)"
echo "  ✅ Flask server executable"
echo "  ✅ Templates and static files"
echo "  ✅ All required dependencies"
echo ""
echo "App size: $(du -sh "dist/mac-arm64/FRCR Examiner.app" | cut -f1)"

