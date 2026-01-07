#!/usr/bin/env python3
"""
Local Backup Manager
Helps users manage their downloaded backups on their local computer
Usage: python manage_local_backups.py <backup_directory>
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

def get_backup_files(directory):
    """Get all backup JSON files in directory"""
    backup_dir = Path(directory)
    if not backup_dir.exists():
        print(f"Error: Directory {directory} does not exist")
        return []
    
    # Find all backup JSON files
    backups = []
    for file in backup_dir.glob('frcr_examiner_backup_*.json'):
        try:
            # Get file info
            stat = file.stat()
            backups.append({
                'path': file,
                'name': file.name,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'created': datetime.fromtimestamp(stat.st_ctime)
            })
        except Exception as e:
            print(f"Warning: Could not read {file.name}: {e}")
    
    # Sort by creation time (newest first)
    backups.sort(key=lambda x: x['created'], reverse=True)
    return backups

def format_size(size_bytes):
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def list_backups(directory):
    """List all backups with details"""
    backups = get_backup_files(directory)
    
    if not backups:
        print("No backup files found in this directory.")
        return
    
    print(f"\nFound {len(backups)} backup(s):\n")
    print(f"{'#':<4} {'Filename':<50} {'Size':<12} {'Created':<20}")
    print("-" * 86)
    
    for i, backup in enumerate(backups, 1):
        print(f"{i:<4} {backup['name']:<50} {format_size(backup['size']):<12} {backup['created'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    total_size = sum(b['size'] for b in backups)
    print("-" * 86)
    print(f"Total: {len(backups)} files, {format_size(total_size)}")

def cleanup_old_backups(directory, keep_count=5):
    """Keep only the most recent N backups"""
    backups = get_backup_files(directory)
    
    if len(backups) <= keep_count:
        print(f"\nYou have {len(backups)} backup(s). No cleanup needed (keeping {keep_count}).")
        return
    
    # Backups to delete
    to_delete = backups[keep_count:]
    
    print(f"\nYou have {len(backups)} backups. Keeping the {keep_count} most recent.")
    print(f"\nThe following {len(to_delete)} backup(s) will be DELETED:")
    
    for i, backup in enumerate(to_delete, 1):
        print(f"{i}. {backup['name']} ({backup['created'].strftime('%Y-%m-%d %H:%M:%S')})")
    
    # Confirm deletion
    response = input(f"\nDelete these {len(to_delete)} old backup(s)? (yes/no): ").strip().lower()
    
    if response == 'yes':
        deleted_count = 0
        deleted_size = 0
        
        for backup in to_delete:
            try:
                backup['path'].unlink()
                deleted_count += 1
                deleted_size += backup['size']
                print(f"✓ Deleted: {backup['name']}")
            except Exception as e:
                print(f"✗ Error deleting {backup['name']}: {e}")
        
        print(f"\nCleanup complete: Deleted {deleted_count} file(s), freed {format_size(deleted_size)}")
    else:
        print("Cleanup cancelled.")

def verify_backup(backup_file):
    """Verify a backup file is valid"""
    try:
        with open(backup_file, 'r') as f:
            data = json.load(f)
        
        # Check required fields
        if 'metadata' not in data:
            print("Error: Missing metadata")
            return False
        
        if 'backup_date' not in data['metadata']:
            print("Error: Missing backup date")
            return False
        
        # Count records
        tables = ['users', 'exam_sessions', 'packets', 'cases', 'candidates', 'case_images', 'questions', 'answers']
        
        print(f"\nBackup file: {Path(backup_file).name}")
        print(f"Backup date: {data['metadata']['backup_date']}")
        print(f"Database type: {data['metadata'].get('database_type', 'unknown')}")
        print("\nRecord counts:")
        
        total_records = 0
        for table in tables:
            count = len(data.get(table, []))
            total_records += count
            print(f"  {table}: {count}")
        
        print(f"\nTotal records: {total_records}")
        print("\n✓ Backup file is valid!")
        return True
        
    except json.JSONDecodeError:
        print("Error: Invalid JSON file")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Local Backup Manager for FRCR Examiner")
        print("\nUsage:")
        print("  python manage_local_backups.py <backup_directory> [command]")
        print("\nCommands:")
        print("  list     - List all backups (default)")
        print("  cleanup  - Delete old backups, keeping only the 5 most recent")
        print("  verify   - Verify a specific backup file")
        print("\nExamples:")
        print("  python manage_local_backups.py ~/Downloads")
        print("  python manage_local_backups.py ~/Downloads cleanup")
        print("  python manage_local_backups.py ~/Downloads/backup.json verify")
        sys.exit(1)
    
    path = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else 'list'
    
    if command == 'list':
        list_backups(path)
    elif command == 'cleanup':
        cleanup_old_backups(path, keep_count=5)
    elif command == 'verify':
        verify_backup(path)
    else:
        print(f"Unknown command: {command}")
        print("Available commands: list, cleanup, verify")
        sys.exit(1)

if __name__ == '__main__':
    main()
