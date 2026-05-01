import time
import shutil
import os
import threading
from collections import defaultdict
from titan_pdf_bot.core.config import AdvancedConfig
from titan_pdf_bot.core.logger import logger


class SessionManager:
    def __init__(self):
        self.sessions = defaultdict(dict)
        self.user_activity = {}
        self.rate_limits = defaultdict(list)
        self.lock = threading.RLock()

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

    def get_session(self, user_id):
        with self.lock:
            return self.sessions.get(user_id)

    def update_session(self, user_id, **kwargs):
        with self.lock:
            if user_id in self.sessions:
                self.sessions[user_id].update(kwargs)
                self.sessions[user_id]['last_activity'] = time.time()
                self.user_activity[user_id] = time.time()

    def clear_session(self, user_id):
        with self.lock:
            if user_id in self.sessions:
                try:
                    user_dir = os.path.join(AdvancedConfig.TEMP_DIR, str(user_id))
                    if os.path.exists(user_dir):
                        shutil.rmtree(user_dir, ignore_errors=True)
                except Exception as e:
                    logger.log('error', f"??? ?? ????? ???? ????????: {e}", user_id)
                self.sessions.pop(user_id, None)
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
            with self.lock:
                self.user_activity.pop(uid, None)

        return len(inactive)


session_manager = SessionManager()
