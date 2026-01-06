#!/usr/bin/env python3
"""
Database Recovery Script
Restore the database from a timestamped backup
"""

import os
import shutil
from datetime import datetime
import sys

def list_backups():
    """List all available database backups"""
    
    backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
    
    if not os.path.exists(backup_dir):
        print("❌ No backups directory found.")
        return []
    
    backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')])
    
    if not backups:
        print("❌ No backups found.")
        return []
    
    print("\n📦 Available Database Backups:")
    print("=" * 80)
    
    for i, backup in enumerate(backups, 1):
        backup_path = os.path.join(backup_dir, backup)
        size_kb = os.path.getsize(backup_path) / 1024
        mod_time = datetime.fromtimestamp(os.path.getmtime(backup_path))
        
        print(f"{i}. {backup}")
        print(f"   Size: {size_kb:.2f} KB | Modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
    
    return backups


def restore_backup(backup_index):
    """Restore database from a selected backup"""
    
    backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'frcr_examiner.db')
    
    # List available backups
    backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')])
    
    if not backups or backup_index < 1 or backup_index > len(backups):
        print(f"❌ Invalid backup index: {backup_index}")
        return False
    
    backup_to_restore = backups[backup_index - 1]
    backup_path = os.path.join(backup_dir, backup_to_restore)
    
    try:
        # Create a safety backup of current database
        if os.path.exists(db_path):
            safety_backup = f"{db_path}.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(db_path, safety_backup)
            print(f"✓ Safety backup created: {safety_backup}")
        
        # Restore the selected backup
        shutil.copy2(backup_path, db_path)
        
        print(f"\n✓ Database restored successfully!")
        print(f"  Restored from: {backup_to_restore}")
        print(f"  Current database: {db_path}")
        print(f"  Size: {os.path.getsize(db_path) / 1024:.2f} KB")
        print(f"\n⚠️  Restart Flask for changes to take effect.")
        
        return True
        
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        return False


def interactive_restore():
    """Interactive restore wizard"""
    
    print("\n" + "=" * 80)
    print("DATABASE RECOVERY WIZARD")
    print("=" * 80)
    
    backups = list_backups()
    
    if not backups:
        print("No backups available to restore.")
        return False
    
    try:
        choice = input("\nEnter the number of the backup to restore (or 'q' to quit): ").strip()
        
        if choice.lower() == 'q':
            print("Recovery cancelled.")
            return False
        
        backup_index = int(choice)
        
        # Confirmation
        backup_to_restore = sorted(backups)[backup_index - 1]
        print(f"\n⚠️  WARNING: This will replace your current database with: {backup_to_restore}")
        confirm = input("Are you sure? (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("Recovery cancelled.")
            return False
        
        return restore_backup(backup_index)
        
    except ValueError:
        print("❌ Invalid input. Please enter a number.")
        return False


if __name__ == '__main__':
    if len(sys.argv) > 1:
        try:
            backup_index = int(sys.argv[1])
            restore_backup(backup_index)
        except ValueError:
            print("Usage: python restore_database.py [backup_number]")
            print("       python restore_database.py  (interactive mode)")
            list_backups()
    else:
        interactive_restore()
