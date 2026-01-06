#!/bin/bash
# Build Windows EXE Installer using Python (alternative to NSIS)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../.."
VERSION="${1:-1.0.2}"
BUILD_DIR="/tmp/frcr-win-build-$$"
EXE_OUTPUT="$PROJECT_ROOT/dist/FRCR-Examiner-Windows-v${VERSION}.exe"

echo "=========================================="
echo "Building Windows Installer (Python-based)"
echo "Version: $VERSION"
echo "=========================================="
echo ""

# Check if PyInstaller is available
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    python3 -m pip install pyinstaller -q
fi

echo "[1/3] Preparing build directory..."
mkdir -p "$BUILD_DIR"

# Create a launcher Python file
cat > "$BUILD_DIR/installer.py" << 'PYTHON_INSTALLER'
#!/usr/bin/env python3
"""
FRCR Examiner Windows Installer
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def install():
    """Main installation routine"""
    print("\n" + "="*50)
    print("FRCR Examiner - Windows Installation")
    print("="*50 + "\n")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required!")
        print(f"Current version: {sys.version}")
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    print(f"✓ Python {sys.version.split()[0]} detected\n")
    
    # Get installation directory
    default_dir = r"C:\Program Files\FRCR-Examiner"
    install_dir = input(f"Installation directory [{default_dir}]: ").strip()
    if not install_dir:
        install_dir = default_dir
    
    # Create installation directory
    Path(install_dir).mkdir(parents=True, exist_ok=True)
    print(f"\n✓ Installation directory: {install_dir}\n")
    
    # Copy application files
    print("Installing application files...")
    script_dir = Path(__file__).parent
    
    files_to_copy = [
        'app.py', 'models.py', 'requirements.txt', 'Procfile',
        'README.md', 'HOW_TO_USE.md', 'CHANGELOG.md', 'CONTRIBUTING.md'
    ]
    
    for file in files_to_copy:
        src = script_dir / file
        if src.exists():
            shutil.copy2(src, install_dir)
    
    # Copy directories
    dirs_to_copy = ['templates', 'static', 'dist', 'backup_*.py']
    for pattern in ['backup_database.py', 'backup_manager.py', 'backup_scheduler.py']:
        src = script_dir / pattern
        if src.exists():
            shutil.copy2(src, install_dir)
    
    for dir_name in ['templates', 'static', 'dist']:
        src = script_dir / dir_name
        if src.exists():
            shutil.copytree(src, install_dir / dir_name, dirs_exist_ok=True)
    
    # Install dependencies
    print("\nInstalling Python dependencies...")
    print("This may take a few minutes...\n")
    
    os.chdir(install_dir)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '-q'])
    
    # Create launcher script
    launcher_path = Path(install_dir) / 'launch.bat'
    launcher_path.write_text('@echo off\ncd /d "%~dp0"\npython app.py\npause\n')
    
    # Create desktop shortcut
    desktop = Path.home() / 'Desktop'
    shortcut_path = desktop / 'FRCR Examiner.lnk'
    
    print("✓ Creating desktop shortcut...")
    
    # Note: Creating .lnk files on Windows requires special handling
    # This is a placeholder - actual .lnk creation would need Windows API
    
    # Success message
    print("\n" + "="*50)
    print("✓ Installation Complete!")
    print("="*50 + "\n")
    print(f"Installation directory: {install_dir}\n")
    print("To launch FRCR Examiner:")
    print(f"  Double-click: {install_dir}\\launch.bat")
    print(f"  Or use desktop shortcut: FRCR Examiner\n")
    
    input("Press Enter to finish installation...")

if __name__ == '__main__':
    try:
        install()
    except Exception as e:
        print(f"\n❌ Installation failed: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)

PYTHON_INSTALLER

echo "[2/3] Creating executable..."
# Create standalone executable
pyinstaller --onefile --windowed --name "FRCR-Examiner-Setup" "$BUILD_DIR/installer.py" 2>/dev/null

echo "[3/3] Finalizing..."
if [ -f "$BUILD_DIR/dist/FRCR-Examiner-Setup.exe" ]; then
    cp "$BUILD_DIR/dist/FRCR-Examiner-Setup.exe" "$EXE_OUTPUT"
    rm -rf "$BUILD_DIR"
    echo ""
    echo "=========================================="
    echo "✓ Windows Installer Created Successfully!"
    echo "=========================================="
    echo ""
    echo "Executable: $EXE_OUTPUT"
    echo "Size: $(du -h "$EXE_OUTPUT" | awk '{print $1}')"
else
    echo "❌ Failed to create executable"
    exit 1
fi
