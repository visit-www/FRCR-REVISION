"""
PyInstaller Build Script for FRCR Examiner
Creates standalone executables for Windows and macOS with custom installers
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

class FRCRBuilder:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.dist_dir = self.project_root / 'dist'
        self.build_dir = self.project_root / 'build'
        self.spec_file = self.project_root / 'frcr_examiner.spec'
        
    def cleanup(self):
        """Clean previous builds"""
        print("🧹 Cleaning previous builds...")
        for dir_path in [self.dist_dir, self.build_dir]:
            if dir_path.exists():
                shutil.rmtree(dir_path)
                print(f"   Removed {dir_path}")
    
    def create_spec_file(self):
        """Create PyInstaller spec file for FRCR Examiner"""
        print("📝 Creating PyInstaller spec file...")
        
        spec_content = '''# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec for FRCR Examiner
Builds standalone Flask application
"""

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('static', 'static'),
        ('templates', 'templates'),
        ('instance', 'instance'),
    ],
    hiddenimports=[
        'flask',
        'flask_sqlalchemy',
        'sqlalchemy',
        'werkzeug',
        'jinja2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FRCR-Examiner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='static/app-icon.icns',  # macOS icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FRCR-Examiner',
)

# macOS app bundle
app = BUNDLE(
    coll,
    name='FRCR-Examiner.app',
    icon='static/app-icon.icns',
    bundle_identifier='com.frcr.examiner',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'CFBundleVersion': '2.0.0',
        'CFBundleShortVersionString': '2.0.0',
    },
)
'''
        
        with open(self.spec_file, 'w') as f:
            f.write(spec_content)
        print(f"   ✓ Created {self.spec_file}")
    
    def build_executable(self):
        """Build the executable using PyInstaller"""
        print("\n🔨 Building executable...")
        
        # Use venv pyinstaller
        venv_pyinstaller = self.project_root / 'build_env' / 'bin' / 'pyinstaller'
        
        if not venv_pyinstaller.exists():
            print(f"   ✗ PyInstaller not found at {venv_pyinstaller}")
            return False
        
        cmd = [
            str(venv_pyinstaller),
            str(self.spec_file),
            '--distpath', str(self.dist_dir),
            '--workpath', str(self.build_dir),
        ]
        
        try:
            result = subprocess.run(cmd, cwd=str(self.project_root), check=True)
            print("   ✓ Build completed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"   ✗ Build failed: {e}")
            return False
    
    def create_macos_dmg(self):
        """Create DMG installer for macOS"""
        print("\n📦 Creating macOS DMG installer...")
        
        app_path = self.dist_dir / 'FRCR-Examiner.app'
        dmg_path = self.dist_dir / 'FRCR-Examiner-v2.0.0-macOS.dmg'
        
        if not app_path.exists():
            print(f"   ✗ App bundle not found at {app_path}")
            return False
        
        # Create temporary DMG folder structure
        dmg_staging = self.dist_dir / 'dmg_staging'
        dmg_staging.mkdir(exist_ok=True)
        
        # Copy app to staging area
        shutil.copytree(app_path, dmg_staging / 'FRCR-Examiner.app', dirs_exist_ok=True)
        
        # Create Applications symlink for drag-and-drop
        (dmg_staging / 'Applications').symlink_to('/Applications', target_is_directory=True)
        
        # Create DMG
        cmd = [
            'hdiutil', 'create', '-volname', 'FRCR-Examiner',
            '-srcfolder', str(dmg_staging),
            '-ov', '-format', 'UDZO',
            str(dmg_path)
        ]
        
        try:
            subprocess.run(cmd, check=True)
            print(f"   ✓ Created {dmg_path.name}")
            shutil.rmtree(dmg_staging)
            return True
        except subprocess.CalledProcessError as e:
            print(f"   ✗ DMG creation failed: {e}")
            return False
    
    def create_macos_installer_script(self):
        """Create standalone shell script installer (no .app wrapper to trigger warning)"""
        print("\n🎨 Creating macOS installer script...")
        
        # Copy the shell script installer from project root
        source_script = self.project_root / 'macos_installer.sh'
        dest_script = self.dist_dir / 'install.sh'
        
        if source_script.exists():
            shutil.copy2(source_script, dest_script)
            os.chmod(dest_script, 0o755)
            print(f"   ✓ Created {dest_script.name}")
            return True
        else:
            print(f"   ⚠️  Source script not found: {source_script}")
            print(f"      Skipping installer script creation")
            return False
    
    def create_windows_installer(self):
        """Create Windows installer"""
        print("\n📦 Creating Windows installer...")
        print("   (Setup requires NSIS - will create batch installer instead)")
        
        # For now, create a batch installer
        batch_installer = '''@echo off
REM FRCR Examiner Windows Installer

setlocal enabledelayedexpansion

title FRCR Examiner Installation Wizard
color 0B

cls
echo ============================================================
echo  FRCR EXAMINER v2.0 - WINDOWS INSTALLATION WIZARD
echo ============================================================
echo.
echo Welcome to FRCR Examiner Installation!
echo.
echo This installer will guide you through the setup process.
echo.
pause

cls
echo ============================================================
echo  FRCR EXAMINER INSTALLATION
echo ============================================================
echo.
echo [1/2] Installing FRCR Examiner...
echo.

set "INSTALLER_DIR=%~dp0"
set "APP_SOURCE=%INSTALLER_DIR%FRCR-Examiner.exe"
set "START_MENU=%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs"
set "DESKTOP=%USERPROFILE%\\Desktop"

if not exist "!APP_SOURCE!" (
    echo Error: FRCR-Examiner.exe not found in current directory
    pause
    exit /b 1
)

REM Copy to Program Files
set "INSTALL_DIR=%ProgramFiles%\\FRCR-Examiner"
if not exist "!INSTALL_DIR!" mkdir "!INSTALL_DIR!"

echo Copying application files...
copy "!APP_SOURCE!" "!INSTALL_DIR!" >nul

if %ERRORLEVEL% equ 0 (
    echo Installation successful!
) else (
    echo Installation failed!
    pause
    exit /b 1
)

REM Create desktop shortcut
echo Creating desktop shortcut...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\\FRCR-Examiner.lnk'); $s.TargetPath = '%INSTALL_DIR%\\FRCR-Examiner.exe'; $s.Save()"

cls
echo ============================================================
echo  INSTALLATION COMPLETE
echo ============================================================
echo.
echo [2/2] Setup finished successfully!
echo.
echo FRCR Examiner has been installed to:
echo   %INSTALL_DIR%
echo.
echo A desktop shortcut has been created.
echo.
echo You can now run FRCR Examiner by:
echo   1. Double-clicking the desktop shortcut, OR
echo   2. Opening it from Start Menu
echo.
echo Thank you for installing FRCR Examiner!
echo.
pause
'''
        
        batch_path = self.dist_dir / 'install.bat'
        with open(batch_path, 'w') as f:
            f.write(batch_installer)
        
        print(f"   ✓ Created {batch_path.name}")
        return True
    
    def build_all(self):
        """Build everything"""
        print("🚀 Starting FRCR Examiner PyInstaller Build\n")
        
        self.cleanup()
        self.create_spec_file()
        
        if not self.build_executable():
            print("\n❌ Build failed!")
            return False
        
        print("\n✅ Build completed!")
        print(f"\n📍 Output directory: {self.dist_dir}")
        
        # Create installers
        self.create_macos_installer_script()
        self.create_windows_installer()
        
        print("\n" + "="*60)
        print("✅ ALL BUILDS COMPLETED SUCCESSFULLY!")
        print("="*60)
        print(f"\nOutput Files:")
        print(f"  📁 {self.dist_dir}")
        print(f"\nmacOS Installation Files:")
        print(f"  • FRCR-Examiner.app (executable)")
        print(f"  • install.sh (installer script - NO WARNING TRIGGER)")
        print(f"\nWindows Installation Files:")
        print(f"  • FRCR-Examiner.exe (executable)")
        print(f"  • install.bat (installer)")
        print(f"\nHow Users Install:")
        print(f"\nmacOS (NO GATEKEEPER WARNING ON INSTALLER):")
        print(f"  1. Download ZIP and extract")
        print(f"  2. Double-click install.sh (or open Terminal: bash install.sh)")
        print(f"  3. Follow the wizard")
        print(f"  4. When launching app: Right-click → Open (bypass warning)")
        print(f"  5. Done!")
        print(f"\nWindows:")
        print(f"  1. Download ZIP and extract")
        print(f"  2. Double-click install.bat")
        print(f"  3. Follow the wizard")
        print(f"  4. Done!")
        print(f"\nNext Steps:")
        print(f"  1. Test on clean macOS system")
        print(f"  2. Test on clean Windows system")
        print(f"  3. Create DMG for macOS:")
        print(f"     hdiutil create -volname 'FRCR-Examiner' -srcfolder dist -ov -format UDZO FRCR-Examiner.dmg")
        print(f"  4. Create ZIP for Windows")
        print(f"  5. Upload to GitHub releases")


if __name__ == '__main__':
    builder = FRCRBuilder()
    success = builder.build_all()
    sys.exit(0 if success else 1)
