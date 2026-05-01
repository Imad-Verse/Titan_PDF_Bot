import io
import os
import sys
import time

from telebot import types

from titan_pdf_bot.core.config import AdvancedConfig
from titan_pdf_bot.core.loader import bot
from titan_pdf_bot.core.logger import logger
from titan_pdf_bot.services.cleanup import cleanup_system
from titan_pdf_bot import handlers  # Registers handlers


def configure_bot_commands():
    commands = [
        types.BotCommand("start", "بدء البوت"),
        types.BotCommand("help", "دليل المساعدة"),
        types.BotCommand("bots", "🤖 قائمة بوتاتنا"),
        types.BotCommand("contact", "مراسلة المطور"),
    ]
    bot.set_my_commands(commands)
    logger.log("info", "✅ Telegram command menu configured")


def start_bot_safe():
    logger.log("info", "🚀 System is initializing...")

    # Restart handling
    if os.path.exists(AdvancedConfig.RESTART_LOG_FILE):
        try:
            with open(AdvancedConfig.RESTART_LOG_FILE, "r", encoding="utf-8") as f:
                cid_text = f.read().strip()
            cid = int(cid_text) if cid_text else 0
            if cid:
                bot.send_message(cid, "🚀 <b>Bot Restarted Successfully!</b>\nSystem is back online.", parse_mode="HTML")
            os.remove(AdvancedConfig.RESTART_LOG_FILE)
        except Exception as e:
            logger.log("error", f"❌ Error handling restart log: {e}")

    # Start cleanup system
    cleanup_system.start()
    logger.log("info", "🧹 Background services & cleanup scheduled")

    try:
        configure_bot_commands()
    except Exception as e:
        logger.log("error", f"❌ Failed to configure bot commands: {e}")

    retry_delay = 10
    while True:
        try:
            logger.log("info", "🚀 Bot is online and ready to serve!")

            print("\n==================================================")
            print("      💡  B O T   I S   R U N N I N G  💡")
            print("==================================================\n")

            # Reset delay on successful start
            retry_delay = 10
            bot.polling(none_stop=True, interval=0, timeout=120)
        except Exception as e:
            logger.log("error", f"❌ Connection or Polling Error: {e}")
            logger.log("info", f"🔄 Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            # Exponential backoff: 30s, 60s, 120s, max 300s (5 min)
            if retry_delay < 30:
                retry_delay = 30
            else:
                retry_delay = min(retry_delay * 2, 300)


def main():
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

    print("\n==================================================")
    print("   🚀  T I T A N   P D F   B O T   S Y S T E M  🚀")
    print("==================================================\n")

    start_bot_safe()


if __name__ == "__main__":
    main()
