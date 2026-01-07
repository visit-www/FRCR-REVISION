# FRCR Examiner - User Guide

## 📱 What is FRCR Examiner?

FRCR Examiner is a web-based application designed to help medical examiners prepare and conduct FRCR (Fellowship of the Royal College of Radiologists) viva examinations. The app works seamlessly on **desktop, tablet, and mobile devices** - allowing you to create, edit, and view exam cases anywhere, anytime.

**Live App**: https://frcr-examiner.vercel.app

---

## 🚀 Quick Start

### Demo Access
Try the app immediately with our demo account:
- **Email**: workinguser@gmail.com
- **Password**: Password@1234

### First Time Setup
1. **Visit**: https://frcr-examiner.vercel.app
2. **Register**: Click "Register" and create your account (first user becomes admin)
3. **Login**: Use your credentials to access the dashboard

---

## ✨ Key Features

### 📋 Complete Exam Management
- **Create Exam Sessions**: Set up exam dates and times
- **Organize Packets**: Group cases into exam packets
- **Manage Cases**: Add diagnosis, questions, answers, and discussion notes
- **Upload Images**: Attach radiology images to cases
- **Track Candidates**: Assign candidates to specific packets

### 📱 Mobile-First Design
- **Responsive Interface**: Works perfectly on phones, tablets, and desktops
- **Touch-Optimized**: Large buttons and touch-friendly navigation
- **On-the-Go Editing**: Create and edit cases directly from your mobile
- **Quick View**: Review cases during exams on your phone or tablet

### 💾 Data Safety
- **Automatic Backup Reminders**: Get notified every 24 hours
- **One-Click Backup**: Download your entire database as JSON
- **Easy Restore**: Upload and restore from any backup file
- **Offline Storage**: Keep backups on your device or cloud storage

### 🔐 Security
- **Password Protected**: Secure authentication system
- **Admin Controls**: First registered user has admin privileges
- **Data Encryption**: Passwords are hashed and never stored in plain text
- **Session Management**: Automatic logout for security

---

## 📖 How to Use

### 1️⃣ Dashboard
After login, you'll see four main sections:
- **Setup Workflows**: Create and manage exam sessions
- **Exam Workflow**: Start examining candidates
- **Backup Manager**: Download and restore your data
- **Profile**: Manage your account

### 2️⃣ Setup Workflow

#### Create an Exam Session
1. Click **"Setup Workflows"** → **"Manage Sessions"**
2. Click **"+ New Session"**
3. Enter:
   - Exam Date
   - Exam Time
   - Session Name
4. Click **"Create Session"**

#### Add Packets to Session
1. Select your session
2. Click **"Add Packet"**
3. Enter packet number (e.g., A, B, C)
4. Click **"Save"**

#### Create Cases in Packet
1. Open a packet
2. Click **"+ Add New Case"**
3. Fill in:
   - **Diagnosis**: The case diagnosis
   - **Questions & Answers**: Add Q&A pairs (click "+" to add more)
   - **Discussion**: Additional notes or discussion points
4. Click **"Save Case"**

#### Upload Case Images
1. Open a case
2. Scroll to **"Images"** section
3. Click **"Choose Files"** or drag & drop
4. Add image description (optional)
5. Images upload automatically

#### Add Candidates
1. Go to **"Setup"** → **"Candidates"**
2. Click **"+ Add Candidate"**
3. Enter candidate details
4. Assign to packet
5. Click **"Save"**

### 3️⃣ Exam Workflow

#### Start Examination
1. Click **"Exam Workflow"** on dashboard
2. Select candidate
3. Their assigned packet and cases load automatically

#### During Examination
- **View Cases**: Navigate through cases in the packet
- **Review Images**: Tap to enlarge images
- **Read Q&A**: All questions and answers are displayed
- **Discussion Notes**: See examiner notes and comments

#### Edit During Exam (Mobile-Friendly)
- Click **"Edit Case"** button
- Make changes on your phone/tablet
- Save instantly
- Continue examination

### 4️⃣ Backup & Data Management

#### Download Backup (Recommended: Daily)
1. Click **"Backup"** in top navigation
2. Click **"Download Backup Now"**
3. File downloads to your device
4. **Filename**: `frcr_examiner_backup_YYYYMMDD_HHMMSS.json`

#### Restore from Backup
1. Go to **"Backup Manager"**
2. Scroll to **"Restore from Backup"**
3. Click **"Choose File"** and select backup
4. Check confirmation box
5. Click **"Restore Database"**
6. ⚠️ **Warning**: This overwrites current data (except user accounts)

#### Backup Best Practices
- **Download daily** before making major changes
- **Keep last 5 backups** on your device
- **Upload weekly** to cloud storage (Google Drive, Dropbox)
- **Test restore** occasionally to ensure backups work

---

## 📱 Mobile Usage Guide

### Creating Cases on Mobile
1. **Tap** "Setup Workflows"
2. **Select** your session and packet
3. **Tap** "+ Add New Case"
4. **Type** diagnosis (auto-saves)
5. **Add** Q&A pairs with "+" button
6. **Save** when complete

### Editing Cases on Mobile
1. **Open** the case
2. **Tap** "Edit Case" (bottom of screen)
3. **Make changes** in the modal
4. **Save** changes
5. **Large buttons** make it easy to tap

### Viewing Images on Mobile
1. **Scroll** to Images section
2. **Tap** image to view full-size
3. **Pinch to zoom** on image
4. **Swipe** to close

### Navigation on Mobile
- **Top Nav**: Hamburger menu (☰) for all sections
- **Breadcrumbs**: Shows your location
- **Back Button**: Returns to previous page
- **Bottom Buttons**: Edit/Delete actions

---

## 🎯 Use Cases

### For Examiners
- **Pre-Exam Preparation**: Create and review cases before exam day
- **Mobile Review**: Check cases on your phone while commuting
- **During Exams**: Access cases on tablet during viva
- **Post-Exam**: Add discussion notes from your experience

### For Exam Coordinators
- **Session Planning**: Organize multiple exam sessions
- **Packet Management**: Create balanced packet sets
- **Candidate Assignment**: Track candidate allocations
- **Data Backup**: Ensure exam data is safely backed up

### For Training
- **Case Repository**: Build a library of training cases
- **Practice Sessions**: Conduct mock exams with trainees
- **Teaching Tool**: Share cases with colleagues (via backup files)
- **Remote Learning**: Access cases from anywhere

---

## 🔧 Tips & Tricks

### Efficiency Tips
1. **Use Templates**: Create a case with your standard Q&A structure, then copy
2. **Batch Upload**: Upload multiple images at once
3. **Quick Edit**: Edit cases directly from view page (mobile-friendly)
4. **Keyboard Shortcuts**: Tab through form fields for faster entry

### Data Organization
1. **Naming Convention**: Use consistent session names (e.g., "FRCR 2026-01")
2. **Packet Labels**: Use A, B, C or numbered packets
3. **Case Numbering**: Auto-numbered by app
4. **Image Descriptions**: Add brief descriptions for quick reference

### Backup Strategy
1. **Before Exam**: Always backup before exam day
2. **After Changes**: Backup after adding multiple cases
3. **Weekly Archive**: Keep one backup per week in cloud
4. **Test Restore**: Practice restoring to ensure familiarity

---

## ❓ Frequently Asked Questions

### Q: Can I use this on my phone?
**A**: Yes! The app is fully mobile-responsive. You can create, edit, and view cases on any mobile device.

### Q: How do I share cases with colleagues?
**A**: Download a backup file and share it. Your colleague can restore it to their account.

### Q: Are my images safe?
**A**: Yes. Images are stored in the database and included in backups. They're never lost.

### Q: Can multiple users access the same data?
**A**: Each user has their own data. Share via backup files or use the same login credentials (demo mode only).

### Q: What happens if I lose my password?
**A**: Use "Forgot Password" on login page to receive a reset link via email.

### Q: How much data can I store?
**A**: The app can handle hundreds of cases and thousands of images without issues.

### Q: Can I export cases to PDF?
**A**: Currently backups are JSON format. Use browser "Print to PDF" to save individual cases.

### Q: Does this work offline?
**A**: The app requires internet connection. However, backups can be stored offline.

---

## 🆘 Troubleshooting

### Cannot Login
- Clear browser cache and cookies
- Check email and password carefully
- Use "Forgot Password" if needed
- Try different browser

### Images Not Uploading
- Check file size (max 10MB per image recommended)
- Ensure stable internet connection
- Try uploading one image at a time
- Supported formats: JPG, PNG, GIF

### Backup Download Fails
- Check browser pop-up blocker settings
- Ensure sufficient device storage
- Try different browser
- Check internet connection

### Mobile Display Issues
- Refresh the page
- Clear browser cache
- Update mobile browser to latest version
- Try landscape orientation for easier viewing

### Case Not Saving
- Check all required fields are filled
- Ensure internet connection is stable
- Try saving again after a few seconds
- Check browser console for errors (F12)

---

## 📊 System Requirements

### Supported Browsers
- ✅ Chrome/Edge (Recommended)
- ✅ Firefox
- ✅ Safari
- ✅ Mobile browsers (iOS Safari, Chrome Mobile)

### Device Requirements
- Any device with modern web browser
- Internet connection required
- Minimum screen size: 320px (phone)
- Recommended: 768px+ (tablet/desktop)

### Data Limits
- Database size: Unlimited on cloud deployment
- Images: Recommended max 10MB per image
- Backup files: Typically 1-100MB depending on content

---

## 🔒 Privacy & Security

### What We Collect
- Email address (for authentication)
- Full name
- Exam session data
- Cases, images, and candidate information

### What We DON'T Collect
- Payment information (free to use)
- Location data
- Usage analytics
- Third-party tracking

### Data Security
- Passwords are hashed (bcrypt)
- HTTPS encryption
- Secure session management
- Admin-only backup access
- No data sharing with third parties

### Data Ownership
- You own all your data
- Download backups anytime
- Delete account anytime
- Export data via backup feature

---

## 📞 Support

### Need Help?
- **Email**: lotusheart2016@gmail.com
- **Developer**: Dr Gaurav S.P Gupta, MBBS, MD, FRCR

### Report Issues
- Describe the problem clearly
- Include screenshots if possible
- Mention device and browser used
- State steps to reproduce issue

### Feature Requests
We welcome suggestions! Email us with:
- Feature description
- Use case scenario
- Why it would be helpful

---

## 🎓 About

**FRCR Examiner** was developed by Dr Gaurav S.P Gupta to help fellow medical examiners conduct more efficient and organized FRCR viva examinations. The app combines clinical expertise with modern web technology to provide a seamless exam management experience.

### Version
- **Current**: 2.0 (Production)
- **Last Updated**: January 2026
- **Platform**: Cloud-based (Vercel)
- **Database**: PostgreSQL (Supabase)

---

## 📄 License

© 2026 FRCR Examiner Tool. All rights reserved.

**Usage Terms**:
- Free for personal and educational use
- Not for commercial redistribution
- Data backup is user's responsibility
- No warranty provided

---

**Ready to start? Visit https://frcr-examiner.vercel.app and begin organizing your FRCR exams today!** 🚀
