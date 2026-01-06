#!/usr/bin/env python3
"""
Automated Database Backup Scheduler
Backs up the database daily and manages retention policy
"""

import os
import shutil
from datetime import datetime, timedelta
import sqlite3
import sys

class BackupScheduler:
    """Manage automated database backups and retention"""
    
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), 'instance', 'frcr_examiner.db')
        self.backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
        self.log_path = os.path.join(self.backup_dir, 'backup_log.txt')
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def log_event(self, message):
        """Log backup event"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {message}"
        
        # Print to console
        print(log_message)
        
        # Append to log file
        with open(self.log_path, 'a') as f:
            f.write(log_message + '\n')
    
    def verify_database(self, db_file):
        """Verify database integrity"""
        try:
            conn = sqlite3.connect(db_file)
            conn.execute('PRAGMA integrity_check')
            conn.close()
            return True
        except Exception as e:
            self.log_event(f"⚠️  Database integrity check failed: {e}")
            return False
    
    def create_backup(self):
        """Create a backup of the database"""
        
        if not os.path.exists(self.db_path):
            self.log_event(f"❌ Database file not found: {self.db_path}")
            return False
        
        try:
            # Verify database before backup
            if not self.verify_database(self.db_path):
                self.log_event("⚠️  Database integrity check failed, proceeding with backup anyway")
            
            # Create timestamped backup
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f'frcr_examiner_backup_{timestamp}.db'
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Copy database file
            shutil.copy2(self.db_path, backup_path)
            
            # Verify the backup
            if not self.verify_database(backup_path):
                os.remove(backup_path)
                self.log_event("❌ Backup verification failed, backup deleted")
                return False
            
            size_kb = os.path.getsize(backup_path) / 1024
            self.log_event(f"✓ Backup created: {backup_filename} ({size_kb:.2f} KB)")
            
            # Apply retention policy
            self.apply_retention_policy()
            
            return True
            
        except Exception as e:
            self.log_event(f"❌ Backup creation failed: {e}")
            return False
    
    def apply_retention_policy(self):
        """
        Apply retention policy:
        - Keep all backups from last 7 days (daily)
        - Keep 4 weekly backups (one per week)
        - Keep 12 monthly backups (one per month)
        """
        
        backups = sorted([f for f in os.listdir(self.backup_dir) if f.endswith('.db')])
        
        if len(backups) <= 30:  # Keep up to 30 backups
            return
        
        # Parse backup dates
        backup_dates = {}
        for backup in backups:
            try:
                # Extract date from filename: frcr_examiner_backup_YYYYMMDD_HHMMSS.db
                date_str = backup.split('_')[3]  # YYYYMMDD
                backup_date = datetime.strptime(date_str, '%Y%m%d').date()
                backup_dates[backup] = backup_date
            except:
                continue
        
        # Sort by date
        sorted_backups = sorted(backup_dates.items(), key=lambda x: x[1], reverse=True)
        
        # Keep the most recent 30 backups
        backups_to_keep = set([b[0] for b in sorted_backups[:30]])
        
        # Delete old backups
        for backup in backups:
            if backup not in backups_to_keep:
                backup_path = os.path.join(self.backup_dir, backup)
                try:
                    os.remove(backup_path)
                    self.log_event(f"🗑️  Deleted old backup: {backup}")
                except Exception as e:
                    self.log_event(f"⚠️  Failed to delete {backup}: {e}")
    
    def list_backups(self):
        """List all backups with statistics"""
        
        backups = sorted([f for f in os.listdir(self.backup_dir) if f.endswith('.db')], reverse=True)
        
        if not backups:
            print("\n❌ No backups found.\n")
            return
        
        print(f"\n📦 Database Backups ({len(backups)} total):")
        print("=" * 80)
        
        total_size = 0
        for i, backup in enumerate(backups[:10], 1):  # Show last 10
            backup_path = os.path.join(self.backup_dir, backup)
            size_kb = os.path.getsize(backup_path) / 1024
            total_size += size_kb
            mod_time = datetime.fromtimestamp(os.path.getmtime(backup_path))
            
            print(f"{i:2}. {backup}")
            print(f"    Size: {size_kb:8.2f} KB | Modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if len(backups) > 10:
            print(f"... and {len(backups) - 10} more backups")
        
        print("=" * 80)
        print(f"Total backup storage: {total_size:.2f} KB ({total_size/1024:.2f} MB)\n")
    
    def show_log(self, lines=20):
        """Show recent backup log entries"""
        
        if not os.path.exists(self.log_path):
            print("\n❌ No backup log found.\n")
            return
        
        with open(self.log_path, 'r') as f:
            all_lines = f.readlines()
        
        print(f"\n📝 Recent Backup Log (last {lines} entries):")
        print("=" * 80)
        
        for line in all_lines[-lines:]:
            print(line.rstrip())
        
        print("=" * 80 + "\n")


def main():
    """Main scheduler function"""
    
    scheduler = BackupScheduler()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == '--backup':
            scheduler.create_backup()
        elif command == '--list':
            scheduler.list_backups()
        elif command == '--log':
            lines = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            scheduler.show_log(lines)
        elif command == '--verify':
            if len(sys.argv) < 3:
                print("Usage: python backup_scheduler.py --verify <backup_file>")
                return
            backup_file = os.path.join(scheduler.backup_dir, sys.argv[2])
            if scheduler.verify_database(backup_file):
                print(f"✓ Database integrity check passed: {sys.argv[2]}")
            else:
                print(f"❌ Database integrity check failed: {sys.argv[2]}")
        else:
            print("Usage: python backup_scheduler.py [command]")
            print("\nCommands:")
            print("  --backup       Create a new backup")
            print("  --list         List all backups")
            print("  --log [N]      Show last N log entries (default: 20)")
            print("  --verify FILE  Verify backup integrity")
    else:
        # Default: create backup
        scheduler.create_backup()


if __name__ == '__main__':
    main()
