from telebot import types

from titan_pdf_bot.core.config import AdvancedConfig
from titan_pdf_bot.core.database import db
from titan_pdf_bot.core.loader import bot
from titan_pdf_bot.core.session import session_manager
from titan_pdf_bot.utils.helpers import get_missing_channels, is_maintenance_mode
from titan_pdf_bot.utils.ui_utils import DEVELOPER_URL, UIManager


def _clear_reply_keyboard(chat_id):
    try:
        cleanup_message = bot.send_message(chat_id, "\u2060", reply_markup=types.ReplyKeyboardRemove())
        bot.delete_message(chat_id, cleanup_message.message_id)
    except Exception:
        pass


def _send_main_menu(chat_id, user_id, title="🏠 <b>الواجهة الرئيسية</b>"):
    _clear_reply_keyboard(chat_id)
    bot.send_message(
        chat_id,
        f"{title}\nاختر الخدمة التي تريدها من الأزرار المدمجة أدناه:",
        reply_markup=UIManager.create_main_menu(user_id),
        parse_mode='HTML'
    )


def _send_welcome(chat_id, user_id):
    _clear_reply_keyboard(chat_id)
    welcome = (
        "🌟 <b>مرحبًا بك في Titan PDF Pro</b>\n\n"
        "أداة احترافية لمعالجة ملفات PDF والصور والنصوص بسرعة ودقة.\n"
        "اختر الخدمة المناسبة من الأزرار المدمجة أدناه، ثم أرسل الملف أو النص وسأكمل معك الخطوات المطلوبة."
    )
    bot.send_message(chat_id, welcome, reply_markup=UIManager.create_main_menu(user_id), parse_mode='HTML')


@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    if db.is_user_blocked(user_id):
        bot.reply_to(message, "🚫 <b>تم حظرك من استخدام البوت.</b>\nللمزيد من المعلومات، تواصل مع المطور.", parse_mode='HTML')
        return
    if is_maintenance_mode() and user_id not in AdvancedConfig.ADMINS:
        bot.reply_to(message, "🔧 <b>البوت حاليًا في وضع الصيانة.</b>\nنعمل على تحسين الخدمة، نرجو العودة لاحقًا.", parse_mode='HTML')
        return
    db.register_user(message.from_user)
    _send_welcome(message.chat.id, user_id)


@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def handle_check_subscription(call):
    missing = get_missing_channels(call.from_user.id)
    if missing:
        bot.answer_callback_query(call.id, "❌ لم تشترك في جميع القنوات المطلوبة!", show_alert=True)
        bot.send_message(
            call.message.chat.id,
            "⚠️ <b>يجب الاشتراك في القنوات التالية:</b>",
            reply_markup=UIManager.create_subscription_markup(missing),
            parse_mode='HTML'
        )
    else:
        bot.answer_callback_query(call.id, "✅ شكرًا لاشتراكك! يمكنك الآن استخدام البوت.")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        db.register_user(call.from_user)
        _send_welcome(call.message.chat.id, call.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def handle_main_menu_callback(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    session_manager.clear_session(user_id)
    _send_main_menu(call.message.chat.id, user_id)


@bot.callback_query_handler(func=lambda call: call.data == "main_menu_broadcast")
def handle_broadcast_menu_click(call):
    handle_main_menu_callback(call)


@bot.message_handler(commands=['help'])
@bot.message_handler(func=lambda m: m.text == "❓ المساعدة")
def handle_help(message):
    max_download_mb = AdvancedConfig.MAX_DOWNLOAD_SIZE // (1024 * 1024)
    max_upload_mb = AdvancedConfig.MAX_UPLOAD_SIZE // (1024 * 1024)
    help_text = f"""
<b>📚 دليل المساعدة - Titan PDF Pro</b>

<b>🔹 الخدمات المتاحة:</b>

1️⃣ <b>🖼 صور إلى PDF:</b> يجمع عدة صور في ملف PDF واحد مرتب
2️⃣ <b>📄 PDF إلى صور:</b> يستخرج جميع صفحات ملف PDF كصور منفصلة
3️⃣ <b>🔄 دمج PDF:</b> يدمج عدة ملفات PDF في ملف واحد
4️⃣ <b>✂️ تقسيم PDF:</b> استخراج صفحات معينة من ملف PDF (مثال: 1-5)
5️⃣ <b>🔐 حماية PDF:</b> حماية ملف PDF بكلمة مرور
6️⃣ <b>🗜️ ضغط PDF:</b> تقليل حجم الملف للمشاركة السهلة
7️⃣ <b>📝 نص إلى PDF:</b> تحويل النصوص الطويلة إلى ملف PDF منسق
   - يدعم النص المكتوب مباشرة
   - يدعم ملفات TXT, DOC, DOCX
8️⃣ <b>💧 علامة مائية:</b> إضافة نص شفاف كعلامة مائية
9️⃣ <b>🔄 تدوير PDF:</b> تدوير صفحات PDF بزوايا مختلفة

<b>🔹 كيفية الاستخدام:</b>
1. اختر الخدمة المطلوبة
2. أرسل الملفات أو النصوص المطلوبة
3. اتبع التعليمات الظاهرة
4. استلم الملف الناتج

<b>🔹 ملاحظات مهمة:</b>
• الحد الأقصى لحجم الملف المرسل للبوت: {max_download_mb} ميجابايت
• الحد الأقصى لحجم الملف الناتج القابل للإرسال: {max_upload_mb} ميجابايت
• الملفات المؤقتة تُحذف تلقائيًا بعد 24 ساعة
• للاستفسارات، تواصل مع المطور
"""
    inline_markup = types.InlineKeyboardMarkup()
    inline_markup.add(types.InlineKeyboardButton("📞 راسل المطور", url=DEVELOPER_URL), types.InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"))

    bot.send_message(message.chat.id, help_text, reply_markup=inline_markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data == "show_help")
def show_help_callback(call):
    bot.answer_callback_query(call.id)
    handle_help(call.message)


@bot.message_handler(commands=['bots'])
def handle_bots_list(message):
    bots_text = """هذه قائمة البوتات الخاصة بنا:

1- 🤖 إدارة الفتاوى | Fatwa CMS:
مشروع خيري يهدف لأرشفة ونشر فتاوى العلماء الثقات، وتسهيل الوصول إليها عبر التليجرام.

🎯 ماذا يمكنه أن يفعل لك؟
• محرك بحث سريع ودقيق.
• تصنيف موضوعي شامل.
• دعم الوسائط المتعددة (نص، صوت، روابط).
• إمكانية النشر التلقائي للقنوات والمجموعات.

🔥 جربه الآن: @Fatwa_CMS_Bot

2- 🤖 العملاق للمستندات | Titan Pdf Pro :

🎯 ماذا يمكنه أن يفعل لك؟

بوت متخصص في معالجة ملفات PDF والصور والنصوص، يقوم بالعديد من المهام:
• تحويل الصور إلى PDF والعكس
• دمج وتقسيم ملفات PDF
• حماية وضغط الملفات
• إضافة علامات مائية والمزيد

🔥 جربه الآن: @TitanPdfBot

3- 🤖 العملاق للتحميل | Titan Downloader :

🎯 ماذا يمكنه أن يفعل لك؟

يتيح لك تحميل فيديوهاتك المفضلة بأعلى جودة ممكنة، بالإضافة إلى استخراج الصوت منها بكل سهولة وسرعة، حيث يُعتبر سريعًا ومجانيًا وسهل الاستخدام ✅️. يمكنه تحميل الفيديوهات القصيرة من منصات مثل يوتيوب، تيك توك، فيسبوك، وإنستجرام.

⛔️ تنبيه: لا تستخدم البوت فيما يغضب الله عز وجل كتحميل الموسيقى والصور المحرمة!

🔥 جربه الآن: @TitanSvBot

4- 🤖 بوت فذكر الدعوي:

بوت "فَذَكِّر" رفيقك اليومي للتذكير بالصلوات، الأذكار، والسنن، ونشر الفوائد والفيديوهات الدعوية، أضفه لقناتك أو مجموعتك لنشر الخير.

🔥 جربه الآن:  @Fadhakir_bot"""
    
    bot.send_message(
        message.chat.id,
        bots_text,
        reply_markup=UIManager.create_bots_list_keyboard(),
        parse_mode='HTML'
    )


@bot.message_handler(func=lambda m: m.text == "🏠 القائمة الرئيسية")
def handle_main_menu(message):
    user_id = message.from_user.id
    session_manager.clear_session(user_id)
    _send_main_menu(message.chat.id, user_id)


@bot.message_handler(commands=['contact'])
@bot.message_handler(func=lambda m: m.text == "📞 تواصل مع المطور")
def handle_contact_developer(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📞 تواصل مع المطور مباشرة", url=DEVELOPER_URL))
    bot.send_message(
        message.chat.id,
        "📞 <b>للتواصل مع المطور:</b>\n\nانقر على الزر أدناه للتواصل مباشرة.",
        parse_mode='HTML',
        reply_markup=markup
    )


@bot.message_handler(func=lambda m: m.text == "🔙 إلغاء وعودة")
def handle_cancel(message):
    user_id = message.from_user.id
    session = session_manager.get_session(user_id)

    if session:
        session_manager.clear_session(user_id)

    _send_main_menu(message.chat.id, user_id)
