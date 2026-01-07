# FRCR Examiner - Backup & Restore System

## Overview

The FRCR Examiner now includes a comprehensive web-based backup and restore system that allows you to:
- **Download** complete database backups to your computer
- **Restore** your database from a backup file
- **Get reminders** every 24 hours to create backups
- **Manage** your backup history (keep last 5 backups)

## Features

### ✅ What's Included

1. **Web-Based Backup Download**
   - Click a button to download your entire database as a JSON file
   - Includes all exam sessions, packets, cases, candidates, images, questions, and answers
   - Secure: Only admin users can access backup features

2. **Automatic Backup Reminders**
   - System reminds you every 24 hours if you haven't backed up
   - Non-intrusive toast notification appears in bottom-right corner
   - "Remind me later" option for busy times

3. **One-Click Restore**
   - Upload any backup file to restore your database
   - Safety confirmation required before overwriting data
   - Shows detailed statistics of what was restored

4. **Backup History Management**
   - Recommended: Keep last 5 backups on your computer
   - Included Python script to manage local backup files
   - Easy verification of backup file integrity

5. **Admin Dashboard Integration**
   - New "Web Backup Manager" link in admin dashboard
   - Real-time backup status display
   - Database statistics overview

## How to Use

### Accessing the Backup Manager

1. Log in as admin (first registered user)
2. Click **Admin** in the top navigation
3. Click **Web Backup Manager (New!)** button
4. You'll see the Backup Manager page with three sections:
   - Backup Status (last backup time, database stats)
   - Download Backup (create and download)
   - Restore from Backup (upload and restore)

### Creating a Backup

**Option 1: Manual Download**
1. Go to Backup Manager page
2. Click **Download Backup Now** button
3. File will download to your default Downloads folder
4. Filename format: `frcr_examiner_backup_YYYYMMDD_HHMMSS.json`

**Option 2: Reminder System**
1. System automatically checks every 24 hours
2. If backup needed, you'll see a reminder notification
3. Click **Go to Backup Manager** to download
4. Or click **Remind Me Later** to dismiss

### Restoring from a Backup

⚠️ **WARNING**: Restoring will overwrite all current data (except user accounts)!

1. Go to Backup Manager page
2. Scroll to **Restore from Backup** section
3. Click **Choose File** and select your backup JSON file
4. Check the confirmation box: "I understand this will overwrite my current data"
5. Click **Restore Database**
6. Wait for completion (page will auto-refresh)
7. Verify your data is restored correctly

### Managing Local Backup Files

Use the included Python script to manage backups on your computer:

```bash
# List all backups in a directory
python manage_local_backups.py ~/Downloads

# Keep only the 5 most recent backups (delete older ones)
python manage_local_backups.py ~/Downloads cleanup

# Verify a specific backup file
python manage_local_backups.py ~/Downloads/frcr_examiner_backup_20250107_120000.json verify
```

**Cleanup Example:**
```bash
$ python manage_local_backups.py ~/Downloads cleanup

You have 8 backups. Keeping the 5 most recent.

The following 3 backup(s) will be DELETED:
1. frcr_examiner_backup_20250101_100000.json (2025-01-01 10:00:00)
2. frcr_examiner_backup_20250102_100000.json (2025-01-02 10:00:00)
3. frcr_examiner_backup_20250103_100000.json (2025-01-03 10:00:00)

Delete these 3 old backup(s)? (yes/no): yes
✓ Deleted: frcr_examiner_backup_20250101_100000.json
✓ Deleted: frcr_examiner_backup_20250102_100000.json
✓ Deleted: frcr_examiner_backup_20250103_100000.json

Cleanup complete: Deleted 3 file(s), freed 45.2 MB
```

## Backup Best Practices

### Recommended Schedule

- **Daily**: Download a backup every day before making changes
- **Before Updates**: Always backup before system updates or major changes
- **After Data Entry**: Backup after adding multiple cases or sessions
- **Weekly Archive**: Keep one weekly backup in cloud storage

### Storage Recommendations

1. **Local Storage** (Required)
   - Keep last 5 backups on your computer
   - Store in organized folder (e.g., `~/Documents/FRCR_Backups/`)
   - Use the cleanup script weekly to maintain 5-backup limit

2. **Cloud Storage** (Recommended)
   - Upload weekly backup to Google Drive, Dropbox, or OneDrive
   - Provides off-site backup protection
   - Easy access from any device

3. **External Drive** (Optional)
   - Monthly backup to external hard drive or USB
   - Ultimate protection against hardware failure

### What Gets Backed Up

✅ **Included in Backup:**
- All exam sessions (date, time, name)
- All packets (packet numbers, IDs)
- All cases (diagnosis, questions, answers, discussions)
- All candidates (names, numbers, packet assignments)
- All case images (full resolution, base64 encoded)
- All questions and answers (separate tables)
- User information (email, name - passwords NOT included)

❌ **NOT Included:**
- User passwords (security measure)
- Session cookies
- Temporary files

## Technical Details

### File Format

Backups are JSON files with this structure:

```json
{
  "metadata": {
    "backup_date": "2025-01-07T12:00:00",
    "database_type": "postgresql",
    "version": "1.0"
  },
  "users": [...],
  "exam_sessions": [...],
  "packets": [...],
  "cases": [...],
  "candidates": [...],
  "case_images": [...],
  "questions": [...],
  "answers": [...]
}
```

### API Endpoints

- `GET /api/backup/status` - Get backup status and statistics
- `GET /api/backup/download` - Download backup file
- `POST /api/backup/restore` - Restore from uploaded backup

### Security

- Only admin users (first registered user) can access backup features
- User passwords are NOT included in backups
- Backups contain sensitive exam data - keep files secure
- Restore requires explicit confirmation checkbox

### Browser Compatibility

- ✅ Chrome/Edge: Full support
- ✅ Firefox: Full support
- ✅ Safari: Full support
- ✅ Mobile browsers: Full support

## Troubleshooting

### Backup Download Not Working

**Problem**: Button clicks but nothing downloads

**Solutions**:
1. Check browser's download settings
2. Ensure pop-up blocker isn't blocking download
3. Check browser console (F12) for errors
4. Try different browser
5. Ensure you're logged in as admin

### Restore Fails

**Problem**: "Restore failed" error message

**Solutions**:
1. Verify backup file is valid JSON:
   ```bash
   python manage_local_backups.py /path/to/backup.json verify
   ```
2. Ensure backup file wasn't corrupted during transfer
3. Check file size (shouldn't be 0 bytes)
4. Try re-downloading the backup from a previous date
5. Check browser console for detailed error

### Reminder Not Appearing

**Problem**: No reminder after 24 hours

**Solutions**:
1. Ensure you're logged in as admin
2. Clear browser localStorage:
   ```javascript
   // In browser console (F12)
   localStorage.removeItem('backup_last_check');
   sessionStorage.removeItem('backup_reminder_dismissed');
   location.reload();
   ```
3. Check browser console for JavaScript errors

### "Admin Access Required" Error

**Problem**: Getting permission error when accessing backup page

**Solutions**:
1. Ensure you're the first registered user (admin)
2. Log out and log back in
3. Check with `User.query.order_by(User.id).first()` in database
4. Contact system administrator if not admin

## Migration from Old Backup System

If you were using the old SQLite-based backup system:

1. **Old backups are still available** in the `backups/` folder
2. **New system uses JSON format** (cross-database compatible)
3. **Old backups won't work** with new restore feature
4. **Recommendation**: Download new JSON backup immediately

## FAQ

**Q: How large are backup files?**
A: Depends on your data. Typical sizes:
- Small database (10 cases): ~500 KB
- Medium database (100 cases with images): ~5-10 MB
- Large database (1000 cases with images): ~50-100 MB

**Q: Can I edit the backup JSON file?**
A: Technically yes, but not recommended. If you need to modify data, use the application interface instead.

**Q: Will restoring delete user accounts?**
A: No, user accounts are preserved. Only exam data is overwritten.

**Q: Can I restore a backup from a different database type?**
A: Yes! Backups are database-agnostic. You can restore a PostgreSQL backup to SQLite and vice versa.

**Q: What happens if I forget to backup?**
A: The reminder system will notify you after 24 hours. However, you can manually download at any time.

**Q: Can I automate daily backups?**
A: Currently manual download only. You can set a daily calendar reminder on your phone/computer to visit the backup page.

## Support

For issues or questions:
1. Check this documentation
2. Check browser console (F12) for errors
3. Verify you're logged in as admin
4. Review the troubleshooting section

## Version History

### v1.0 (Current)
- Initial release of web-based backup system
- JSON format for cross-database compatibility
- Automatic 24-hour reminders
- One-click download and restore
- Local backup management script
- Admin dashboard integration
