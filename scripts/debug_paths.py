import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from titan_pdf_bot.core.config import AdvancedConfig
    print(f"BASE_DIR: {AdvancedConfig.BASE_DIR}")
    print(f"STORAGE_DIR: {AdvancedConfig.STORAGE_DIR}")
    print(f"TEMP_DIR: {AdvancedConfig.TEMP_DIR}")
    print(f"DB_FILE: {AdvancedConfig.DB_FILE}")
    print(f"LOG_FILE: {AdvancedConfig.LOG_FILE}")
    print(f"RESTART_LOG_FILE: {AdvancedConfig.RESTART_LOG_FILE}")
    print(f"Current Working Directory: {os.getcwd()}")
except Exception as e:
    print(f"Error: {e}")
