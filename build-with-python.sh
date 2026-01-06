#!/bin/bash
# Build script that bundles Python with Electron app
# This script:
# 1. Creates a PyInstaller bundle of the Flask app
# 2. Builds the Electron app with the bundled Python executable

set -e

echo "🐍 Building FRCR Examiner with Bundled Python"
echo "=============================================="

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Not in a virtual environment. Activating venv..."
    if [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo "❌ Error: No virtual environment found. Please create one first:"
        echo "   python3 -m venv venv"
        echo "   source venv/bin/activate"
        echo "   pip install -r requirements.txt"
        exit 1
    fi
fi

# Check if PyInstaller is installed
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "📦 Installing PyInstaller..."
    pip install pyinstaller
fi

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build dist/flask_server

# Build Flask app with PyInstaller
echo "🔨 Building Flask app with PyInstaller..."
pyinstaller flask_server.spec --clean --noconfirm

# Check if build was successful
if [ ! -f "dist/flask_server/flask_server" ] && [ ! -f "dist/flask_server/flask_server.exe" ]; then
    echo "❌ Error: PyInstaller build failed!"
    exit 1
fi

echo "✅ PyInstaller build complete!"

# Move flask_server to resources directory for Electron
echo "📦 Preparing Flask bundle for Electron..."
mkdir -p resources
rm -rf resources/flask_server
cp -r dist/flask_server resources/

# Build Electron app
echo "⚡ Building Electron app..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    npm run build-mac
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    npm run build-win
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    npm run build
else
    npm run build-all
fi

echo ""
echo "🎉 Build complete!"
echo "📦 Check the 'dist' folder for installers"
echo "🐍 Python is now bundled with the app - no separate Python installation needed!"

