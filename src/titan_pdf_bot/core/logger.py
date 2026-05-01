import logging
from logging.handlers import RotatingFileHandler
from titan_pdf_bot.core.config import AdvancedConfig


class AdvancedLogger:
    def __init__(self):
        self.logger = logging.getLogger("TitanPDFBot")
        if self.logger.handlers:
            return

        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Use RotatingFileHandler to prevent log bloat
        file_handler = RotatingFileHandler(
            AdvancedConfig.LOG_FILE, 
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.propagate = False

    def log(self, level, message, user_id=None):
        user_info = f"????????:{user_id} - " if user_id else ""
        getattr(self.logger, level)(f"{user_info}{message}")


logger = AdvancedLogger()
