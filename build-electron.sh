#!/bin/bash
# Build script for FRCR Examiner Electron app

set -e

echo "🔨 Building FRCR Examiner Electron App"
echo "======================================"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
  echo "📦 Installing dependencies..."
  npm install
fi

# Determine OS and build accordingly
if [[ "$OSTYPE" == "darwin"* ]]; then
  echo "🍎 Building for macOS..."
  npm run build-mac
  echo "✅ macOS build complete!"
  echo "📦 Output: dist/FRCR\ Examiner-*.dmg"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
  echo "🪟 Building for Windows..."
  npm run build-win
  echo "✅ Windows build complete!"
  echo "📦 Output: dist/FRCR\ Examiner-*.exe"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
  echo "🐧 Building for Linux..."
  npm run build
  echo "✅ Linux build complete!"
  echo "📦 Output: dist/FRCR-Examiner-*.AppImage"
else
  echo "❓ Unknown OS type: $OSTYPE"
  echo "Running universal build..."
  npm run build-all
fi

echo ""
echo "🎉 Build complete!"
echo "Check the 'dist' folder for installers"
