from telebot import TeleBot, apihelper
import requests
from titan_pdf_bot.core.config import AdvancedConfig


# Config TeleBot
session = requests.Session()
session.verify = True
apihelper.SESSION = session
apihelper.READ_TIMEOUT = AdvancedConfig.REQUEST_TIMEOUT
apihelper.CONNECT_TIMEOUT = AdvancedConfig.REQUEST_TIMEOUT

bot = TeleBot(
    AdvancedConfig.API_TOKEN,
    num_threads=AdvancedConfig.THREAD_POOL_SIZE,
    parse_mode='HTML',
    skip_pending=True
)
