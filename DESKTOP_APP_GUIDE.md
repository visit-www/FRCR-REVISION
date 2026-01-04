# FRCR EXAMINER - Desktop App Guide

## 🖥️ Creating & Sharing as Desktop Application

This guide explains how to convert the Flask web app into a standalone desktop application that others can run on their computers without installing Python.

---

## 📋 Three Ways to Run & Share

### **1. Web App (Current - Easy Start)**
```bash
./run.sh
# Opens: http://localhost:5000
```
**Best for:** Quick testing, local use only

**Requirements:**
- Python 3.8+
- Pip & dependencies

---

### **2. Desktop App (Recommended - Easiest to Share)**
Convert to standalone executable that runs without Python.

**For macOS Users:**
```bash
# Build the app
chmod +x build_desktop_app.sh
./build_desktop_app.sh

# Output: dist/FRCR_Examiner
# Just double-click to run!
```

**For Windows Users:**
```bash
# Build the app
python -m pip install pyinstaller
pyinstaller --onefile --windowed app.py

# Output: dist/FRCR_Examiner.exe
# Just double-click to run!
```

**Sharing:**
1. Zip the entire `dist` folder
2. Send to anyone
3. They extract and run (no Python needed!)

---

### **3. Python Script (For Developers)**
```bash
python desktop_app.py
# Launches app in browser automatically
```

**Best for:** Developers who have Python installed

---

## 🚀 Step-by-Step: Build Desktop App (macOS)

### **Step 1: Install PyInstaller**
```bash
cd /Users/zen/myRepos/projects/FRCR_EXAMINER
pip install pyinstaller
```

### **Step 2: Build the App**
```bash
pyinstaller --onefile \
    --windowed \
    --name "FRCR_Examiner" \
    --add-data "templates:templates" \
    --add-data "static:static" \
    --hidden-import=flask \
    --hidden-import=flask_sqlalchemy \
    app.py
```

### **Step 3: Run Your Desktop App**
```bash
dist/FRCR_Examiner
```

### **Step 4: Share with Others**
```bash
# Create a zip file
zip -r FRCR_Examiner_macOS.zip dist/FRCR_Examiner

# Send FRCR_Examiner_macOS.zip to others
# They can unzip and run directly!
```

---

## 🖥️ Step-by-Step: Build Desktop App (Windows)

### **Step 1: Install PyInstaller**
```bash
cd /Users/zen/myRepos/projects/FRCR_EXAMINER
pip install pyinstaller
```

### **Step 2: Build the App**
```bash
pyinstaller --onefile --windowed --name "FRCR_Examiner" ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --hidden-import=flask ^
    --hidden-import=flask_sqlalchemy ^
    app.py
```

### **Step 3: Run Your Desktop App**
Double-click: `dist/FRCR_Examiner.exe`

### **Step 4: Share with Others**
```bash
# Create a zip file
# Compress dist\FRCR_Examiner.exe

# Send to others
# They extract and double-click to run!
```

---

## 🔧 Advanced: Desktop App with Native Window

Use the included `desktop_app.py` for better desktop integration:

```bash
python desktop_app.py
```

Features:
- ✅ Automatically opens in default browser
- ✅ Clean console output
- ✅ Professional appearance

**Convert to executable:**
```bash
pyinstaller --onefile --windowed desktop_app.py
dist/FRCR_Examiner
```

---

## 📦 What Gets Packaged?

When you build with PyInstaller, it includes:
- ✅ Python runtime
- ✅ All dependencies (Flask, SQLAlchemy, etc.)
- ✅ HTML templates
- ✅ CSS files
- ✅ Database engine
- ✅ All required libraries

**Size:** ~100-150 MB (includes entire Python environment)

---

## 💾 Distribution Methods

### **Method 1: ZIP File (Easiest)**
```bash
# Create zip
zip -r FRCR_Examiner_v1.0.zip dist/FRCR_Examiner

# Share via:
# - Email (if < 25MB, may need to split)
# - Google Drive
# - Dropbox
# - GitHub
# - OneDrive
```

### **Method 2: Installer (Professional)**
Create a professional installer with NSIS or Inno Setup:
```bash
pip install cx_Freeze
# Create custom installer
```

### **Method 3: GitHub Releases**
1. Build desktop app
2. Zip the dist folder
3. Go to GitHub repo → Releases
4. Create release & upload ZIP

### **Method 4: Direct Sharing**
```bash
# Just zip and send
zip -r FRCR_Examiner.zip dist/
# Send via email, cloud storage, etc.
```

---

## 🎯 Comparison: All 3 Options

| Feature | Web App | Desktop App | Python Script |
|---------|---------|-------------|----------------|
| Requires Python | ✅ Yes | ❌ No | ✅ Yes |
| Easy to Share | ⚠️ Medium | ✅ Very Easy | ⚠️ Medium |
| File Size | Small | ~120MB | Small |
| Startup Time | Fast | Slower (~5s) | Fast |
| Works Offline | ✅ Yes | ✅ Yes | ✅ Yes |
| Professional Look | ⚠️ Browser | ✅ Desktop | ⚠️ Browser |
| Update Process | ✅ Easy | ⚠️ Complex | ✅ Easy |
| Users Skills | Dev only | Anyone | Dev only |

---

## 🚨 Troubleshooting

### **Issue: "File not found" error**
```bash
# Ensure you're in the correct directory
cd /Users/zen/myRepos/projects/FRCR_EXAMINER

# Rebuild with correct data paths
pyinstaller --onefile --windowed \
    --add-data "templates:templates" \
    --add-data "static:static" \
    app.py
```

### **Issue: Port 5000 in use**
Edit `app.py` last line:
```python
app.run(debug=False, host='localhost', port=5001)
```

### **Issue: Database not found**
The app auto-creates the database. If issues occur:
```bash
# Delete old database
rm instance/frcr_examiner.db

# Rebuild and run
pyinstaller --onefile --windowed app.py
dist/FRCR_Examiner
```

### **Issue: App won't start**
```bash
# Try running in terminal to see errors
python app.py

# Check logs and fix issues, then rebuild
```

---

## 📋 Recommended Setup for Sharing

**Best Practice:**
1. Test the web app locally
2. Build desktop app with PyInstaller
3. Create ZIP with both options:
   - `dist/FRCR_Examiner` (macOS/Linux)
   - `dist/FRCR_Examiner.exe` (Windows)
   - `run.sh` (for developers)
4. Include README with instructions
5. Share ZIP via GitHub Releases

**Users then:**
1. Download ZIP
2. Extract folder
3. Double-click executable
4. App runs!

---

## 🔄 Version Updates

When you update the app:

**For Web App:**
```bash
git commit -m "Update features"
git push
# Users pull latest code
```

**For Desktop App:**
```bash
# Update source code
# Rebuild: pyinstaller --onefile --windowed app.py
# Create new ZIP: FRCR_Examiner_v1.1.zip
# Upload to GitHub Releases
# Users download new version
```

---

## 💡 Pro Tips

1. **Icon for Desktop App:**
   ```bash
   pyinstaller --onefile --windowed \
       --icon=app_icon.icns \  # macOS
       app.py
   ```

2. **Hide Console (Windows):**
   Already using `--windowed` flag does this

3. **Add Splash Screen:**
   Create custom launcher with images

4. **Auto-Update:**
   Add update checker in app.py

---

## 📞 Quick Reference

| Task | Command |
|------|---------|
| Start web app | `./run.sh` |
| Run Python launcher | `python desktop_app.py` |
| Build desktop app | `chmod +x build_desktop_app.sh && ./build_desktop_app.sh` |
| Run built app (macOS) | `dist/FRCR_Examiner` |
| Run built app (Windows) | `dist\FRCR_Examiner.exe` |
| Share app | Zip `dist` folder |
| Clean build files | `rm -rf build dist` |

---

## 🎓 Which Option to Choose?

**Use Web App (./run.sh) if:**
- Users have Python installed
- You're developing/testing
- Quick deployment needed

**Use Desktop App (PyInstaller) if:**
- Users don't have Python
- Want professional distribution
- Need to share with non-technical users
- Want standalone executable

**Use Python Script (desktop_app.py) if:**
- Target audience is developers
- Want better error messages
- Easier debugging

---

## ✅ Summary

Your FRCR Examiner app can now be:
- ✅ Run as web app (Flask)
- ✅ Shared as desktop app (PyInstaller)
- ✅ Packaged as ZIP
- ✅ Distributed on GitHub
- ✅ Run locally without internet

**All with the same codebase!**

---

## 📚 Next Steps

1. **Test Web App:** `./run.sh`
2. **Try Python Script:** `python desktop_app.py`
3. **Build Desktop App:** `./build_desktop_app.sh`
4. **Share with Others:** Zip and send

**That's it!** Your app is now ready for distribution. 🚀

---

Created: January 2, 2026
Version: 1.0 Desktop Guide
