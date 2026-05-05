import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv


def _find_base_dir() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "requirements.txt").exists() or (parent / "assets").exists():
            return parent
    return current.parents[3] if len(current.parents) > 3 else current.parent


BASE_DIR_PATH = _find_base_dir()
load_dotenv(BASE_DIR_PATH / ".env")


class AdvancedConfig:
    API_TOKEN = os.getenv('PDF_BOT_TOKEN')

    if not API_TOKEN:
        print("? ???: PDF_BOT_TOKEN ??? ????? ?? ??? .env!")
        sys.exit(1)

    ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
    ADMINS = [int(x) for x in os.getenv('ADMINS', '').split(',') if x.strip()]
    if ADMIN_ID and ADMIN_ID not in ADMINS:
        ADMINS.append(ADMIN_ID)

    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '@Admin')
    REQUIRED_CHANNELS = [
        ch.strip() for ch in os.getenv('REQUIRED_CHANNELS', '').split(',')
        if ch.strip()
    ]

    BASE_DIR = str(BASE_DIR_PATH)

    STORAGE_DIR = os.path.join(BASE_DIR, "storage")
    TEMP_DIR = os.path.join(STORAGE_DIR, "temp")
    DB_FILE = os.path.join(STORAGE_DIR, "database", "titan_v8_ultimate.db")
    LOG_FILE = os.path.join(BASE_DIR, "logs", "system.log")
    BACKUP_DIR = os.path.join(STORAGE_DIR, "backups")
    USER_DATA_DIR = os.path.join(STORAGE_DIR, "users")
    MAINTENANCE_FILE = os.path.join(STORAGE_DIR, "maintenance_mode.flag")
    RESTART_LOG_FILE = os.path.join(STORAGE_DIR, "restart_log.txt")

    MAX_FILE_SIZE = 20 * 1024 * 1024  # Deprecated, use MAX_DOWNLOAD_SIZE
    MAX_DOWNLOAD_SIZE = 20 * 1024 * 1024  # حد التحميل الرسمي لتيليجرام (20 ميجابايت)
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024    # حد الإرسال الرسمي لتيليجرام (50 ميجابايت)
    MAX_FILES_PER_USER = 20
    CLEANUP_INTERVAL = 1800
    SESSION_TIMEOUT = 3600

    THREAD_POOL_SIZE = 100
    MAX_CONCURRENT_TASKS = 4   # أقصى عدد لعمليات المعالجة الثقيلة في نفس الوقت
    REQUEST_TIMEOUT = 90
    RATE_LIMIT_PER_USER = 10

    ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.txt', '.doc', '.docx'}
    BLOCKED_USERS_FILE = os.path.join(BASE_DIR, "blocked_users.json")

    START_TIME = time.time()


# Enforce working directory to be the bot's directory
try:
    os.chdir(AdvancedConfig.BASE_DIR)
except Exception as e:
    print(f"?? Warning: Could not set working directory to {AdvancedConfig.BASE_DIR}: {e}")

# Create necessary directories
LOGS_DIR = os.path.dirname(AdvancedConfig.LOG_FILE)
DB_DIR = os.path.dirname(AdvancedConfig.DB_FILE)

for folder in [AdvancedConfig.STORAGE_DIR, AdvancedConfig.TEMP_DIR, AdvancedConfig.BACKUP_DIR,
               AdvancedConfig.USER_DATA_DIR, LOGS_DIR, DB_DIR]:
    os.makedirs(folder, exist_ok=True)
