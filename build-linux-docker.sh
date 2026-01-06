#!/bin/bash
# Build Linux installer using Docker on macOS
# This allows cross-platform building without Linux

set -e

echo "🐳 Building Linux installer with Docker..."
echo "==========================================="
echo ""

# Check Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo "Start Docker Desktop and try again"
    exit 1
fi

cd "$(cd "$(dirname "$0")" && pwd)"

echo "📦 Building for Linux..."
docker run --rm \
  -v "$(pwd):/project" \
  -w /project \
  -e ELECTRON_CACHE=/.electron-cache \
  -e npm_config_cache=/.npm \
  electronuserland/builder:latest \
  bash -c "npm install --legacy-peer-deps && npm run build"

echo ""
echo "✅ Linux build complete!"
echo "📁 Check dist/ folder for installers:"
ls -lh dist/*.AppImage 2>/dev/null || echo "No .AppImage files found"

echo ""
echo "📦 Ready to upload to GitHub!"
