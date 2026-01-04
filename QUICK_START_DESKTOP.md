# ⚡ FRCR Examiner - Quick Start (2 Minutes)

## 📥 Download & Install

### **Mac:**
1. Download: `FRCR_Examiner.app`
2. Open Finder → Applications
3. Right-click `FRCR_Examiner.app` → **Open**
4. Click **Open** in security dialog
5. ✅ App launches in browser

### **Windows:**
1. Download: `FRCR_Examiner.exe`
2. Double-click `FRCR_Examiner.exe`
3. If warning appears, click **"Run anyway"**
4. ✅ App launches in browser

### **Linux:**
1. Download: `FRCR_Examiner`
2. Run: `./FRCR_Examiner`
3. ✅ App launches at `http://localhost:5000`

---

## 🎯 First 5 Minutes

### **Minute 1: Create Exam**
- Click **"Prepare for Exam"** tab
- Enter date: e.g., `05 Jan 2026`
- Enter time: e.g., `14:30`
- Click **"Create Exam Session"**

### **Minute 2: Add Packets**
- Enter Packet Number: `1`
- Enter Packet ID: `FORM001`
- Click **"Add Packet"**
- Repeat for packets 2, 3, 4

### **Minute 3: Add Cases**
- Click **"+ Add Case"** in packet 1
- Fill in:
  - Case #: `1`
  - Diagnosis: `Type your diagnosis`
  - Questions: `Type your questions`
  - Answers: `Type your answers`
  - Discussion: `Add comments`
- Click **"Save Case"**

### **Minute 4: Add Candidate**
- Scroll to **Manage Candidates**
- Name: `Dr. John Smith`
- Number: `1`
- Click **"Add Candidate"**

### **Minute 5: Start Exam**
- Click **"Start Exam"** tab
- Select candidate dropdown
- Select exam session
- Click **"Select Candidate"**
- ✅ Ready to view cases!

---

## 🔑 Key Features

| Feature | Location | Use |
|---------|----------|-----|
| Create exam | "Prepare for Exam" tab | Set date/time |
| Manage sessions | "Manage Sessions" tab | Edit packets/cases |
| Start exam | "Start Exam" tab | View cases |
| Add packets | Session management | Create packet groups |
| Add cases | Within packets | Create individual cases |
| Add candidates | Session management | Register exam takers |
| Edit anything | Click "Edit" button | Modify anytime |
| Delete anything | Click "Delete" button | Remove anytime |

---

## 💾 Backup Your Data

**Monthly backup (30 seconds):**
1. Open file explorer
2. Go to FRCR Examiner folder
3. Copy `instance/frcr_examiner.db`
4. Paste to: USB drive or cloud storage
5. Label: `backup_Jan_2026.db`

**If data is lost:**
1. Get backup file
2. Delete `instance/frcr_examiner.db`
3. Paste backup file back
4. Restart app
5. ✅ Data restored!

---

## ⚙️ Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Go back | Browser back button |
| Refresh | Cmd/Ctrl + R |
| Edit candidate | Click Edit button |
| Delete candidate | Click Delete button |
| Add case | Click + Add Case |
| View case | Click case number |

---

## ❓ Quick Help

**App won't start?**  
→ Restart computer, try again

**Can't find app?**  
→ Check Downloads and Applications folder

**Data missing?**  
→ Restore from backup (see Backup section)

**Browser won't load?**  
→ Go manually to: `http://localhost:5000`

**Port in use?**  
→ Restart computer

---

## 📊 What Gets Stored

| Item | Location | Backup? |
|------|----------|---------|
| Exam sessions | Database | Yes, backup monthly |
| Packets | Database | Yes |
| Cases | Database | Yes |
| Candidates | Database | Yes |
| Settings | Local | Yes |

**Location:** `instance/frcr_examiner.db`

---

## 🎓 Typical Workflow

```
1. Prepare → Create exam sessions, add packets and cases
2. Manage → Edit sessions, add candidates, adjust cases  
3. Conduct → Start exam, select candidate, view cases
4. Repeat → Create new sessions for each exam date
```

---

## ✅ You're Ready!

Everything is set up. Start creating exam sessions and managing candidates.

**Remember:** Backup your data monthly! 🔒

---

## 🚀 Full Documentation

See `DESKTOP_INSTALLATION_GUIDE.md` for detailed help on:
- Troubleshooting
- Detailed installation steps
- FAQ section
- System requirements

**Questions?** Refer to full guide or contact your IT administrator.

Good luck! 🎉
