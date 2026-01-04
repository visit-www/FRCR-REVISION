# 📱 FRCR Examiner - Desktop Application

**Version 2.0 - Standalone Desktop App**

A standalone, offline-first exam management system for FRCR (Fundamental Radiology Certificate Review) exams.

---

## 🎯 What's Included in This Package

```
FRCR_Examiner/
├── FRCR_Examiner.app (macOS)
├── FRCR_Examiner.exe (Windows)
├── QUICK_START_DESKTOP.md (Start here!)
└── DESKTOP_INSTALLATION_GUIDE.md (Detailed help)
```

---

## ⚡ Quick Start (3 Steps)

### **Step 1: Download**
- Mac: `FRCR_Examiner.app`
- Windows: `FRCR_Examiner.exe`


### **Step 2: Run**
- Mac: Right-click app → **Open**
- Windows: Double-click `.exe` file

---

### ⚠️  macOS Security Notice (Gatekeeper)

**If you see a message like:**
> "FRCR_Examiner.app cannot be opened because it is from an unidentified developer."

This is normal for apps not downloaded from the App Store.

**How to open the app:**
1. Open Finder and locate `FRCR_Examiner.app` (in Applications or Downloads)
2. Right-click (or Control-click) the app and select **Open**
3. In the dialog, click **Open** again
4. The app will launch

**If you still can't open it:**
1. Go to **System Settings** → **Privacy & Security**
2. Scroll down to "Security" section
3. You will see a message about "FRCR_Examiner.app was blocked..."
4. Click **Allow Anyway**
5. Try opening the app again (right-click → Open)

This only needs to be done the first time. After that, you can double-click to open normally.

### **Step 3: Use**
- App opens in your browser
- Create exam sessions
- Manage packets and cases
- Start exams with candidates

**That's it! No installation, no setup, no internet needed.**

---

## ✨ Key Features

✅ **Completely Free** - Download once, use forever  
✅ **Works Offline** - No internet needed  
✅ **Private** - All data stays on your computer  
✅ **Fast** - Runs locally, no network delays  
✅ **Simple** - Easy to use interface  
✅ **Portable** - Download on any computer  
✅ **Reliable** - SQLite database included  

---

## 📋 Features

- **Exam Sessions**: Create sessions with date and time
- **Packets**: Organize cases by packet (1-4)
- **Cases**: Add unlimited cases per packet with:
  - Diagnosis
  - Questions
  - Answers
  - Discussion/Comments
- **Candidates**: Manage exam takers
- **Session Management**: Full CRUD (Create, Read, Update, Delete)
- **Responsive Design**: Works on Windows, Mac, Linux
- **Data Backup**: Local SQLite database (easy to backup)

---

## 🚀 Installation

### **MacOS (Intel or Apple Silicon)**
1. Download `FRCR_Examiner.app`
2. Open Finder → Applications
3. Right-click `FRCR_Examiner.app`
4. Click **"Open"** (first time only)
5. Click **"Open"** in security dialog
6. App opens in browser at `http://localhost:5000`

**Next launches:** Just double-click the app

### **Windows 10/11**
1. Download `FRCR_Examiner.exe`
2. Double-click to run
3. If prompted "Windows protected your PC", click **"More info"** → **"Run anyway"**
4. App opens in browser at `http://localhost:5000`

### **Linux**
1. Download `FRCR_Examiner`
2. Run: `chmod +x FRCR_Examiner && ./FRCR_Examiner`
3. App opens at `http://localhost:5000`

---

## 💾 Your Data

### **Where is my data stored?**
- File: `instance/frcr_examiner.db`
- Location: Same folder as the app
- Format: SQLite database (portable, standard)
- Security: All local, never uploaded

### **How to backup?**
1. Copy `instance/frcr_examiner.db` file
2. Save to: USB drive, cloud storage, or email
3. Done! Monthly backups recommended

### **How to restore?**
1. Delete current `instance/frcr_examiner.db`
2. Copy backup file back
3. Restart app
4. Data restored!

---

## 🎓 Typical Workflow

### **Preparation Phase**
1. Open FRCR Examiner
2. Click **"Prepare for Exam"** tab
3. Create exam session (date + time)
4. Add packets (1, 2, 3, 4)
5. Add cases to each packet:
   - Diagnosis
   - Questions
   - Answers
   - Discussion
6. Save candidates

### **Management Phase**
1. Click **"Manage Sessions"** tab
2. Select session to edit
3. Modify packets/cases as needed
4. Add/remove candidates
5. Changes save automatically

### **Exam Phase**
1. Click **"Start Exam"** tab
2. Select exam session from dropdown
3. Select candidate to examine
4. Navigate through cases
5. Review questions, answers, discussion

---

## 🔧 System Requirements

| Item | Requirement |
|------|-------------|
| **OS** | Windows 7+, macOS 10.13+, Linux Ubuntu 18+ |
| **RAM** | 2 GB minimum, 4 GB recommended |
| **Disk Space** | 500 MB for app + database |
| **Internet** | Not required |
| **Browser** | Chrome, Firefox, or Safari (auto-opens) |

---

## ❓ FAQ

**Q: Do I need internet?**  
A: No! Completely offline application.

**Q: Is it secure?**  
A: Yes! Data never leaves your computer.

**Q: Can I use it on multiple computers?**  
A: Yes! Download on each computer. Each has its own database.

**Q: What if my computer crashes?**  
A: Restore from your backup file (stored elsewhere).

**Q: Is there a cost?**  
A: No! Free, forever.

**Q: Can I edit exams after creating them?**  
A: Yes! Click "Edit Session" to modify anything.

**Q: How many exams can I create?**  
A: Unlimited (limited only by disk space).

**Q: How many cases per packet?**  
A: Unlimited per packet.

**Q: Can my team use this together?**  
A: Each person downloads their own copy. Or one person runs app and team accesses via local network.

**Q: What if I find a bug?**  
A: Contact your institution's IT support.

---

## 📖 Documentation

Start with:
1. **QUICK_START_DESKTOP.md** - 2-minute overview
2. **DESKTOP_INSTALLATION_GUIDE.md** - Detailed help & troubleshooting

---

## 🎯 Version Info

**Version:** 2.0 Desktop  
**Release Date:** January 4, 2026  
**Type:** Standalone Desktop Application  
**Database:** SQLite (local)  
**Framework:** Flask + React (packaged as standalone)  

---

## 🔄 What's Different from Web Version?

| Feature | Web Version | Desktop App |
|---------|-------------|------------|
| Internet needed | Yes | No |
| Hosting cost | Yes (paid) | No |
| Data privacy | Cloud | Local |
| Setup required | Yes | No |
| Backup location | Cloud | Local |
| Team access | Shared URL | Same network or email |
| Offline access | No | Yes |
| Best for | Remote teams | Institutions, local use |

---

## 📞 Support

### **For Installation Issues:**
See `DESKTOP_INSTALLATION_GUIDE.md` - Troubleshooting section

### **For Usage Questions:**
See `QUICK_START_DESKTOP.md` - FAQ section

### **For Technical Help:**
Contact your institution's IT coordinator

---

## ✅ Getting Started

1. ✅ Download app for your OS
2. ✅ Run the app
3. ✅ Create first exam session
4. ✅ Add packets and cases
5. ✅ Add candidates
6. ✅ Start exam
7. ✅ Backup data monthly

---

## 🎉 Ready?

**Start by reading:** `QUICK_START_DESKTOP.md` (2 minutes)

**For detailed help:** `DESKTOP_INSTALLATION_GUIDE.md` (5-10 minutes)

**Then:** Launch app and create your first exam!

---

## 📝 License & Support

- **License**: Educational use
- **Support**: Through institution IT
- **Updates**: Contact administrator
- **Cost**: FREE (forever)

---

## 🚀 Key Advantages

✅ No internet required  
✅ No hosting costs  
✅ No subscription fees  
✅ Complete data privacy  
✅ Works on any computer  
✅ Easy to backup  
✅ Fast performance  
✅ Simple interface  

**Perfect for educational institutions!** 🎓

---

**Questions? See the documentation files included in this package.**

**Ready to start? Launch the app and enjoy!** 🚀
