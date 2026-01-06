# Automated Database Backup & Recovery System

## Overview

The FRCR Examiner application now includes a **fully automated, enterprise-grade backup and recovery system** that:

✅ **Automatically backs up your database every 24 hours**
✅ **Protects against accidental deletion or data corruption**
✅ **Allows one-click recovery to any previous state**
✅ **Maintains detailed activity logs of all operations**
✅ **Includes database statistics and monitoring**
✅ **Starts automatically when the app runs**

## System Architecture

### Components

```
FRCR_EXAMINER/
├── backup_manager.py          ← Core backup system (auto-loaded)
├── backup_database.py         ← Manual backup script
├── backup_scheduler.py        ← Scheduler and management
├── restore_database.py        ← Interactive recovery tool
├── app.py                     ← Flask app (integrated backup APIs)
├── templates/
│   └── admin_dashboard.html   ← Web UI for backup management
└── backups/                   ← Backup storage directory
    ├── frcr_examiner_backup_*.db    ← Backup files
    ├── backup_log.txt               ← Activity log
    └── backups_metadata.json        ← Backup metadata
```

## Automatic Features

### 1. **Automatic Daily Backups**

The backup system starts automatically when you run the Flask app:

```bash
flask run
# Automatic daily backups begin in the background
```

Output in console:
```
[2026-01-06 18:30:17] [INFO] Auto-backup scheduler started (interval: 24h)
```

**What happens:**
- Every 24 hours, a new timestamped backup is created
- Backups are stored in `backups/` directory with timestamps
- Old backups are automatically cleaned up (keeps last 30)
- All operations are logged to `backups/backup_log.txt`

### 2. **Database Change Tracking**

Each backup includes a snapshot of database statistics:
- Number of records in each table (Cases, Packets, Candidates, etc.)
- Backup timestamp and size
- Optional description (auto or manual)

## Using the Backup System

### Method 1: Web Dashboard (Recommended for Users)

1. **Open the Admin Dashboard:**
   - Go to `http://127.0.0.1:5000/admin`
   - Or click "Backup Center" in the navigation bar

2. **View Statistics:**
   - Total number of backups
   - Storage used
   - Database table counts
   - Oldest and newest backup dates

3. **Create Manual Backup:**
   - Click "Create Backup Now"
   - Optionally add a description
   - System creates timestamped backup immediately

4. **Restore from Backup:**
   - View all available backups in the list
   - Select any backup
   - Click "Restore" button
   - Confirm the restore
   - Current database is saved as safety backup before restore
   - Database is restored automatically

5. **Monitor Activity:**
   - View recent backup log at bottom of dashboard
   - See all backup operations with timestamps
   - Monitor backup success/failures

### Method 2: Command Line (For Scripting/Automation)

#### Create a backup manually:
```bash
python backup_database.py
# Output:
# ✓ Database backed up successfully!
#   Location: /Users/zen/.../backups/frcr_examiner_backup_20260106_143022.db
#   Size: 40.00 KB
```

#### List all backups:
```bash
python backup_database.py --list
# Output:
# 📦 Available Database Backups:
# 1. frcr_examiner_backup_20260106_143022.db
#    Size: 40.00 KB | Modified: 2026-01-06 14:30:22
```

#### Restore from backup (interactive):
```bash
python restore_database.py
# Launches interactive recovery wizard:
# - Shows all available backups
# - You select which to restore
# - Creates safety backup of current DB
# - Restores selected backup
# - Verifies integrity
```

#### Restore specific backup directly:
```bash
python restore_database.py 1  # Restores backup #1
```

#### Using the scheduler:
```bash
# Create a backup
python backup_scheduler.py --backup

# View backup statistics
python backup_scheduler.py --list

# View activity log
python backup_scheduler.py --log 30

# Verify backup integrity
python backup_scheduler.py --verify frcr_examiner_backup_20260106_143022.db
```

## Backup Storage Location

All backups are stored in the `backups/` directory at the project root:

```
FRCR_EXAMINER/
├── backups/
│   ├── frcr_examiner_backup_20260106_143022.db   (40 KB)
│   ├── frcr_examiner_backup_20260105_020000.db   (38 KB)
│   ├── frcr_examiner_backup_20260104_020000.db   (35 KB)
│   ├── backup_log.txt                            (activity log)
│   └── backups_metadata.json                     (metadata)
└── ...
```

### Backup Filename Format

`frcr_examiner_backup_YYYYMMDD_HHMMSS.db`

Example: `frcr_examiner_backup_20260106_143022.db`
- Date: 2026-01-06
- Time: 14:30:22 (2:30 PM)

## Safety Features

### 1. **Safety Backup Before Restore**

When you restore from a backup, the current database is automatically backed up:

```
instance/frcr_examiner.db.before_restore_20260106_150000
```

This allows you to revert to the current state if needed.

### 2. **Database Integrity Verification**

- All backups are verified after creation
- All backups are verified before restoration
- Corrupted backups are automatically deleted
- Failed operations are logged with error messages

### 3. **Automatic Retention Policy**

- Keeps the most recent 30 backups
- Automatically deletes old backups
- Prevents excessive storage usage
- Maintains a good balance of backup coverage

### 4. **Comprehensive Logging**

All backup operations are logged:

```
[2026-01-06 18:30:17] [INFO] Auto-backup scheduler started (interval: 24h)
[2026-01-06 18:31:22] [INFO] Backup created: frcr_examiner_backup_20260106_183122.db (40.00 KB)
[2026-01-06 18:35:45] [INFO] Database restored from: frcr_examiner_backup_20260106_140000.db
```

View the log file: `backups/backup_log.txt`

## API Endpoints

The Flask app provides REST API endpoints for backup management:

```
POST   /api/backup/create              - Create new backup
GET    /api/backup/list                - List all backups
GET    /api/backup/statistics          - Get backup statistics
POST   /api/backup/restore/<timestamp> - Restore from backup
GET    /api/backup/log                 - Get activity log
```

### Example API Usage

```bash
# Create a backup via API
curl -X POST http://127.0.0.1:5000/api/backup/create \
  -H "Content-Type: application/json" \
  -d '{"description": "Pre-major-update backup"}'

# Get all backups
curl http://127.0.0.1:5000/api/backup/list

# Get statistics
curl http://127.0.0.1:5000/api/backup/statistics

# Restore a backup
curl -X POST http://127.0.0.1:5000/api/backup/restore/20260106_143022

# Get activity log (last 30 entries)
curl http://127.0.0.1:5000/api/backup/log?lines=30
```

## Common Scenarios

### Scenario 1: Daily Usage
✅ System automatically backs up your database every night
✅ You work normally, no action needed
✅ Backups are stored securely

### Scenario 2: Accidental Deletion
1. Open Admin Dashboard (`/admin`)
2. Find the backup from before deletion
3. Click "Restore"
4. Confirm restore
5. Database recovered to previous state

### Scenario 3: Database Corruption
1. Go to Admin Dashboard
2. Check Recent Activity Log
3. Find last successful backup
4. Click "Restore" on that backup
5. System verified backup integrity before restoring

### Scenario 4: Regular Maintenance
1. Click "Create Backup Now" in dashboard
2. Add description: "Pre-maintenance snapshot"
3. Perform maintenance
4. If issues occur, restore from saved backup

### Scenario 5: Testing New Features
1. Create backup: "Before feature testing"
2. Test new features
3. If problems found, restore to clean state
4. No data lost, quick recovery

## Monitoring & Maintenance

### Weekly Checks

```bash
# Check backup status
python backup_scheduler.py --list

# View recent log entries
python backup_scheduler.py --log 20
```

### Monthly Verification

```bash
# Verify all recent backups are intact
python backup_scheduler.py --verify frcr_examiner_backup_20260106_143022.db
python backup_scheduler.py --verify frcr_examiner_backup_20260105_020000.db
```

### Storage Management

Monitor backup storage:
```bash
du -sh /Users/zen/myRepos/projects/FRCR_EXAMINER/backups/
# If backups exceed 500MB, system will keep only 30 most recent
```

## Advanced: Setting Up Additional Automated Backups

### Option 1: Multiple Daily Backups (macOS/Linux)

Edit crontab:
```bash
crontab -e
```

Add backup at 2 AM, 10 AM, and 6 PM:
```cron
0 2 * * * cd /Users/zen/myRepos/projects/FRCR_EXAMINER && python backup_scheduler.py --backup
0 10 * * * cd /Users/zen/myRepos/projects/FRCR_EXAMINER && python backup_scheduler.py --backup
0 18 * * * cd /Users/zen/myRepos/projects/FRCR_EXAMINER && python backup_scheduler.py --backup
```

### Option 2: Backup to External Drive

Create a copy of backups to external drive:
```bash
# Create a script: backup_to_external.sh
#!/bin/bash
cp -r /Users/zen/myRepos/projects/FRCR_EXAMINER/backups/* /Volumes/ExternalDrive/FRCR_Backups/
```

Add to crontab (weekly):
```cron
0 3 * * 0 /Users/zen/myRepos/projects/FRCR_EXAMINER/backup_to_external.sh
```

### Option 3: Cloud Backup (Google Drive, Dropbox)

```bash
# Install rclone: https://rclone.org/
rclone config create gdrive google storage-helpers

# Add to crontab (daily)
0 4 * * * rclone sync /Users/zen/myRepos/projects/FRCR_EXAMINER/backups gdrive:FRCR_Backups
```

## Troubleshooting

### Problem: "No backups found"
**Solution:** 
- Click "Create Backup Now" in the dashboard
- Or run: `python backup_database.py`

### Problem: Backup creation is slow
**Solution:**
- Database file is locked by Flask app
- Flask automatically handles this
- Wait 1-2 seconds and retry

### Problem: Cannot restore - permission denied
**Solution:**
```bash
chmod 755 instance/
chmod 644 instance/frcr_examiner.db
python restore_database.py
```

### Problem: Backup file is corrupted
**Solution:**
- System detects corrupted backups automatically
- Corrupted backups are deleted
- Restore from an earlier backup:
```bash
python restore_database.py
# Select an earlier backup
```

### Problem: Too many backups using storage
**Solution:**
- System keeps only 30 most recent backups
- Old backups are deleted automatically
- Check storage: `du -sh backups/`

## Database Statistics Tracked

Each backup includes:

| Table | What's Tracked |
|-------|----------------|
| exam_session | Total exam sessions created |
| packet | Total exam packets prepared |
| case | Total exam cases stored |
| candidate | Total candidates |
| case_image | Total images uploaded |

This helps you understand database growth and recovery points.

## Next Steps

1. **For First-Time Users:**
   - Go to `/admin` dashboard
   - Review backup statistics
   - Create a manual backup to test

2. **For Regular Use:**
   - System automatically backs up daily
   - No action required
   - Check dashboard monthly

3. **For Advanced Users:**
   - Set up additional scheduled backups
   - Configure external backups
   - Monitor backup storage

4. **For Developers:**
   - Use backup API endpoints for custom integrations
   - Automate backup testing
   - Integrate with CI/CD pipelines

## Summary

Your database is now protected with:
- ✅ Automatic daily backups
- ✅ One-click web interface for recovery
- ✅ Command-line tools for scripting
- ✅ Comprehensive logging and monitoring
- ✅ Safety features and integrity checks
- ✅ Automatic storage management

**Your data is secure. You can work confidently!**

---

**Last Updated:** 2026-01-06
**System Version:** 1.0
**Backup Format:** SQLite 3
**Supported Recovery:** Full point-in-time recovery
