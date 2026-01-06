#!/bin/bash
# Build and Create Distribution Packages Locally
# This script creates distribution packages for manual release

echo "============================================"
echo "FRCR Examiner - Distribution Package Builder"
echo "============================================"
echo ""

# Get version
read -p "Enter version (e.g., 1.0.0): " VERSION
if [ -z "$VERSION" ]; then
    echo "Error: Version is required"
    exit 1
fi

# Create release directory
RELEASE_DIR="release-v${VERSION}"
mkdir -p "$RELEASE_DIR"

echo "Creating distribution packages for version ${VERSION}..."
echo ""

# Create Windows package
echo "[1/2] Creating Windows distribution package..."
SCRIPT_DIR="$(dirname "$0")"
cd "$SCRIPT_DIR/.."
mkdir -p "$RELEASE_DIR"
zip -r "$SCRIPT_DIR/$RELEASE_DIR/FRCR-Examiner-Windows-v${VERSION}.zip" \
    app.py \
    models.py \
    backup_*.py \
    requirements.txt \
    Procfile \
    README.md \
    HOW_TO_USE.md \
    CHANGELOG.md \
    CONTRIBUTING.md \
    templates/ \
    static/ \
    dist/windows/ \
    dist/icons/ \
    dist/INSTALLATION_GUIDE.md \
    dist/QUICK_START.md \
    dist/RELEASE_NOTES.md \
    -x "**/__pycache__/*" "**/*.pyc" "**/.DS_Store" "**/instance/*" "**/backups/*" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Windows package created"
else
    echo "✗ Failed to create Windows package"
fi

# Create SCRIPT_DIR/$macOS package
echo "[2/2] Creating macOS distribution package..."
zip -r "$RELEASE_DIR/FRCR-Examiner-macOS-v${VERSION}.zip" \
    app.py \
    models.py \
    backup_*.py \
    requirements.txt \
    Procfile \
    README.md \
    HOW_TO_USE.md \
    CHANGELOG.md \
    CONTRIBUTING.md \
    templates/ \
    static/ \
    dist/macos/ \
    dist/icons/ \
    dist/INSTALLATION_GUIDE.md \
    dist/QUICK_START.md \
    dist/RELEASE_NOTES.md \
    -x "**/__pycache__/*" "**/*.pyc" "**/.DS_Store" "**/instance/*" "**/backups/*" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ macOS package created"
else
    echo "✗ Failed to create macOS package"
fi

# Generate checksums
echo ""
echo "Generating checksums..."
cd "$SCRIPT_DIR/$RELEASE_DIR"
shasum -a 256 *.zip > checksums.txt
cd "$SCRIPT_DIR"

echo ""
echo "============================================"
echo "Distribution packages created successfully!"
echo "============================================"
echo ""
echo "Location: $SCRIPT_DIR/$RELEASE_DIR/"
echo ""
ls -lh "$SCRIPT_DIR/$RELEASE_DIR"
echo ""
echo "Files created:"
echo "  - FRCR-Examiner-Windows-v${VERSION}.zip"
echo "  - FRCR-Examiner-macOS-v${VERSION}.zip"
echo "  - checksums.txt"
echo ""
echo "Next steps:"
echo "  1. Test the packages on Windows and macOS"
echo "  2. Create a new release on GitHub"
echo "  3. Upload the ZIP files and checksums.txt"
echo "  4. Copy contents of dist/RELEASE_NOTES.md to release description"
echo ""
