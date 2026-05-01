import os
import re
from titan_pdf_bot.core.config import AdvancedConfig
from titan_pdf_bot.core.loader import bot


def is_maintenance_mode():
    return os.path.exists(AdvancedConfig.MAINTENANCE_FILE)


def set_maintenance_mode(enable=True):
    if enable:
        with open(AdvancedConfig.MAINTENANCE_FILE, 'w', encoding='utf-8') as f:
            f.write("1")
    elif os.path.exists(AdvancedConfig.MAINTENANCE_FILE):
        os.remove(AdvancedConfig.MAINTENANCE_FILE)


def get_missing_channels(user_id):
    missing = []
    for channel in AdvancedConfig.REQUIRED_CHANNELS:
        try:
            status = bot.get_chat_member(channel, user_id).status
            if status not in ['member', 'administrator', 'creator']:
                missing.append(channel)
        except Exception:
            missing.append(channel)
    return missing


def is_valid_page_range(value):
    if not value:
        return False
    return re.fullmatch(r"\d+(\s*-\s*\d+)?", value.strip()) is not None


def format_duration(seconds):
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    parts = []
    if days:
        parts.append(f"{days} يوم")
    if hours:
        parts.append(f"{hours} ساعة")
    if minutes:
        parts.append(f"{minutes} دقيقة")
    parts.append(f"{seconds} ثانية")
    return " ".join(parts)
