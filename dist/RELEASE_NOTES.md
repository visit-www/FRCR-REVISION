# FRCR Examiner Tool - Release Notes

## Version 1.0.0 - Production Release

### Overview
First production-ready release of FRCR Examiner Tool - a comprehensive application designed to help medical professionals prepare for FRCR viva examinations.

### Features

#### Core Functionality
- **Session Management**: Create and manage exam sessions with date, time, and details
- **Packet Management**: Organize cases into packets for structured examination
- **Case Management**: Add, edit, and view medical cases with images and descriptions
- **Candidate Management**: Register and track multiple candidates
- **Examination Mode**: Conduct live examinations with real-time case viewing
- **Backup & Restore**: Automated backup system with manual backup/restore capability

#### User Interface
- Modern, responsive design with soft color palette
- Intuitive navigation with breadcrumb trails
- Card-based layout for easy information access
- Mobile-friendly interface
- Image viewing with zoom and descriptions

#### Technical Features
- Local SQLite database for data storage
- All data stored on user's computer (privacy-focused)
- Cross-platform support (Windows & macOS)
- Easy installation with guided installers
- Desktop shortcuts and Start Menu integration
- Browser-based interface

### What's Included

#### Windows Package
- Automated installer (`install.bat`)
- Application launcher with desktop shortcut
- Complete application files
- Documentation

#### macOS Package
- Automated installer script (`install.sh`)
- Application bundle (.app)
- Application launcher
- Complete application files
- macOS security override guide
- Documentation

### Installation

See the included documentation:
- `QUICK_START.md` - Quick installation guide
- `INSTALLATION_GUIDE.md` - Comprehensive installation and usage guide

### System Requirements

**Windows:**
- Windows 10 or later
- Python 3.8 or higher
- 4GB RAM (8GB recommended)
- 500MB free space

**macOS:**
- macOS 10.14 (Mojave) or later
- Python 3.8 or higher
- 4GB RAM (8GB recommended)
- 500MB free space

### Known Issues

#### macOS
- First launch requires security override (documented in guide)
- Some antivirus software may flag the installer (false positive)

#### Windows
- Requires "Run as administrator" for installation
- Windows Defender may show SmartScreen warning (click "More info" → "Run anyway")

### Data Storage

All data is stored locally:
- **Windows**: `C:\Users\YourUsername\FRCR_Examiner\instance\`
- **macOS**: `~/Applications/FRCR_Examiner/instance/`

### Support

**Developer:** Dr Gaurav S.P Gupta, MBBS, MD, FRCR  
**Email:** lotusheart2016@gmail.com  
**GitHub Issues:** https://github.com/visit-www/Frcr-examiner/issues

### License

© 2026 FRCR Examiner Tool. All rights reserved.

---

## Changelog

### [1.0.0] - 2026-01-06

#### Added
- Initial production release
- Complete examination management system
- Windows installer with desktop integration
- macOS installer with app bundle
- Comprehensive documentation
- Backup and restore functionality
- Admin dashboard
- Soft, professional color scheme
- Responsive UI design

#### Technical
- Flask web framework
- SQLAlchemy ORM
- SQLite database
- Bootstrap 5 UI
- Font Awesome icons

---

Thank you for using FRCR Examiner Tool!
