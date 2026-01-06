#!/bin/bash
# Cross-platform build using Docker
# Builds Windows and Linux installers on macOS

set -e

echo "🐳 Building FRCR Examiner using Docker..."
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed!"
    echo "Install Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Build Windows in Docker
echo "🪟 Building Windows installer..."
docker run --rm \
  -v "$(pwd):/project" \
  -w /project \
  electronuserland/builder:wine-mono \
  npm install && npm run build-win

echo "✅ Windows build complete!"
echo "📦 Output: dist/FRCR\ Examiner\ Setup\ *.exe"
echo ""

# Build Linux in Docker  
echo "🐧 Building Linux installer..."
docker run --rm \
  -v "$(pwd):/project" \
  -w /project \
  electronuserland/builder:latest \
  npm install && npm run build

echo "✅ Linux build complete!"
echo "📦 Output: dist/FRCR-Examiner-*.AppImage"
echo ""

echo "🎉 All builds complete!"
echo "Check dist/ folder for installers"
