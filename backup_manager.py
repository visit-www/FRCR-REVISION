#!/usr/bin/env python3
"""
Comprehensive Database Backup Management System
Handles automated backups, restoration, and database change tracking
"""

import os
import shutil
from datetime import datetime, timedelta
import sqlite3
import json
from threading import Thread
import time

class DatabaseBackupManager:
    """Centralized backup management with automatic scheduling"""
    
    def __init__(self, app_context=None):
        """Initialize backup manager
        
        Args:
            app_context: Flask app context for database operations
        """
        self.db_path = os.path.join(os.path.dirname(__file__), 'instance', 'frcr_examiner.db')
        self.backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
        self.log_path = os.path.join(self.backup_dir, 'backup_log.txt')
        self.metadata_path = os.path.join(self.backup_dir, 'backups_metadata.json')
        self.app_context = app_context
        
        os.makedirs(self.backup_dir, exist_ok=True)
        self._load_metadata()
    
    def _load_metadata(self):
        """Load backup metadata from JSON file"""
        if os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, 'r') as f:
                    self.metadata = json.load(f)
            except:
                self.metadata = {}
        else:
            self.metadata = {}
    
    def _save_metadata(self):
        """Save backup metadata to JSON file"""
        with open(self.metadata_path, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def log_event(self, message, level='INFO'):
        """Log backup event with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] [{level}] {message}"
        
        print(log_message)
        
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
            self.log_event(f"Database integrity check failed: {e}", 'WARNING')
            return False
    
    def create_backup(self, description=""):
        """Create a backup with metadata
        
        Args:
            description: Optional description of the backup
            
        Returns:
            dict: Backup information or None if failed
        """
        
        if not os.path.exists(self.db_path):
            self.log_event(f"Database file not found: {self.db_path}", 'ERROR')
            return None
        
        try:
            if not self.verify_database(self.db_path):
                self.log_event("Database integrity check failed, proceeding with backup anyway", 'WARNING')
            
            # Create timestamped backup
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f'frcr_examiner_backup_{timestamp}.db'
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Copy database
            shutil.copy2(self.db_path, backup_path)
            
            # Verify backup
            if not self.verify_database(backup_path):
                os.remove(backup_path)
                self.log_event("Backup verification failed, backup deleted", 'ERROR')
                return None
            
            size_kb = os.path.getsize(backup_path) / 1024
            
            # Get database stats
            db_stats = self._get_database_stats()
            
            # Store metadata
            backup_info = {
                'filename': backup_filename,
                'timestamp': timestamp,
                'size_kb': size_kb,
                'description': description,
                'database_stats': db_stats,
                'verified': True
            }
            
            self.metadata[timestamp] = backup_info
            self._save_metadata()
            
            self.log_event(f"Backup created: {backup_filename} ({size_kb:.2f} KB)", 'INFO')
            
            # Apply retention policy
            self.apply_retention_policy()
            
            return backup_info
            
        except Exception as e:
            self.log_event(f"Backup creation failed: {e}", 'ERROR')
            return None
    
    def _get_database_stats(self):
        """Get current database statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {
                'timestamp': datetime.now().isoformat(),
                'tables': {}
            }
            
            # Get table names and row counts
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                stats['tables'][table_name] = row_count
            
            conn.close()
            return stats
        except:
            return {}
    
    def get_backup_list(self):
        """Get list of all backups with metadata
        
        Returns:
            list: List of backup dictionaries
        """
        backups = []
        
        for timestamp, info in sorted(self.metadata.items(), reverse=True):
            backup_path = os.path.join(self.backup_dir, info['filename'])
            if os.path.exists(backup_path):
                info['exists'] = True
                backups.append(info)
        
        return backups
    
    def restore_backup(self, timestamp, create_safety_backup=True):
        """Restore database from backup
        
        Args:
            timestamp: Backup timestamp (key in metadata)
            create_safety_backup: Whether to backup current DB before restoring
            
        Returns:
            dict: Result information
        """
        
        if timestamp not in self.metadata:
            self.log_event(f"Backup not found: {timestamp}", 'ERROR')
            return {'success': False, 'message': 'Backup not found'}
        
        backup_info = self.metadata[timestamp]
        backup_path = os.path.join(self.backup_dir, backup_info['filename'])
        
        if not os.path.exists(backup_path):
            self.log_event(f"Backup file missing: {backup_info['filename']}", 'ERROR')
            return {'success': False, 'message': 'Backup file not found'}
        
        try:
            # Create safety backup of current database
            if create_safety_backup and os.path.exists(self.db_path):
                safety_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safety_path = f"{self.db_path}.before_restore_{safety_timestamp}"
                shutil.copy2(self.db_path, safety_path)
                self.log_event(f"Safety backup created: {safety_path}", 'INFO')
            
            # Verify backup before restore
            if not self.verify_database(backup_path):
                return {'success': False, 'message': 'Backup integrity check failed'}
            
            # Restore backup
            shutil.copy2(backup_path, self.db_path)
            
            # Verify restored database
            if not self.verify_database(self.db_path):
                self.log_event("Restored database failed integrity check", 'ERROR')
                return {'success': False, 'message': 'Restored database integrity check failed'}
            
            size_kb = os.path.getsize(self.db_path) / 1024
            
            self.log_event(f"Database restored from: {backup_info['filename']}", 'INFO')
            
            return {
                'success': True,
                'message': f"Database restored successfully",
                'backup_info': backup_info,
                'size_kb': size_kb
            }
            
        except Exception as e:
            self.log_event(f"Restore failed: {e}", 'ERROR')
            return {'success': False, 'message': f'Restore failed: {e}'}
    
    def apply_retention_policy(self, max_backups=6):
        """Apply retention policy to backups
        
        Args:
            max_backups: Maximum number of backups to keep (default: 6, keeps last 5-7)
        """
        
        backups = sorted([f for f in os.listdir(self.backup_dir) if f.endswith('.db')])
        
        if len(backups) <= max_backups:
            return
        
        # Keep most recent N backups (default 6)
        for backup in backups[:-max_backups]:
            backup_path = os.path.join(self.backup_dir, backup)
            try:
                os.remove(backup_path)
                self.log_event(f"Deleted old backup: {backup}", 'INFO')
                
                # Remove from metadata
                for ts in list(self.metadata.keys()):
                    if self.metadata[ts]['filename'] == backup:
                        del self.metadata[ts]
                        self._save_metadata()
                        break
                        
            except Exception as e:
                self.log_event(f"Failed to delete {backup}: {e}", 'WARNING')
    
    def get_statistics(self):
        """Get backup system statistics
        
        Returns:
            dict: Statistics about backups
        """
        backups = sorted([f for f in os.listdir(self.backup_dir) if f.endswith('.db')])
        
        total_size = 0
        for backup in backups:
            backup_path = os.path.join(self.backup_dir, backup)
            total_size += os.path.getsize(backup_path)
        
        # Get database stats
        db_stats = self._get_database_stats()
        
        return {
            'total_backups': len(backups),
            'oldest_backup': min([os.path.getmtime(os.path.join(self.backup_dir, b)) for b in backups]) if backups else None,
            'newest_backup': max([os.path.getmtime(os.path.join(self.backup_dir, b)) for b in backups]) if backups else None,
            'total_size_kb': total_size / 1024,
            'total_size_mb': total_size / (1024 * 1024),
            'database_tables': db_stats.get('tables', {}),
            'backup_count': len(backups)
        }
    
    def get_log(self, lines=50):
        """Get recent log entries
        
        Args:
            lines: Number of lines to return
            
        Returns:
            list: Log entries
        """
        if not os.path.exists(self.log_path):
            return []
        
        with open(self.log_path, 'r') as f:
            all_lines = f.readlines()
        
        return all_lines[-lines:]
    
    def start_auto_backup_scheduler(self, interval_hours=24):
        """Start automatic backup scheduler in background thread
        
        Args:
            interval_hours: Hours between backups (default 24 = daily)
        """
        def backup_loop():
            while True:
                try:
                    self.create_backup(description="Automatic scheduled backup")
                except Exception as e:
                    self.log_event(f"Auto-backup failed: {e}", 'ERROR')
                
                # Sleep for specified hours
                time.sleep(interval_hours * 3600)
        
        # Start backup thread as daemon (exits when main app exits)
        backup_thread = Thread(target=backup_loop, daemon=True)
        backup_thread.start()
        self.log_event(f"Auto-backup scheduler started (interval: {interval_hours}h)", 'INFO')


# Global instance
backup_manager = None

def init_backup_manager(app):
    """Initialize backup manager with Flask app
    
    Args:
        app: Flask application instance
    """
    global backup_manager
    backup_manager = DatabaseBackupManager(app)
    
    # Skip backups in serverless environment (Vercel, AWS Lambda, etc.)
    # These environments have ephemeral storage that gets wiped anyway
    is_serverless = os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME')
    
    if not is_serverless:
        # Create startup backup (always create on app start)
        try:
            backup_manager.create_backup(description="Auto backup on app startup")
        except Exception as e:
            print(f"Warning: Could not create startup backup: {e}")
        
        # Start automatic daily backups (24-hour interval)
        try:
            backup_manager.start_auto_backup_scheduler(interval_hours=24)
        except Exception as e:
            print(f"Warning: Could not start backup scheduler: {e}")
    
    return backup_manager

def get_backup_manager():
    """Get global backup manager instance"""
    global backup_manager
    return backup_manager
