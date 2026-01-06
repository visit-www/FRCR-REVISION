# Database Backup & Recovery Guide

## Overview

The FRCR Examiner application now includes a comprehensive backup and recovery system to protect your data. This guide explains how to use the backup tools.

## Files

Three scripts manage your database backups:

1. **backup_database.py** - Manual backup creation
2. **backup_scheduler.py** - Automated backups and retention management
3. **restore_database.py** - Restore from any backup

## Quick Start

### Create a Backup Now

```bash
python backup_database.py
```

Output:
```
✓ Database backup created
  Filename: frcr_examiner_backup_20250107_143022.db
  Size: 24.50 KB
  Location: backups/
```

### List All Available Backups

```bash
python backup_database.py --list
```

Output:
```
📦 Available Database Backups:
================================================================================
1. frcr_examiner_backup_20250107_143022.db
   Size: 24.50 KB | Modified: 2025-01-07 14:30:22

2. frcr_examiner_backup_20250106_120000.db
   Size: 23.80 KB | Modified: 2025-01-06 12:00:00
```

### Restore from a Backup

```bash
python restore_database.py
```

This launches an interactive recovery wizard:

1. Lists all available backups
2. You select which backup to restore
3. Creates a safety backup of your current database
4. Restores your selected backup
5. Verifies the restored database

Example:
```
================================================================================
DATABASE RECOVERY WIZARD
================================================================================

📦 Available Database Backups:
================================================================================
1. frcr_examiner_backup_20250107_143022.db
   Size: 24.50 KB | Modified: 2025-01-07 14:30:22

Enter the number of the backup to restore (or 'q' to quit): 1

⚠️  WARNING: This will replace your current database with: frcr_examiner_backup_20250107_143022.db
Are you sure? (yes/no): yes

✓ Safety backup created: instance/frcr_examiner.db.before_restore_20250107_145000

✓ Database restored successfully!
  Restored from: frcr_examiner_backup_20250107_143022.db
  Current database: instance/frcr_examiner.db
  Size: 24.50 KB

⚠️  Restart Flask for changes to take effect.
```

Or restore directly by backup number:

```bash
python restore_database.py 1
```

## Automated Backups

### Run Manual Scheduled Backup

```bash
python backup_scheduler.py --backup
```

Output:
```
[2025-01-07 14:30:22] ✓ Backup created: frcr_examiner_backup_20250107_143022.db (24.50 KB)
```

### View Backup Log

```bash
python backup_scheduler.py --log
```

Shows the last 20 backup events with timestamps.

### View Backup Statistics

```bash
python backup_scheduler.py --list
```

Output:
```
📦 Database Backups (5 total):
================================================================================
 1. frcr_examiner_backup_20250107_143022.db
    Size:   24.50 KB | Modified: 2025-01-07 14:30:22
 2. frcr_examiner_backup_20250106_120000.db
    Size:   23.80 KB | Modified: 2025-01-06 12:00:00
================================================================================
Total backup storage: 121.30 KB (0.12 MB)
```

### Verify Backup Integrity

```bash
python backup_scheduler.py --verify frcr_examiner_backup_20250107_143022.db
```

This checks if a backup is valid and not corrupted.

## Setting Up Automated Daily Backups

### On macOS/Linux (Cron)

1. Open crontab editor:
   ```bash
   crontab -e
   ```

2. Add a daily backup at 2 AM:
   ```
   0 2 * * * cd /Users/zen/myRepos/projects/FRCR_EXAMINER && python backup_scheduler.py --backup
   ```

3. The backup will run automatically every night at 2 AM

### On Windows (Task Scheduler)

1. Open Task Scheduler
2. Create New Task
3. Set Trigger: Daily at 2:00 AM
4. Set Action: Run program `python.exe` with arguments `backup_scheduler.py --backup`
5. Set Working Directory: `C:\path\to\FRCR_EXAMINER`

## Backup Retention Policy

The backup system automatically manages backup storage:

- **Last 7 days**: Keep all daily backups
- **Older backups**: Keep up to 30 total backups
- **Automatic cleanup**: Old backups are deleted when the limit is reached
- **Storage monitoring**: Total backup size is calculated

This ensures you have recovery options without excessive storage usage.

## Backup Storage Location

All backups are stored in the `backups/` directory:

```
FRCR_EXAMINER/
├── backups/
│   ├── frcr_examiner_backup_20250107_143022.db
│   ├── frcr_examiner_backup_20250106_120000.db
│   ├── frcr_examiner_backup_20250105_020000.db
│   └── backup_log.txt
├── instance/
│   └── frcr_examiner.db  (current database)
└── ...
```

## Safety Features

### Pre-Restore Safety Backup

When you restore from a backup, the current database is automatically backed up:

```
instance/frcr_examiner.db.before_restore_20250107_145000
```

This allows you to revert to the current state if the restore wasn't what you expected.

### Database Integrity Checks

- All backups are verified before saving
- Backups are verified before restoring
- Corrupted backups are deleted automatically
- Log entries report verification results

## Common Scenarios

### Scenario 1: Accidental Data Deletion

1. Restore from the most recent backup before deletion
2. The current database is saved as a safety backup
3. Your recent data is recovered

```bash
python restore_database.py
# Select the backup from just before the deletion
```

### Scenario 2: Database Corruption

1. View available backups
2. Select the most recent backup you trust
3. Restore from that backup

```bash
python restore_database.py 1
```

### Scenario 3: Regular Maintenance

1. Set up automated daily backups via cron/Task Scheduler
2. Check backup log periodically
3. Monitor storage usage with `--list` command

```bash
python backup_scheduler.py --log 50  # View last 50 events
```

### Scenario 4: Archival

1. List all backups
2. Copy important backups to external storage
3. Keep local backups for recent recovery

```bash
python backup_scheduler.py --list
# Copy backups/frcr_examiner_backup_*.db to external drive
```

## Troubleshooting

### "No backups directory found"

The backups directory is created automatically on first use. Try:

```bash
python backup_database.py
# This will create the backups/ directory
```

### "Database file not found"

Ensure the Flask app has created the database:

```bash
python load_sample_data.py
# This creates instance/frcr_examiner.db
```

### "Backup verification failed"

The database may be in use. Ensure:

1. Flask is not running
2. No other process is accessing the database
3. Try again: `python backup_database.py`

### "Cannot restore - permission denied"

Ensure you have write permissions to the instance/ directory:

```bash
chmod 755 instance/
chmod 644 instance/frcr_examiner.db
```

## Best Practices

1. **Regular Backups**: Set up automated daily backups (2 AM is a good time)
2. **Verify Backups**: Periodically verify backup integrity
3. **Monitor Storage**: Check backup storage size with `--list`
4. **External Backup**: Copy important backups to external media
5. **Document**: Keep notes of significant states you want to preserve
6. **Test Recovery**: Periodically test restoring from a backup
7. **Check Logs**: Review backup_log.txt for any issues

## Command Reference

| Command | Purpose |
|---------|---------|
| `python backup_database.py` | Create backup now |
| `python backup_database.py --list` | List all backups |
| `python backup_scheduler.py --backup` | Create backup (for scheduler) |
| `python backup_scheduler.py --list` | View backup statistics |
| `python backup_scheduler.py --log [N]` | Show last N log entries |
| `python backup_scheduler.py --verify FILE` | Check backup integrity |
| `python restore_database.py` | Interactive restore wizard |
| `python restore_database.py N` | Restore backup #N directly |

## Support

For issues or questions, refer to the troubleshooting section above, or check the backup_log.txt file for detailed error messages.

---

**Last Updated**: 2025-01-07
**Database Version**: SQLite 3
**Backup Format**: SQLite database files (.db)
