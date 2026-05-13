import logging
import os
from datetime import datetime
from rich.console import Console
from rich.theme import Theme
from logging.handlers import RotatingFileHandler
from titan_pdf_bot.core.config import AdvancedConfig

# --- Professional Logging System ---
custom_theme = Theme({
    "info": "cyan",
    "warning": "bold yellow",
    "error": "bold red",
    "success": "bold green",
})

console = Console(theme=custom_theme)
LEVEL_MAP = {"DEBUG": 10, "INFO": 20, "SUCCESS": 25, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}

class AdvancedLogger:
    def __init__(self):
        self.logger = logging.getLogger("TitanPDFBot")
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler = RotatingFileHandler(
                AdvancedConfig.LOG_FILE, 
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            self.logger.propagate = False

        self.log_level = os.getenv("TITAN_LOG_LEVEL", "INFO").upper()
        self.current_level = LEVEL_MAP.get(self.log_level, 20)

    def _should_print(self, level_name):
        return LEVEL_MAP.get(level_name, 20) >= self.current_level

    def log(self, level, message, user_id=None):
        level = level.lower()
        if level == "success": level = "info" # Map success to info for standard logger
        
        user_info = f"UID:{user_id} - " if user_id else ""
        full_msg = f"{user_info}{message}"
        
        # File Logging
        getattr(self.logger, level)(full_msg)
        
        # Console Logging
        level_upper = level.upper()
        if "success" in message.lower() or level_upper == "SUCCESS":
            style = "success"
            tag = "✅"
            msg_level = "SUCCESS"
        elif level_upper == "ERROR":
            style = "error"
            tag = "❌"
            msg_level = "ERROR"
        elif level_upper == "WARNING":
            style = "warning"
            tag = "⚠️"
            msg_level = "WARNING"
        else:
            style = "info"
            tag = "ℹ️"
            msg_level = "INFO"

        if self._should_print(msg_level):
            console.print(f"[dim]{datetime.now().strftime('%H:%M:%S')}[/dim] {tag} {full_msg}", style=style)

logger = AdvancedLogger()
