# FRCR Examiner - Quick Installation Guide for Colleagues

## ⚡ Quick Installation (60 seconds)

### Step 1: Download
Download: **FRCR-Examiner-Installer-1.0.0.dmg**
[Get from GitHub Release](https://github.com/visit-www/Frcr-examiner/releases)

### Step 2: Install (pick ONE method)

**🖱️ Method A: One-Click (Easiest - No Terminal)**
```
1. Double-click the DMG file
2. Double-click "Install FRCR Examiner.command"
3. Wait for completion
4. Done! ✨
```

**💻 Method B: Terminal**
```bash
# Open Terminal and paste:
bash /Volumes/FRCR\ Examiner\ Installer/install.sh
```

**🎯 Method C: Manual**
```
1. Drag the app to Applications folder
2. Run the app
3. Done!
```

### Step 3: Launch
- Open **Applications** folder
- Double-click **FRCR Examiner**
- Enjoy! 🎉

---

## ⚠️ If You See a Security Warning

### Option A: Simple (One-time only)
1. Right-click the app
2. Select "Open"
3. Click "Open" again
4. Never see the warning again ✓

### Option B: Terminal Fix (Permanent)
```bash
sudo xattr -rd com.apple.quarantine "/Applications/FRCR Examiner.app"
```

---

## 🚀 First Launch

- **App takes 5-10 seconds to start** (creating database)
- Flask server initializes automatically
- Just wait - it will appear!

---

## ❓ Troubleshooting

**"Permission denied"**
→ Right-click the .command file → Open

**"Cannot connect to server"**
→ Wait 10 seconds → Try again

**"Database error"**
→ Delete: `~/Library/Application Support/FRCR Examiner/instance/`
→ Restart app (database will recreate)

---

## 📚 More Help

See the full guides:
- **[INSTALLER_GUIDE.md](INSTALLER_GUIDE.md)** - Detailed instructions
- **[COLLEAGUE_SETUP.md](COLLEAGUE_SETUP.md)** - User-friendly guide
- **[GitHub Issues](https://github.com/visit-www/Frcr-examiner/issues)** - Report problems

---

## ✨ That's It!

No Python, no Node.js, no terminal needed.
Just download, install, and use!

**Enjoy FRCR Examiner! 🎉**
