from urllib.parse import quote_plus

from telebot import types

from titan_pdf_bot.core.config import AdvancedConfig
from titan_pdf_bot.core.loader import bot


DEVELOPER_URL = "https://t.me/abulharith_imad"


class UIManager:
    SERVICE_ITEMS = [
        ("🖼 صور إلى PDF", "img_to_pdf"),
        ("📄 PDF إلى صور", "pdf_to_img"),
        ("🔄 دمج PDF", "merge_pdf"),
        ("✂️ تقسيم PDF", "split_pdf"),
        ("🗜️ ضغط PDF", "compress_pdf"),
        ("📝 نص إلى PDF", "text_to_pdf"),
        ("🔐 حماية PDF", "encrypt_pdf"),
        ("📊 معلومات الملف", "file_info"),
        ("💧 علامة مائية", "watermark"),
        ("🔄 تدوير PDF", "rotate_pdf"),
    ]
    SERVICE_LABEL_TO_MODE = {label: mode for label, mode in SERVICE_ITEMS}
    SERVICE_MODE_TO_LABEL = {mode: label for label, mode in SERVICE_ITEMS}

    @staticmethod
    def create_main_menu(user_id):
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        service_buttons = [
            types.InlineKeyboardButton(label, callback_data=f"service:{mode}")
            for label, mode in UIManager.SERVICE_ITEMS
        ]

        for index in range(0, len(service_buttons), 2):
            keyboard.row(*service_buttons[index:index + 2])

        keyboard.row(
            types.InlineKeyboardButton("❓ المساعدة", callback_data="show_help"),
            types.InlineKeyboardButton("📞 المطور", url=DEVELOPER_URL),
        )

        if user_id in AdvancedConfig.ADMINS:
            keyboard.row(types.InlineKeyboardButton("⚙️ إعدادات المدير", callback_data="admin_settings"))

        return keyboard

    @staticmethod
    def create_pending_service_menu(user_id):
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        service_buttons = [
            types.InlineKeyboardButton(label, callback_data=f"service:{mode}")
            for label, mode in UIManager.SERVICE_ITEMS
        ]

        for index in range(0, len(service_buttons), 2):
            keyboard.row(*service_buttons[index:index + 2])

        keyboard.row(types.InlineKeyboardButton("❌ إلغاء العملية", callback_data="cancel_pending"))
        return keyboard

    @staticmethod
    def create_service_menu(show_done=True):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        buttons = [types.KeyboardButton("🗑️ حذف الملفات الحالية")]
        if show_done:
            buttons.append(types.KeyboardButton("✅ تم الإدخال"))
        buttons.append(types.KeyboardButton("🏠 القائمة الرئيسية"))
        keyboard.add(*buttons)
        return keyboard

    @staticmethod
    def create_settings_menu(user_id):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        keyboard.add(types.KeyboardButton("📞 مراسلة المطور"), types.KeyboardButton("📊 الإحصائيات"))
        keyboard.add(types.KeyboardButton("🏠 القائمة الرئيسية"))
        return keyboard

    @staticmethod
    def create_admin_settings_menu():
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        keyboard.add(types.KeyboardButton("📊 إحصائيات النظام"), types.KeyboardButton("🚫 إدارة الحظر"))
        keyboard.add(types.KeyboardButton("📢 الإذاعة للمستخدمين"), types.KeyboardButton("🔄 إعادة تشغيل البوت"))
        keyboard.add(types.KeyboardButton("📦 تحديث المكتبات"), types.KeyboardButton("💾 نسخ قاعدة البيانات"))
        keyboard.add(types.KeyboardButton("🔧 وضع الصيانة"), types.KeyboardButton("🏠 القائمة الرئيسية"))
        return keyboard

    @staticmethod
    def create_cancel_only_keyboard():
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        keyboard.add(types.KeyboardButton("🔙 إلغاء وعودة"))
        return keyboard

    @staticmethod
    def create_cancel_inline_keyboard():
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("❌ إلغاء العملية", callback_data="cancel_pending"))
        return keyboard

    @staticmethod
    def create_progress_message(chat_id, text, progress_percent=0):
        progress_percent = max(0, min(100, int(progress_percent)))
        progress_bar = "▓" * int(progress_percent / 10) + "░" * (10 - int(progress_percent / 10))
        return bot.send_message(chat_id, f"⏳ <b>{text}</b>\n\n{progress_bar} {progress_percent}%", parse_mode="HTML")

    @staticmethod
    def update_progress_message(message_id, chat_id, text, progress_percent):
        try:
            progress_percent = max(0, min(100, int(progress_percent)))
            progress_bar = "▓" * int(progress_percent / 10) + "░" * (10 - int(progress_percent / 10))
            bot.edit_message_text(
                f"⏳ <b>{text}</b>\n\n{progress_bar} {progress_percent}%",
                chat_id, message_id, parse_mode="HTML"
            )
            return True
        except Exception:
            return False

    @staticmethod
    def clear_reply_keyboard(chat_id):
        try:
            cleanup_message = bot.send_message(chat_id, "\u2060", reply_markup=types.ReplyKeyboardRemove())
            bot.delete_message(chat_id, cleanup_message.message_id)
        except Exception:
            pass

    @staticmethod
    def create_completion_buttons():
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        share_text = "استخدم هذا البوت لأدوات PDF الاحترافية: @TitanPDFBot"
        share_url = f"https://t.me/share/url?url=https://t.me/TitanPDFBot&text={quote_plus(share_text)}"
        keyboard.row(
            types.InlineKeyboardButton("📤 مشاركة البوت", url=share_url),
            types.InlineKeyboardButton("👨‍💻 مراسلة المطور", url=DEVELOPER_URL)
        )
        keyboard.row(types.InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"))
        return keyboard

    @staticmethod
    def create_error_buttons():
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("🔄 إعادة المحاولة", callback_data="retry_service"),
            types.InlineKeyboardButton("❓ كيفية الاستخدام", callback_data="show_help")
        )
        keyboard.add(
            types.InlineKeyboardButton("👨‍💻 مراسلة المطور", url=DEVELOPER_URL),
            types.InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")
        )
        return keyboard

    @staticmethod
    def create_subscription_markup(missing_channels):
        markup = types.InlineKeyboardMarkup(row_width=1)
        for channel in missing_channels:
            markup.add(types.InlineKeyboardButton(f"اشترك في {channel}", url=f"https://t.me/{channel.replace('@', '')}"))
        markup.add(types.InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription"))
        return markup

    @staticmethod
    def create_broadcast_markup():
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("👨‍💻 مراسلة المطور", url=DEVELOPER_URL),
            types.InlineKeyboardButton("❓ المساعدة", callback_data="show_help")
        )
        markup.add(types.InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"))
        return markup
    @staticmethod
    def create_bots_list_keyboard():
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.row(
            types.InlineKeyboardButton("📞 مراسلة المطور", url=DEVELOPER_URL),
            types.InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")
        )
        return keyboard
