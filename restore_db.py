#!/usr/bin/env python3
"""
Quick database restore script
Restores your database from the latest backup
"""
import shutil
import os
from pathlib import Path

BACKUP_DIR = Path("/Users/zen/myRepos/projects/FRCR_EXAMINER/backups")
DB_PATH = Path("/Users/zen/myRepos/projects/FRCR_EXAMINER/instance/frcr_examiner.db")

# Find latest backup
backups = sorted(BACKUP_DIR.glob("frcr_examiner_backup_*.db"))

if not backups:
    print("❌ No backups found!")
    exit(1)

latest_backup = backups[-1]
print(f"📦 Latest backup: {latest_backup.name}")
print(f"📅 Size: {latest_backup.stat().st_size / 1024:.1f} KB")

# Restore
try:
    shutil.copy2(latest_backup, DB_PATH)
    print(f"✅ Data restored successfully!")
    print(f"📍 Location: {DB_PATH}")
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
