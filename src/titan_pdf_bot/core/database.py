import sqlite3
import threading
import os
import json
from datetime import datetime
from titan_pdf_bot.core.config import AdvancedConfig


class AdvancedDatabase:
    def __init__(self):
        self.db_path = AdvancedConfig.DB_FILE
        self.lock = threading.Lock()
        self.init_database()

    def init_database(self):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                language TEXT DEFAULT 'ar',
                join_date TEXT,
                last_active TEXT,
                total_operations INTEGER DEFAULT 0,
                total_size INTEGER DEFAULT 0,
                is_premium INTEGER DEFAULT 0,
                is_blocked INTEGER DEFAULT 0,
                settings TEXT DEFAULT '{}'
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                operation_type TEXT,
                file_name TEXT,
                file_size INTEGER,
                processing_time REAL,
                status TEXT,
                timestamp TEXT,
                details TEXT
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS statistics (
                date TEXT PRIMARY KEY,
                total_users INTEGER DEFAULT 0,
                total_operations INTEGER DEFAULT 0,
                total_size INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS sessions (
                user_id TEXT PRIMARY KEY,
                data TEXT,
                last_activity REAL
            )''')
            conn.commit()

    def execute(self, query, params=(), commit=False):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            if commit:
                conn.commit()
            return cursor.fetchall()

    def register_user(self, user):
        user_id = str(user.id)
        first_name = user.first_name or ""
        username = f"@{user.username}" if user.username else "غير معروف"
        join_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.execute(
            '''INSERT OR IGNORE INTO users (user_id, first_name, username, join_date, last_active)
               VALUES (?, ?, ?, ?, ?)''',
            (user_id, first_name, username, join_date, join_date),
            commit=True
        )

    def log_operation(self, user_id, operation_type, file_name="", file_size=0,
                      processing_time=0, status="ناجح", details=""):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.execute(
            '''INSERT INTO operations
               (user_id, operation_type, file_name, file_size, processing_time, status, timestamp, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (str(user_id), operation_type, file_name, file_size, processing_time, status, timestamp, details),
            commit=True
        )
        self.execute(
            '''UPDATE users SET total_operations = total_operations + 1,
               total_size = total_size + ?, last_active = ? WHERE user_id = ?''',
            (file_size, timestamp, str(user_id)),
            commit=True
        )

    def get_user_stats(self, user_id):
        result = self.execute(
            '''SELECT total_operations, total_size, join_date, is_premium
               FROM users WHERE user_id = ?''',
            (str(user_id),)
        )
        return result[0] if result else (0, 0, "غير متاح", 0)

    def get_system_stats(self):
        total_users = self.execute("SELECT COUNT(*) FROM users")[0][0]
        total_ops = self.execute("SELECT COUNT(*) FROM operations")[0][0]
        total_size = self.execute("SELECT COALESCE(SUM(total_size), 0) FROM users")[0][0]
        try:
            today_ops = self.execute("SELECT COUNT(*) FROM operations WHERE date(timestamp) = date('now')")[0][0]
            active_users = self.execute(
                "SELECT COUNT(DISTINCT user_id) FROM operations WHERE date(timestamp) = date('now')"
            )[0][0]
        except Exception:
            today_ops = 0
            active_users = 0

        return {
            'total_users': total_users,
            'total_operations': total_ops,
            'total_size': total_size,
            'today_operations': today_ops,
            'active_users': active_users
        }

    def backup_database(self):
        backup_path = os.path.join(
            AdvancedConfig.BACKUP_DIR,
            f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )
        with self.lock:
            with sqlite3.connect(self.db_path) as source_conn, sqlite3.connect(backup_path) as backup_conn:
                source_conn.backup(backup_conn)
                backup_conn.commit()
        return backup_path

    def toggle_block_user(self, user_id):
        current_status = self.execute("SELECT is_blocked FROM users WHERE user_id = ?", (str(user_id),))
        if not current_status:
            return None
        new_status = 1 if current_status[0][0] == 0 else 0
        self.execute("UPDATE users SET is_blocked = ? WHERE user_id = ?", (new_status, str(user_id)), commit=True)
        return new_status

    def is_user_blocked(self, user_id):
        res = self.execute("SELECT is_blocked FROM users WHERE user_id = ?", (str(user_id),))
        return res and res[0][0] == 1

    def delete_user(self, user_id):
        self.execute("DELETE FROM users WHERE user_id = ?", (str(user_id),), commit=True)

    def save_session(self, user_id, data, last_activity):
        self.execute(
            "INSERT OR REPLACE INTO sessions (user_id, data, last_activity) VALUES (?, ?, ?)",
            (str(user_id), json.dumps(data), last_activity),
            commit=True
        )

    def load_all_sessions(self):
        return self.execute("SELECT user_id, data, last_activity FROM sessions")

    def delete_session(self, user_id):
        self.execute("DELETE FROM sessions WHERE user_id = ?", (str(user_id),), commit=True)


db = AdvancedDatabase()
