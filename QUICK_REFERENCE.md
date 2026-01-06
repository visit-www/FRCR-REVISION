# Quick Reference Guide

Fast lookup guide for common tasks and commands.

## 📚 Documentation Files

| File | Purpose | Audience |
|------|---------|----------|
| **README.md** | Complete technical overview | Developers, DevOps |
| **HOW_TO_USE.md** | Step-by-step user guide | End users, Examiners |
| **SETUP.md** | Installation instructions | System admins, Developers |
| **CONTRIBUTING.md** | Developer guidelines | Contributors |
| **CHANGELOG.md** | Version history and changes | Everyone |

---

## 🚀 Quick Start Commands

### Local Development
```bash
# Setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run
export FLASK_ENV=development
flask run

# Access
Open http://localhost:5000
```

### Production Deployment (Railway)
1. Push to GitHub
2. Connect repo to Railway.app
3. Add `DATABASE_URL` environment variable
4. Deploy automatically

---

## 🎯 User Workflow

```
Home → Get Started → Manage Session → Add Cases & Candidates
  ↓
Exam → Select Session → Choose Candidate → Start Exam
```

---

## 🛠️ Common Admin Tasks

### Backup
- Automatic: Every 24 hours in `backups/` folder
- Manual: Copy database file or use Admin panel

### Add New User Feature
1. Define model in `models.py`
2. Create API endpoint in `app.py`
3. Add template in `templates/`
4. Update documentation

### Change Database
- Development: SQLite (automatic)
- Production: Set `DATABASE_URL` environment variable

---

## 📝 File Structure Quick Reference

```
app.py              → Main Flask app & routes
models.py           → Database models
requirements.txt    → Python dependencies
templates/
  ├── base.html     → Navigation template
  ├── dashboard.html → Home page
  └── ...other pages
static/
  ├── style.css     → Styling
  └── ...js files
instance/           → Database (development)
backups/            → Auto-backups
```

---

## 🔗 Important Routes

| Path | Purpose |
|------|---------|
| `/` | Dashboard home |
| `/setup/sessions` | Manage exam sessions |
| `/manage-session/<id>` | Edit session, add cases/candidates |
| `/exam/start` | Start exam workflow |
| `/view-case/<id>` | View case during exam |
| `/admin` | Admin dashboard |
| `/api/*` | REST API endpoints |

---

## 🐛 Troubleshooting Quick Links

| Issue | Solution |
|-------|----------|
| Port 5000 in use | `flask run --port 5001` |
| Module not found | Activate venv, reinstall requirements |
| Database error | Check DATABASE_URL, restart PostgreSQL |
| Images not showing | Check static files, clear browser cache |
| Permission denied | Fix file/directory permissions with chmod |

---

## 📊 Database Models

### Core Models
- **ExamSession** - Exam sessions
- **Candidate** - Candidate information
- **Packet** - Case packets
- **Case** - Medical cases
- **Question** - Q&A questions
- **Answer** - Q&A answers
- **CaseImage** - Case images

---

## 🔐 Security Checklist

- [ ] Set `SECRET_KEY` in production
- [ ] Use PostgreSQL (not SQLite) in production
- [ ] Enable HTTPS
- [ ] Set `FLASK_ENV=production`
- [ ] Configure firewall rules
- [ ] Enable backups
- [ ] Use strong database password
- [ ] Regular security updates

---

## 📱 Browser Support

- Chrome/Edge: ✅ Fully supported
- Firefox: ✅ Fully supported
- Safari: ✅ Fully supported
- IE: ❌ Not supported (use modern browser)

### Mobile
- Responsive design for tablets
- Touch-friendly interface
- Tested on iOS Safari and Android Chrome

---

## 🚀 Performance Tips

- Optimize images (< 5MB each)
- Use compression for backups
- Keep < 100 sessions active
- Limit cases per session to < 1000
- Regular database optimization

---

## 📞 Support Resources

| Need | Contact |
|------|---------|
| Bug report | GitHub Issues |
| Feature request | GitHub Issues |
| General help | lotusheart2016@gmail.com |
| Installation help | See SETUP.md |
| Usage help | See HOW_TO_USE.md |

---

## 📖 Key Concepts

### Session
Container for one day's exams, holds packets and candidates

### Packet
Group of cases assigned to a candidate

### Case
Medical scenario with images, diagnosis, and Q&A

### Candidate
Person taking the exam, assigned to a specific packet

### Q&A Pair
Question to ask and expected answer for learning/reference

---

## ⚡ Performance Metrics

- Page load: < 2 seconds
- Database query: < 500ms
- Image upload: Depends on file size
- Backup creation: < 5 seconds

---

## 📅 Important Dates

- **Version**: 1.0.0
- **Release Date**: January 6, 2026
- **Last Updated**: January 6, 2026

---

## 🎓 Learning Resources

1. **For Users**: Start with HOW_TO_USE.md
2. **For Developers**: Read README.md then CONTRIBUTING.md
3. **For DevOps**: Check SETUP.md
4. **For History**: See CHANGELOG.md

---

## 💾 Database Connection Examples

### SQLite (Development)
```python
DATABASE_URL = "sqlite:///./instance/frcr_examiner.db"
```

### PostgreSQL (Production)
```python
DATABASE_URL = "postgresql://user:password@localhost:5432/frcr_examiner"
```

### Environment Variable
```bash
export DATABASE_URL="postgresql://user:password@host:5432/db"
```

---

## 🔄 Workflow Examples

### Create and Run Exam
1. Create session: Name, Date, Time
2. Add packet in session
3. Add case to packet with images
4. Add Q&A pairs to case
5. Register candidate and assign packet
6. Start exam from Exam menu

### Backup and Restore
1. Automatic backups created in backups/
2. Backup files: `frcr_examiner_backup_YYYYMMDD_HHMMSS.db`
3. Restore: Copy backup file back to instance/

---

**Quick Help**: For detailed information, refer to appropriate documentation file listed above.

Last Updated: January 6, 2026
