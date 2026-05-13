import os
import sqlite3
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from titan_pdf_bot.core.config import AdvancedConfig
from titan_pdf_bot.core.logger import logger
from titan_pdf_bot.core.loader import bot
from titan_pdf_bot.core.database import db

class BackupService:
    """
    Professional Backup Service for Titan PDF Bot.
    Handles online backups, asynchronous execution, and automated cleanup.
    """
    _executor = ThreadPoolExecutor(max_workers=2)

    @classmethod
    def perform_backup_async(cls, chat_id=None):
        """
        Triggers the backup process in a background thread to prevent bot lag.
        
        Args:
            chat_id (int, optional): The chat ID to send the backup to. 
                                    Defaults to the main ADMIN_ID if not provided.
        """
        cls._executor.submit(cls._run_backup_flow, chat_id)

    @classmethod
    def _run_backup_flow(cls, chat_id):
        """Core backup workflow: Create -> Send -> Cleanup."""
        try:
            logger.log("info", "🔄 Starting professional database backup...")
            
            # 1. Create Online Backup
            backup_path = cls._create_online_backup()
            
            # 2. Send to Admin
            target_id = chat_id or AdvancedConfig.ADMIN_ID
            if target_id:
                cls._send_backup_to_admin(target_id, backup_path)
            
            # 3. Cleanup Old Backups (Retention: 7 days)
            cls.cleanup_old_backups()
            
            logger.log("success", f"✅ Backup completed and stored at: {backup_path}")
        except Exception as e:
            logger.log("error", f"❌ Backup failed: {str(e)}")
            if chat_id:
                try:
                    bot.send_message(chat_id, f"❌ <b>فشل النسخ الاحتياطي:</b>\n<code>{str(e)}</code>", parse_mode='HTML')
                except: pass

    @classmethod
    def _create_online_backup(cls) -> str:
        """
        Creates a safe backup of the SQLite database using the backup() API.
        This method is thread-safe and works while the database is in use.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"titan_backup_{timestamp}.db"
        backup_path = os.path.join(AdvancedConfig.BACKUP_DIR, backup_filename)
        
        # Ensure backup directory exists
        os.makedirs(AdvancedConfig.BACKUP_DIR, exist_ok=True)
        
        # Using sqlite3.backup() for a safe online backup
        with db.lock:
            with sqlite3.connect(db.db_path) as source:
                with sqlite3.connect(backup_path) as destination:
                    source.backup(destination)
        return backup_path

    @classmethod
    def _send_backup_to_admin(cls, chat_id, file_path):
        """Sends the backup file via Telegram."""
        try:
            with open(file_path, 'rb') as f:
                bot.send_document(
                    chat_id, f,
                    caption=f"💾 <b>نسخة احتياطية احترافية</b>\n\n"
                            f"📅 <b>التاريخ:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
                            f"📄 <b>الملف:</b> <code>{os.path.basename(file_path)}</code>\n"
                            f"⚙️ <b>الحالة:</b> ناجح ✅",
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.log("error", f"❌ Failed to send backup to admin {chat_id}: {e}")

    @classmethod
    def cleanup_old_backups(cls):
        """
        Deletes backup files older than 7 days from the storage directory.
        Uses dynamic paths and handles errors gracefully.
        """
        try:
            now = time.time()
            retention_period = 7 * 24 * 60 * 60  # 7 days in seconds
            
            if not os.path.exists(AdvancedConfig.BACKUP_DIR):
                return

            deleted_count = 0
            for filename in os.listdir(AdvancedConfig.BACKUP_DIR):
                file_path = os.path.join(AdvancedConfig.BACKUP_DIR, filename)
                
                # Check if it's a file and if it's a backup (to avoid deleting other things)
                if os.path.isfile(file_path) and filename.startswith("titan_backup_"):
                    if now - os.path.getmtime(file_path) > retention_period:
                        os.remove(file_path)
                        deleted_count += 1
            
            if deleted_count > 0:
                logger.log("info", f"🧹 Backup Cleanup: Removed {deleted_count} old backup files.")
        except Exception as e:
            logger.log("error", f"❌ Error during backup cleanup: {e}")

# Global instance for easy access
backup_service = BackupService()
