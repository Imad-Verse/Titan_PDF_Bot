import threading
import time
import os
import shutil
from datetime import datetime
from titan_pdf_bot.core.config import AdvancedConfig
from titan_pdf_bot.core.logger import logger
from titan_pdf_bot.core.session import session_manager
from titan_pdf_bot.core.database import db


class AdvancedCleanupSystem:
    def __init__(self):
        self.running = True

    def start(self):
        def cleanup_loop():
            while self.running:
                try:
                    session_manager.cleanup_inactive_sessions()
                    self.cleanup_temp_files()
                    self.update_system_stats()
                    
                    # New: Professional Backup Cleanup
                    from titan_pdf_bot.services.backup import BackupService
                    BackupService.cleanup_old_backups()
                except Exception as e:
                    logger.log('error', f"? Cleanup Error: {e}")
                time.sleep(AdvancedConfig.CLEANUP_INTERVAL)

        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()

    def cleanup_temp_files(self):
        now = time.time()
        if not os.path.exists(AdvancedConfig.TEMP_DIR):
            return
        for user_dir in os.listdir(AdvancedConfig.TEMP_DIR):
            dir_path = os.path.join(AdvancedConfig.TEMP_DIR, user_dir)
            if os.path.isdir(dir_path):
                if now - os.path.getmtime(dir_path) > 86400:
                    shutil.rmtree(dir_path, ignore_errors=True)

    def update_system_stats(self):
        try:
            stats = db.get_system_stats()
            date = datetime.now().strftime('%Y-%m-%d')
            db.execute(
                '''INSERT OR REPLACE INTO statistics (date, total_users, total_operations, total_size, active_users)
                   VALUES (?, ?, ?, ?, ?)''',
                (date, stats['total_users'], stats['total_operations'], stats['total_size'], stats['active_users']),
                commit=True
            )
        except Exception:
            pass


cleanup_system = AdvancedCleanupSystem()
