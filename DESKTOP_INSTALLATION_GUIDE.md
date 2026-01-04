# 📱 FRCR Examiner - Desktop Installation Guide

## ✅ What You're Getting

A **standalone desktop application** for managing FRCR exam sessions, packets, cases, and candidates.

- **No installation needed** (just download and run)
- **Works completely offline**
- **All data stored on your computer**
- **Free forever** (no subscriptions)
- **No internet required**

---

## 🖥️ Installation by Operating System

### **Windows Users**

#### Step 1: Download
1. Go to your email or file share
2. Find file named: `FRCR_Examiner.exe` or `FRCR_Examiner_Windows.zip`
3. Download to your computer

#### Step 2: Run
1. **Option A (Direct)**: Double-click `FRCR_Examiner.exe`
2. **Option B (If zipped)**: Extract zip file, then double-click `FRCR_Examiner.exe`

#### Step 3: Wait for App to Start
- First launch takes 10-15 seconds
- Your default browser will open automatically
- Application loads at: `http://localhost:5000`
- You see the FRCR Examiner home page

#### Step 4: Start Using
- Click **"Prepare for Exam"** tab
- Create exam session with date and time
- Add packets and cases
- Start exam when ready

#### Troubleshooting (Windows):
| Issue | Solution |
|-------|----------|
| "Windows protected your PC" | Click **"More info"** → **"Run anyway"** |
| App doesn't open | Right-click → **"Run as Administrator"** |
| Browser doesn't open | Manually go to `http://localhost:5000` |
| Port 5000 in use | Close other apps, restart computer |

---

### **Mac Users (Intel or Apple Silicon)**

#### Step 1: Download
1. Receive `FRCR_Examiner.app` file
2. Download to your computer (usually in Downloads folder)

#### Step 2: Move to Applications (Optional but Recommended)
1. Open Finder
2. Go to Downloads folder
3. Right-click `FRCR_Examiner.app`
4. Select **"Move to Applications"**
5. Or just keep in Downloads folder (either works)


#### Step 3: Run the App
**First Time Only:**
1. Open Finder → Applications (or Downloads)
2. Right-click `FRCR_Examiner.app`
3. Click **"Open"** (do NOT double-click)
4. Click **"Open"** in the security dialog
5. If you see a message like "FRCR_Examiner.app cannot be opened because it is from an unidentified developer":
   - Go to **System Settings** → **Privacy & Security**
   - Scroll down to the Security section
   - You will see a message about "FRCR_Examiner.app was blocked..."
   - Click **Allow Anyway**
   - Try opening the app again (right-click → Open)
6. App starts and browser opens

**After First Time:**
- Just double-click `FRCR_Examiner.app` to launch

#### Step 4: Start Using
- Application loads at: `http://localhost:5000`
- See the FRCR Examiner home page
- Click **"Prepare for Exam"** tab
- Create and manage exam sessions

#### Troubleshooting (Mac):
| Issue | Solution |
|-------|----------|
| "Cannot open FRCR_Examiner" | Right-click → **"Open"** (not double-click) |
| "Verify app" message | Click **"Open"** in security dialog |
| App won't start | Check System Preferences → Security & Privacy |
| Browser won't open | Manually open browser, go to `http://localhost:5000` |

---

### **Linux Users**

#### Step 1: Download
1. Get file: `FRCR_Examiner_Linux.tar.gz` or similar
2. Extract: `tar -xzf FRCR_Examiner_Linux.tar.gz`

#### Step 2: Run
```bash
./FRCR_Examiner
```

#### Step 3: Access
- Application starts
- Open browser
- Go to: `http://localhost:5000`

---

## 🎯 First Time Setup

Once the app opens in your browser:

### **Step 1: Create Exam Session**
1. Click **"Prepare for Exam"** tab
2. Enter exam date (e.g., 05 Jan 2026)
3. Enter exam time (e.g., 14:30)
4. Click **"Create Exam Session"**

### **Step 2: Add Packets**
1. In the form below, enter:
   - Packet Number: 1, 2, 3, or 4
   - Packet ID: e.g., "FORM001"
2. Click **"Add Packet"**
3. Repeat for all packets

### **Step 3: Add Cases**
1. For each packet:
   - Enter Case Number: 1, 2, or 3
   - Enter Diagnosis
   - Enter Questions
   - Enter Answers
   - Enter Discussion/Comments
2. Click **"Save Case"**

### **Step 4: Add Candidates**
1. In Manage Candidates section
2. Enter candidate name and number
3. Click **"Add Candidate"**

### **Step 5: Start Exam**
1. Click **"Start Exam"** tab
2. Select candidate from dropdown
3. Click **"Select Candidate"**
4. Navigate through packets and cases
5. Read questions, answers, and discussion

---

## 📊 Using Your Exam Sessions

### **View Sessions**
- Click **"Manage Sessions"** tab
- See all created exam sessions
- Shows date, time, and number of packets

### **Edit Sessions**
- Click **"Edit Session"** button
- Modify or add packets and cases
- Add or remove candidates
- Changes saved immediately

### **Running Exams**
- Click **"Start Exam"** tab
- Select exam session from dropdown
- Select candidate
- View packets and cases
- Navigate with buttons

---

## 💾 Backing Up Your Data

**Your data is stored in:** `instance/frcr_examiner.db`

### **Create a Backup**
1. Open Finder (Mac) or File Explorer (Windows)
2. Navigate to FRCR Examiner folder
3. Find `instance` folder
4. Copy `frcr_examiner.db` file
5. Save to: USB drive, cloud storage, or email
6. Date the backup: `backup_Jan_4_2026.db`

### **Restore from Backup**
1. Locate the backup file: `frcr_examiner.db`
2. Open FRCR Examiner folder
3. Delete old `instance/frcr_examiner.db` file
4. Copy backup file into `instance` folder
5. Restart FRCR Examiner
6. Your old data is restored!

---

## 🔧 Common Issues & Solutions

### **"App won't open" (All Platforms)**
```
Solution: Restart computer and try again
```

### **"Browser doesn't load app" (All Platforms)**
```
Solution: 
1. Make sure app is running
2. Open browser manually
3. Go to: http://localhost:5000
4. If still blank, wait 5 seconds and refresh
```

### **"Lost my data" (All Platforms)**
```
Solution: Check instance/frcr_examiner.db exists
If missing, restore from backup
If no backup, data cannot be recovered
(Always backup monthly!)
```

### **"Can't find FRCR Examiner.app" (Mac)**
```
Solution: 
1. Check Downloads folder first
2. Check Applications folder
3. Look in recent files (Cmd + Shift + Recent)
```

### **"Port 5000 in use" (All Platforms)**
```
Solution:
1. Close FRCR Examiner completely
2. Restart computer
3. Open FRCR Examiner again
If issue persists:
- Close other apps (Skype, Slack, etc.)
- They might be using port 5000
```

---

## ❓ Frequently Asked Questions

**Q: Is this safe to use?**  
A: Yes! All data stays on your computer. No internet connection needed.

**Q: Can I use this on multiple computers?**  
A: Yes! Download on each computer. Each has its own database.

**Q: Can my team access the app together?**  
A: If on same network: Yes! Run on one computer, others access via IP address on same network.

**Q: What if I update the app?**  
A: Download new version. Your old data stays in the database file.

**Q: Do I need internet to use this?**  
A: No! Completely offline application.

**Q: Is there a cost?**  
A: No! Free and always free.

**Q: Where is my data stored?**  
A: In the `instance/frcr_examiner.db` file (SQLite database) on your computer.

**Q: Can I export my data?**  
A: You can backup the `frcr_examiner.db` file. Export feature coming soon.

**Q: What if my computer crashes?**  
A: Restore from your backup file. Always backup monthly!

---

## 🚀 Getting Started Checklist

- [ ] Downloaded FRCR_Examiner app
- [ ] Installed/Extracted app on computer
- [ ] Launched app successfully
- [ ] App opened in browser at http://localhost:5000
- [ ] Created first exam session
- [ ] Added packets
- [ ] Added cases to packets
- [ ] Added candidate
- [ ] Started an exam
- [ ] Backed up database file to safe location
- [ ] Ready to use! 🎉

---

## 📞 Support & Help

### **If app won't start:**
1. Restart computer
2. Try double-clicking app again
3. Check System Preferences (Mac) or Windows Defender (Windows)

### **If data is missing:**
1. Check backup files
2. Restore from recent backup

### **If you have suggestions:**
Contact: Your institution's IT coordinator

---

## 📋 System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **OS** | Windows 7+ / Mac 10.13+ / Linux Ubuntu 18+ | Windows 10+ / Mac 11+ / Linux Ubuntu 20+ |
| **RAM** | 2 GB | 4 GB |
| **Disk Space** | 500 MB | 1 GB |
| **Internet** | Not required | Not required |
| **Browser** | Chrome, Firefox, Safari | Chrome or Firefox |

---

## ✅ You're All Set!

Your FRCR Examiner desktop app is ready to use.

**Next Steps:**
1. Create your first exam session
2. Add packets and cases
3. Start managing exams locally
4. Backup your data monthly
5. Share with colleagues (they download their own copy)

**Questions?** Refer to the sections above or contact your institution's IT support.

Happy exam managing! 🎓
