#!/bin/bash
# Build Windows installer using Docker on macOS
# This allows cross-platform building without Windows

set -e

echo "🐳 Building Windows installer with Docker..."
echo "=============================================="
echo ""

# Check Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo "Start Docker Desktop and try again"
    exit 1
fi

cd "$(cd "$(dirname "$0")" && pwd)"

echo "📦 Building for Windows..."
docker run --rm \
  -v "$(pwd):/project" \
  -w /project \
  -e ELECTRON_CACHE=/.electron-cache \
  -e npm_config_cache=/.npm \
  electronuserland/builder:wine \
  bash -c "npm install --legacy-peer-deps && npm run build-win"

echo ""
echo "✅ Windows build complete!"
echo "📁 Check dist/ folder for installers:"
ls -lh dist/*.exe 2>/dev/null || echo "No .exe files found"

echo ""
echo "📦 Ready to upload to GitHub!"
