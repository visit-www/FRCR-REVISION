#!/bin/bash

# FRCR EXAMINER - Desktop App Builder using PyInstaller
# This script creates a standalone desktop application

echo "╔════════════════════════════════════════════════════════════╗"
echo "║   FRCR EXAMINER - Building Desktop App                    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "📦 Installing PyInstaller..."
    pip install pyinstaller
fi

echo "🔨 Building desktop application..."
echo ""

# Create the desktop app
pyinstaller --onefile \
    --windowed \
    --name "FRCR_Examiner" \
    --icon=None \
    --add-data "templates:templates" \
    --add-data "static:static" \
    --add-data "instance:instance" \
    --hidden-import=flask \
    --hidden-import=flask_sqlalchemy \
    --hidden-import=sqlalchemy \
    app.py

echo ""
echo "✅ Build complete!"
echo ""
echo "📍 Your desktop app is ready at:"
echo "   dist/FRCR_Examiner (macOS app)"
echo "   dist/FRCR_Examiner.exe (Windows executable)"
echo ""
echo "🚀 To run the desktop app:"
echo "   • macOS: Open dist/FRCR_Examiner"
echo "   • Windows: Double-click dist/FRCR_Examiner.exe"
echo ""
echo "📦 To share with others:"
echo "   1. Zip the 'dist' folder"
echo "   2. Send the zip file to others"
echo "   3. They can extract and run directly (no Python needed!)"
echo ""
