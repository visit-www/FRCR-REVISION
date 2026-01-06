#!/usr/bin/env python3
"""
Database Backup Script
Automatically backs up the SQLite database to a timestamped file
"""

import os
import shutil
from datetime import datetime
import sys

def backup_database():
    """Create a timestamped backup of the database"""
    
    # Define paths
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'frcr_examiner.db')
    backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
    
    # Create backups directory if it doesn't exist
    os.makedirs(backup_dir, exist_ok=True)
    
    # Check if database exists
    if not os.path.exists(db_path):
        print("❌ Database not found at:", db_path)
        return False
    
    try:
        # Create timestamped backup filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'frcr_examiner_backup_{timestamp}.db'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Copy database to backup location
        shutil.copy2(db_path, backup_path)
        
        print(f"✓ Database backed up successfully!")
        print(f"  Location: {backup_path}")
        print(f"  Size: {os.path.getsize(backup_path) / 1024:.2f} KB")
        
        return True
        
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False


def list_backups():
    """List all available database backups"""
    
    backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
    
    if not os.path.exists(backup_dir):
        print("No backups found. Create your first backup by running backup_database.py")
        return
    
    backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')])
    
    if not backups:
        print("No backups found.")
        return
    
    print("\n📦 Available Database Backups:")
    print("=" * 80)
    
    for i, backup in enumerate(backups, 1):
        backup_path = os.path.join(backup_dir, backup)
        size_kb = os.path.getsize(backup_path) / 1024
        mod_time = datetime.fromtimestamp(os.path.getmtime(backup_path))
        
        print(f"{i}. {backup}")
        print(f"   Size: {size_kb:.2f} KB | Modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--list':
        list_backups()
    else:
        backup_database()
