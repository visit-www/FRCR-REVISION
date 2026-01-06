; NSIS Installer for FRCR Examiner
; Modern UI with professional look

!include "MUI2.nsh"

; Installer properties
Name "FRCR Examiner"
OutFile "..\FRCR-Examiner-Windows-v1.0.2.exe"
InstallDir "$PROGRAMFILES\FRCR-Examiner"
InstallDirRegKey HKLM "Software\FRCR-Examiner" "Install_Dir"

; UI Configuration
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

; Installer initialization
Function .onInit
    ; Check if Python 3 is installed
    ReadRegStr $0 HKLM "SOFTWARE\Python\PythonCore" ""
    ${If} $0 == ""
        MessageBox MB_YESNO "Python 3 is not detected on your system.$\n$\nFRCR Examiner requires Python 3.8 or higher.$\n$\nWould you like to visit the Python website to install it?" IDYES python_yes IDNO python_no
        python_yes:
            ExecShell "open" "https://www.python.org/downloads/"
            Quit
        python_no:
            MessageBox MB_OK "Please install Python 3 before installing FRCR Examiner."
            Quit
    ${EndIf}
FunctionEnd

; Installation section
Section "Install"
    SetOutPath "$INSTDIR"
    
    ; Copy application files
    File /r "app.py"
    File /r "models.py"
    File /r "backup_database.py"
    File /r "backup_manager.py"
    File /r "backup_scheduler.py"
    File /r "requirements.txt"
    File /r "Procfile"
    File /r "README.md"
    File /r "HOW_TO_USE.md"
    File /r "templates"
    File /r "static"
    File /r "dist"
    
    ; Install Python dependencies
    MessageBox MB_OK "Installing Python dependencies...$\nThis may take a few minutes."
    ExecWait '"cmd.exe" /c python -m pip install -r requirements.txt'
    
    ; Create desktop shortcut
    CreateDirectory "$SMPROGRAMS\FRCR Examiner"
    CreateShortcut "$SMPROGRAMS\FRCR Examiner\FRCR Examiner.lnk" "$INSTDIR\launch.bat"
    CreateShortcut "$DESKTOP\FRCR Examiner.lnk" "$INSTDIR\launch.bat"
    
    ; Create launch batch file
    FileOpen $0 "$INSTDIR\launch.bat" w
    FileWrite $0 "@echo off$\ncd /d `$INSTDIR`$\npython app.py$\npause"
    FileClose $0
    
    ; Write uninstall info
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\FRCR-Examiner" "DisplayName" "FRCR Examiner"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\FRCR-Examiner" "UninstallString" "$INSTDIR\uninstall.exe"
    WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

; Uninstaller section
Section "Uninstall"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\FRCR-Examiner"
    RMDir /r "$INSTDIR"
    RMDir /r "$SMPROGRAMS\FRCR Examiner"
    Delete "$DESKTOP\FRCR Examiner.lnk"
SectionEnd
