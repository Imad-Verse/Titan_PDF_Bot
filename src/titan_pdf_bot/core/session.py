import time
import shutil
import os
import threading
import json
from collections import defaultdict
from titan_pdf_bot.core.config import AdvancedConfig
from titan_pdf_bot.core.logger import logger
from titan_pdf_bot.core.database import db


class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.user_activity = {}
        self.rate_limits = defaultdict(list)
        self.lock = threading.RLock()
        self._load_from_db()

    def _load_from_db(self):
        """تحميل الجلسات المحفوظة من قاعدة البيانات عند بدء التشغيل"""
        try:
            stored_sessions = db.load_all_sessions()
            with self.lock:
                for user_id, data, last_activity in stored_sessions:
                    try:
                        self.sessions[user_id] = json.loads(data)
                        self.user_activity[user_id] = last_activity
                    except Exception:
                        continue
            logger.log('info', f"✅ تم استعادة {len(self.sessions)} جلسة من قاعدة البيانات")
        except Exception as e:
            logger.log('error', f"❌ فشل تحميل الجلسات من قاعدة البيانات: {e}")

    def create_session(self, user_id, mode, **kwargs):
        with self.lock:
            self.sessions[user_id] = {
                'mode': mode,
                'files': [],
                'text_parts': [],
                'step': 'input',
                'created_at': time.time(),
                'last_activity': time.time(),
                **kwargs
            }
            self.user_activity[user_id] = time.time()
            db.save_session(user_id, self.sessions[user_id], self.user_activity[user_id])

    def get_session(self, user_id):
        with self.lock:
            return self.sessions.get(user_id)

    def update_session(self, user_id, **kwargs):
        with self.lock:
            if user_id in self.sessions:
                self.sessions[user_id].update(kwargs)
                self.sessions[user_id]['last_activity'] = time.time()
                self.user_activity[user_id] = time.time()
                db.save_session(user_id, self.sessions[user_id], self.user_activity[user_id])

    def clear_session(self, user_id):
        with self.lock:
            if user_id in self.sessions:
                try:
                    user_dir = os.path.join(AdvancedConfig.TEMP_DIR, str(user_id))
                    if os.path.exists(user_dir):
                        shutil.rmtree(user_dir, ignore_errors=True)
                except Exception as e:
                    logger.log('error', f"خطأ في حذف ملفات المستخدم: {e}", user_id)
                self.sessions.pop(user_id, None)
                db.delete_session(user_id)
            self.user_activity.pop(user_id, None)

    def check_rate_limit(self, user_id):
        now = time.time()
        with self.lock:
            self.rate_limits[user_id] = [
                req for req in self.rate_limits.get(user_id, []) if now - req < 60
            ]
            if len(self.rate_limits[user_id]) >= AdvancedConfig.RATE_LIMIT_PER_USER:
                return False
            self.rate_limits[user_id].append(now)
            return True

    def cleanup_inactive_sessions(self):
        now = time.time()
        with self.lock:
            inactive = [
                uid for uid, last in self.user_activity.items()
                if now - last > AdvancedConfig.SESSION_TIMEOUT
            ]
            for uid, requests in list(self.rate_limits.items()):
                recent_requests = [req for req in requests if now - req < 60]
                if recent_requests:
                    self.rate_limits[uid] = recent_requests
                else:
                    self.rate_limits.pop(uid, None)

        for uid in inactive:
            self.clear_session(uid)

        return len(inactive)


session_manager = SessionManager()
