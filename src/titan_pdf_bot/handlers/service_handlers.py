from telebot import types
from types import SimpleNamespace
import os
from titan_pdf_bot.core.config import AdvancedConfig
from titan_pdf_bot.core.loader import bot
from titan_pdf_bot.core.database import db
from titan_pdf_bot.core.session import session_manager
from titan_pdf_bot.utils.ui_utils import UIManager
from titan_pdf_bot.utils.file_utils import FileProcessor
from titan_pdf_bot.utils.helpers import get_missing_channels, is_valid_page_range, is_maintenance_mode
from titan_pdf_bot.services.processor import process_file

SINGLE_FILE_MODES = {'pdf_to_img', 'split_pdf', 'encrypt_pdf', 'compress_pdf', 'watermark', 'rotate_pdf', 'file_info'}
MULTI_FILE_MODES = {'img_to_pdf', 'merge_pdf', 'text_to_pdf'}
NEED_OUTPUT_NAME_MODES = {'img_to_pdf', 'merge_pdf', 'text_to_pdf', 'split_pdf'}
SERVICE_TEXTS = tuple(UIManager.SERVICE_LABEL_TO_MODE.keys())


def _get_access_denial_text(user_id):
    if db.is_user_blocked(user_id):
        return "🚫 <b>تم حظرك من استخدام البوت.</b>\nللمزيد من المعلومات، تواصل مع المطور."
    if is_maintenance_mode() and user_id not in AdvancedConfig.ADMINS:
        return "🔧 <b>البوت حالياً في وضع الصيانة.</b>\nنعمل على تحسين الخدمة، نرجو العودة لاحقاً."
    return None


def _ensure_message_access(message):
    denial_text = _get_access_denial_text(message.from_user.id)
    if not denial_text:
        return True
    if hasattr(message, 'message_id'):
        bot.reply_to(message, denial_text, parse_mode='HTML')
    else:
        bot.send_message(message.chat.id, denial_text, parse_mode='HTML')
    return False


def _ensure_call_access(call):
    denial_text = _get_access_denial_text(call.from_user.id)
    if not denial_text:
        return True
    bot.answer_callback_query(call.id, "🚫 غير متاح حالياً", show_alert=True)
    bot.send_message(call.message.chat.id, denial_text, parse_mode='HTML')
    return False


def _check_rate_limit_for_message(message):
    if session_manager.check_rate_limit(message.from_user.id):
        return True
    bot.reply_to(
        message,
        "⏳ <b>عدد الطلبات كبير خلال دقيقة واحدة.</b>\nيرجى الانتظار قليلًا ثم المحاولة مجددًا.",
        parse_mode='HTML'
    )
    return False


def _check_rate_limit_for_call(call):
    if session_manager.check_rate_limit(call.from_user.id):
        return True
    bot.answer_callback_query(call.id, "⏳ مهلة قصيرة ثم أعد المحاولة", show_alert=True)
    return False


def _is_file_entry_valid_for_mode(file_entry, mode):
    file_path = file_entry.get('path')
    if not file_path or not os.path.exists(file_path):
        return False
    try:
        FileProcessor.validate_file(os.path.getsize(file_path), os.path.basename(file_path), mode)
    except ValueError:
        return False
    return True


def _prepare_pending_files(mode, pending_files):
    if not pending_files:
        return []

    candidates = [pending_files[-1]] if mode in SINGLE_FILE_MODES else pending_files
    valid = [item for item in candidates if _is_file_entry_valid_for_mode(item, mode)]

    if mode in MULTI_FILE_MODES and len(valid) > AdvancedConfig.MAX_FILES_PER_USER:
        valid = valid[:AdvancedConfig.MAX_FILES_PER_USER]

    if mode in SINGLE_FILE_MODES:
        return [valid[-1]] if valid else []
    return valid


def _is_ready_for_processing(mode, session):
    if not session:
        return False
    if session.get('step') == 'الاسم' and mode in NEED_OUTPUT_NAME_MODES:
        return False
    if mode in ['img_to_pdf', 'merge_pdf']:
        return bool(session.get('files'))
    if mode == 'text_to_pdf':
        return bool(session.get('text_parts'))
    if mode in ['pdf_to_img', 'compress_pdf', 'file_info']:
        return bool(session.get('files'))
    if mode == 'encrypt_pdf':
        return bool(session.get('files')) and bool(session.get('password'))
    if mode == 'watermark':
        return bool(session.get('files')) and bool(session.get('watermark_text'))
    if mode == 'split_pdf':
        return bool(session.get('files')) and bool(session.get('pages'))
    if mode == 'rotate_pdf':
        return bool(session.get('files')) and bool(session.get('angle'))
    return False


def _prompt_missing_input(chat_id, mode, session):
    if session.get('step') == 'الاسم' and mode in NEED_OUTPUT_NAME_MODES:
        bot.send_message(chat_id, "⚠️ <b>يرجى إرسال اسم الملف النهائي.</b>", parse_mode='HTML')
        return

    if mode in ['img_to_pdf', 'merge_pdf', 'pdf_to_img', 'compress_pdf', 'file_info', 'split_pdf', 'rotate_pdf', 'encrypt_pdf', 'watermark']:
        if not session.get('files'):
            bot.send_message(chat_id, "⚠️ <b>لم تقم بإرسال أي ملف بعد. يرجى إرسال الملفات.</b>", parse_mode='HTML')
            return

    if mode == 'text_to_pdf' and not session.get('text_parts'):
        bot.send_message(chat_id, "⚠️ <b>يرجى إرسال النصوص أو الملفات (لبدء التحويل).</b>", parse_mode='HTML')
        return

    if mode == 'encrypt_pdf' and not session.get('password'):
        bot.send_message(chat_id, "⚠️ <b>يرجى إرسال كلمة المرور المطلوبة.</b>", parse_mode='HTML')
        return

    if mode == 'watermark' and not session.get('watermark_text'):
        bot.send_message(chat_id, "⚠️ <b>يرجى إرسال نص العلامة المائية.</b>", parse_mode='HTML')
        return

    if mode == 'split_pdf' and not session.get('pages'):
        bot.send_message(chat_id, "⚠️ <b>يرجى تحديد نطاق الصفحات (مثال: 1-5).</b>", parse_mode='HTML')
        return

    if mode == 'rotate_pdf' and not session.get('angle'):
        bot.send_message(chat_id, "⚠️ <b>يرجى اختيار زاوية التدوير.</b>", parse_mode='HTML')
        return

@bot.callback_query_handler(func=lambda call: call.data == "retry_service")
def handle_retry_service(call):
    if not _ensure_call_access(call):
        return

    bot.answer_callback_query(call.id, "🔄 جاري إعادة المحاولة...")
    if not _check_rate_limit_for_call(call):
        return

    user_id = call.from_user.id
    session = session_manager.get_session(user_id)

    if not session:
        bot.send_message(
            call.message.chat.id,
            "⚠️ <b>انتهت الجلسة.</b>\nيرجى البدء من جديد من القائمة الرئيسية.",
            parse_mode='HTML'
        )
        return

    mode = session.get('mode')
    if not _is_ready_for_processing(mode, session):
        _prompt_missing_input(call.message.chat.id, mode, session)
        return

    process_file(call.message, session)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_pending")
def handle_cancel_pending(call):
    if not _ensure_call_access(call):
        return

    user_id = call.from_user.id
    session = session_manager.get_session(user_id)
    
    if session:
        session_manager.clear_session(user_id)
    
    bot.answer_callback_query(call.id, "❌ تم إلغاء العملية")
    try:
        bot.edit_message_text(
            "❌ <b>تم إلغاء عملية رفع الملفات.</b>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )
    except Exception:
        pass


@bot.callback_query_handler(func=lambda call: call.data.startswith("service:"))
def handle_inline_service_selection(call):
    if not _ensure_call_access(call):
        return

    mode = call.data.split(":", 1)[1]
    service_text = UIManager.SERVICE_MODE_TO_LABEL.get(mode)
    if not service_text:
        bot.answer_callback_query(call.id, "الخدمة غير متاحة حاليًا", show_alert=True)
        return

    bot.answer_callback_query(call.id, f"تم اختيار: {service_text}")

    synthetic_message = SimpleNamespace(
        text=service_text,
        chat=SimpleNamespace(id=call.message.chat.id),
        from_user=SimpleNamespace(id=call.from_user.id),
        message_id=call.message.message_id,
    )
    handle_menu_selection(synthetic_message)

@bot.message_handler(func=lambda m: m.text in [
    "🖼 صور إلى PDF", "📄 PDF إلى صور", "🔄 دمج PDF", "✂️ تقسيم PDF", 
    "🔐 حماية PDF", "🗜️ ضغط PDF", "📝 نص إلى PDF", "📊 معلومات الملف", 
    "💧 علامة مائية", "🔄 تدوير PDF"
])
def handle_menu_selection(message):
    if not _ensure_message_access(message):
        return

    user_id = message.from_user.id
    missing_channels = get_missing_channels(user_id)
    if missing_channels:
        bot.send_message(message.chat.id, "🔔 <b>للوصول للخدمات، يجب الاشتراك في القنوات التالية:</b>", 
                        reply_markup=UIManager.create_subscription_markup(missing_channels), parse_mode='HTML')
        return

    mode_map = {
        "🖼 صور إلى PDF": "img_to_pdf",
        "📄 PDF إلى صور": "pdf_to_img",
        "🔄 دمج PDF": "merge_pdf",
        "✂️ تقسيم PDF": "split_pdf",
        "🔐 حماية PDF": "encrypt_pdf",
        "🗜️ ضغط PDF": "compress_pdf",
        "📝 نص إلى PDF": "text_to_pdf",
        "📊 معلومات الملف": "file_info",
        "💧 علامة مائية": "watermark",
        "🔄 تدوير PDF": "rotate_pdf"
    }
    
    mode = mode_map[message.text]

    # Check for pending files
    pending_files = []
    old_session = session_manager.get_session(user_id)
    if old_session and old_session.get('mode') == 'pending_selection':
        pending_files = old_session.get('files', [])

    session_manager.create_session(user_id, mode)
    
    # رسائل توجيهية محسنة لكل خدمة
    if mode == 'img_to_pdf':
        bot.send_message(message.chat.id, 
                        "🖼 <b>تحويل الصور إلى PDF</b>\n\n"
                        "• أرسل الصور التي تريد تحويلها إلى PDF\n"
                        "• يمكنك إرسال عدة صور دفعة واحدة\n"
                        "• عند الانتهاء، اضغط 'تم الإدخال'\n\n"
                        "📝 <b>ملاحظة:</b> سيتم ترتيب الصور حسب وقت الإرسال.",
                        reply_markup=UIManager.create_service_menu(), parse_mode='HTML')
    
    elif mode == 'pdf_to_img':
        bot.send_message(message.chat.id,
                        "📄 <b>تحويل PDF إلى صور</b>\n\n"
                        "• أرسل ملف PDF الذي تريد استخراج صور منه\n"
                        "• سأقوم بتحويل كل صفحة إلى صورة منفصلة\n"
                        "• إذا كان الملف يحتوي على أكثر من 30 صفحة، سأرسل ملف ZIP",
                        reply_markup=UIManager.create_service_menu(show_done=False), parse_mode='HTML')
    
    elif mode == 'merge_pdf':
        bot.send_message(message.chat.id,
                        "🔄 <b>دمج ملفات PDF</b>\n\n"
                        "• أرسل ملفات PDF التي تريد دمجها\n"
                        "• يمكنك إرسال عدة ملفات\n"
                        "• عند الانتهاء، اضغط 'تم الإدخال'\n"
                        "• سيتم الدمج حسب ترتيب الإرسال",
                        reply_markup=UIManager.create_service_menu(), parse_mode='HTML')
    
    elif mode == 'split_pdf':
        bot.send_message(message.chat.id,
                        "✂️ <b>تقسيم ملف PDF</b>\n\n"
                        "1. أرسل ملف PDF الذي تريد تقسيمه\n"
                        "2. أرسل نطاق الصفحات المطلوب\n"
                        "   • مثال: 1-5 (من صفحة 1 إلى 5)\n"
                        "   • مثال: 3 (الصفحة 3 فقط)\n\n"
                        "📝 <b>ملاحظة:</b> أرقام الصفحات تبدأ من 1",
                        reply_markup=UIManager.create_service_menu(show_done=False), parse_mode='HTML')
    
    elif mode == 'encrypt_pdf':
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        keyboard.add(types.KeyboardButton("🔐 تنفيذ الحماية"), 
                     types.KeyboardButton("🔄 إعادة إرسال الملف"),
                     types.KeyboardButton("🏠 القائمة الرئيسية"))
        bot.send_message(message.chat.id,
                        "🔐 <b>حماية ملف PDF بكلمة مرور</b>\n\n"
                        "1. أرسل ملف PDF الذي تريد حمايته\n"
                        "2. أرسل كلمة المرور المطلوبة\n"
                        "3. اضغط 'تنفيذ الحماية'\n\n"
                        "🔒 <b>تنبيه:</b> احتفظ بكلمة المرور في مكان آمن",
                        reply_markup=keyboard, parse_mode='HTML')
    
    elif mode == 'watermark':
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        keyboard.add(types.KeyboardButton("💧 تنفيذ العلامة المائية"), 
                     types.KeyboardButton("🔄 إعادة إرسال الملف"),
                     types.KeyboardButton("🏠 القائمة الرئيسية"))
        bot.send_message(message.chat.id,
                        "💧 <b>إضافة علامة مائية إلى PDF</b>\n\n"
                        "1. أرسل ملف PDF\n"
                        "2. أرسل النص الذي تريد إضافته كعلامة مائية\n"
                        "3. اضغط 'تنفيذ العلامة المائية'\n\n"
                        "📝 <b>مثال:</b> 'خاص بـ' أو 'مسودة'",
                        reply_markup=keyboard, parse_mode='HTML')
    
    elif mode == 'text_to_pdf':
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        keyboard.add(types.KeyboardButton("🗑️ حذف الملفات الحالية"),
                     types.KeyboardButton("✅ تم الإدخال"), 
                     types.KeyboardButton("🏠 القائمة الرئيسية"))
        bot.send_message(message.chat.id,
                        "📝 <b>تحويل النص إلى PDF</b>\n\n"
                        "• أرسل النصوص التي تريد تحويلها\n"
                        "• يمكنك إرسال نصوص طويلة\n"
                        "• يمكنك إرسال ملفات نصية (TXT, DOC, DOCX)\n"
                        "• عند الانتهاء، اضغط 'تم الإدخال'\n\n"
                        "✨ <b>ميزة:</b> يدعم اللغة العربية تلقائياً",
                        reply_markup=keyboard, parse_mode='HTML')
    
    elif mode == 'compress_pdf':
        bot.send_message(message.chat.id,
                        "🗜️ <b>ضغط ملف PDF</b>\n\n"
                        "• أرسل ملف PDF الذي تريد ضغطه\n"
                        "• سأقوم بتحسين حجم الملف مع الحفاظ على الجودة\n"
                        "• مثالي للمشاركة عبر الإنترنت",
                        reply_markup=UIManager.create_service_menu(show_done=False), parse_mode='HTML')
    
    elif mode == 'file_info':
        bot.send_message(message.chat.id,
                        "📊 <b>معلومات الملف</b>\n\n"
                        "• أرسل ملف PDF لمعرفة معلوماته التفصيلية\n"
                        "• سأعرض لك:\n"
                        "  - عدد الصفحات\n"
                        "  - الحجم\n"
                        "  - حالة الحماية\n"
                        "  - والمزيد",
                        reply_markup=UIManager.create_service_menu(show_done=False), parse_mode='HTML')
    
    elif mode == 'rotate_pdf':
        bot.send_message(message.chat.id,
                        "🔄 <b>تدوير صفحات PDF</b>\n\n"
                        "1. أرسل ملف PDF الذي تريد تدويره\n"
                        "2. اختر زاوية التدوير\n"
                        "   • 90 درجة: ربع دورة\n"
                        "   • 180 درجة: نصف دورة\n"
                        "   • 270 درجة: ثلاثة أرباع الدورة\n\n"
                        "📝 <b>ملاحظة:</b> سيتم تدوير جميع الصفحات بنفس الزاوية",
                        reply_markup=UIManager.create_service_menu(show_done=False), parse_mode='HTML')

    if pending_files:
        session = session_manager.get_session(user_id)
        compatible_files = _prepare_pending_files(mode, pending_files)

        if mode == 'text_to_pdf':
            extracted_parts = []
            for item in compatible_files:
                try:
                    text_data = FileProcessor.extract_text_from_file(item['path'])
                    if text_data and text_data.strip():
                        extracted_parts.append(text_data)
                except Exception:
                    continue

            session_manager.update_session(user_id, files=[], text_parts=extracted_parts)
            if extracted_parts:
                bot.send_message(
                    message.chat.id,
                    f"✅ <b>تم استخراج النص من {len(extracted_parts)} ملف/ملفات معلّقة.</b>\n"
                    "أرسل المزيد أو اضغط '✅ تم الإدخال'.",
                    parse_mode='HTML'
                )
            else:
                bot.send_message(
                    message.chat.id,
                    "⚠️ <b>لا توجد ملفات معلّقة صالحة لخدمة (نص إلى PDF).</b>\n"
                    "أرسل نصًا مباشرًا أو ملفات TXT/DOC/DOCX.",
                    parse_mode='HTML'
                )
            return

        if not compatible_files:
            bot.send_message(
                message.chat.id,
                "⚠️ <b>الملفات المعلّقة غير متوافقة مع هذه الخدمة.</b>\nيرجى إرسال ملف/ملفات مناسبة.",
                parse_mode='HTML'
            )
            return

        if mode in MULTI_FILE_MODES and len(compatible_files) == AdvancedConfig.MAX_FILES_PER_USER and len(pending_files) > AdvancedConfig.MAX_FILES_PER_USER:
            bot.send_message(
                message.chat.id,
                f"⚠️ <b>تم اعتماد أول {AdvancedConfig.MAX_FILES_PER_USER} ملفات فقط.</b>",
                parse_mode='HTML'
            )

        session_manager.update_session(user_id, files=compatible_files)
        session = session_manager.get_session(user_id)

        if mode == 'img_to_pdf':
            bot.send_message(message.chat.id, f"✅ <b>تم نقل {len(session['files'])} صور.</b>\nأرسل المزيد أو اضغط 'تم الإدخال'.", parse_mode='HTML')
        elif mode == 'merge_pdf':
            bot.send_message(message.chat.id, f"✅ <b>تم نقل {len(session['files'])} ملفات.</b>\nأرسل المزيد أو اضغط 'تم الإدخال'.", parse_mode='HTML')
        elif mode in ['pdf_to_img', 'compress_pdf', 'file_info']:
            if not _check_rate_limit_for_message(message):
                return
            process_file(message, session)
        elif mode == 'split_pdf':
            bot.send_message(message.chat.id, "✅ <b>تم استلام الملف.</b>\nأرسل نطاق الصفحات (مثال: 1-5).", parse_mode='HTML')
        elif mode in ['encrypt_pdf', 'watermark']:
            bot.send_message(message.chat.id, "✅ <b>تم استلام الملف.</b>\nأرسل كلمة المرور/النص المطلوب.", parse_mode='HTML')
        elif mode == 'rotate_pdf':
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
            keyboard.add("90°", "180°", "270°")
            keyboard.add("🗑️ حذف الملفات الحالية", "🏠 القائمة الرئيسية")
            bot.send_message(message.chat.id, "✅ <b>تم استلام الملف.</b>\nاختر زاوية التدوير:", reply_markup=keyboard, parse_mode='HTML')

@bot.message_handler(content_types=['document', 'photo'])
def handle_file_upload(message):
    user_id = message.from_user.id

    if not _ensure_message_access(message):
        return

    session = session_manager.get_session(user_id)

    # Ignore if user is broadcasting
    if session and session.get('mode') == 'broadcasting':
        return

    if not _check_rate_limit_for_message(message):
        return

    if not session:
        session_manager.create_session(user_id, 'pending_selection')
        session = session_manager.get_session(user_id)

    mode = session.get('mode')
    if mode in SINGLE_FILE_MODES and session.get('files'):
        bot.reply_to(
            message,
            "⚠️ <b>لقد أرسلت ملفاً بالفعل لهذا الغرض. أرسل (إلغاء وعودة) للإلغاء.</b>",
            parse_mode='HTML'
        )
        return

    if (mode in MULTI_FILE_MODES or mode == 'pending_selection') and len(session.get('files', [])) >= AdvancedConfig.MAX_FILES_PER_USER:
        bot.reply_to(
            message,
            f"⚠️ <b>تجاوزت الحد الأقصى للملفات ({AdvancedConfig.MAX_FILES_PER_USER}).</b>",
            parse_mode='HTML'
        )
        return

    try:
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            file_size = message.photo[-1].file_size
            file_name = FileProcessor.sanitize_filename(f"صورة_{message.message_id}.jpg")
        else:
            file_id = message.document.file_id
            file_size = message.document.file_size
            file_name = FileProcessor.sanitize_filename(message.document.file_name or "ملف.pdf")

        try:
            FileProcessor.validate_file(file_size, file_name, mode)
        except ValueError as e:
            bot.reply_to(message, f"❌ <b>خطأ:</b>\n{str(e)}", parse_mode='HTML')
            return

        file_info = bot.get_file(file_id)
        file_content = bot.download_file(file_info.file_path)

        file_path = FileProcessor.save_file(user_id, file_content, file_name)

        if mode == 'text_to_pdf' and file_name.lower().endswith(('.txt', '.doc', '.docx')):
            try:
                text_data = FileProcessor.extract_text_from_file(file_path)
                if text_data:
                    if 'text_parts' not in session:
                        session['text_parts'] = []
                    session['text_parts'].append(text_data)
                    bot.reply_to(
                        message,
                        "✅ <b>تم استخراج النص من الملف.</b>\nأرسل المزيد أو اضغط على '✅ تم الإدخال'.",
                        parse_mode='HTML'
                    )
                    session_manager.update_session(user_id, text_parts=session['text_parts'])
                    return
                raise Exception("لم يتم العثور على نص في الملف")
            except Exception as e:
                bot.reply_to(message, f"❌ <b>فشل في قراءة الملف:</b>\n{str(e)}", parse_mode='HTML')
                return

        session['files'].append({'path': file_path, 'id': message.message_id})
        session_manager.update_session(user_id, files=session['files'])

        if mode == 'pending_selection':
            bot.reply_to(
                message,
                f"📂 <b>تم استلام الملف (العدد: {len(session['files'])}).</b>\nالرجاء اختيار الخدمة أو إرسال المزيد.",
                parse_mode='HTML',
                reply_markup=UIManager.create_pending_service_menu(user_id)
            )

        elif mode == 'img_to_pdf':
            bot.reply_to(
                message,
                f"✅ <b>تم استلام {len(session['files'])} صور.</b>\nعند الانتهاء اضغط '✅ تم الإدخال'.",
                parse_mode='HTML'
            )

        elif mode in ['merge_pdf', 'text_to_pdf']:
            bot.reply_to(
                message,
                "✅ <b>تم الاستلام.</b>\nأرسل المزيد أو اضغط على '✅ تم الإدخال'.",
                parse_mode='HTML'
            )

        elif mode in ['encrypt_pdf', 'watermark']:
            bot.reply_to(
                message,
                "✅ <b>تم استلام الملف.</b>\nأرسل كلمة المرور/النص المطلوب.",
                parse_mode='HTML'
            )

        elif mode == 'split_pdf':
            bot.reply_to(
                message,
                "✅ <b>تم استلام الملف.</b>\nأرسل نطاق الصفحات (مثال: 1-5).",
                parse_mode='HTML'
            )

        elif mode == 'rotate_pdf':
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
            keyboard.add("90°", "180°", "270°")
            keyboard.add("🗑️ حذف الملفات الحالية", "🏠 القائمة الرئيسية")
            bot.reply_to(
                message,
                "✅ <b>تم استلام الملف.</b>\nاختر زاوية التدوير:",
                reply_markup=keyboard, parse_mode='HTML'
            )

        elif mode in ['pdf_to_img', 'compress_pdf', 'file_info']:
            process_file(message, session)

    except Exception as e:
        bot.reply_to(
            message,
            f"❌ <b>حدث خطأ غير متوقع:</b>\n{str(e)}",
            reply_markup=UIManager.create_error_buttons(),
            parse_mode='HTML'
        )

@bot.message_handler(content_types=['text'])
def handle_text_input(message):
    user_id = message.from_user.id

    if not _ensure_message_access(message):
        return

    session = session_manager.get_session(user_id)
    text = message.text.strip()

    if session and session['mode'] == 'pdf_to_img':
        bot.reply_to(
            message,
            "⚠️ <b>هذه الخدمة تقبل ملف PDF فقط.</b>\nالرجاء إرسال ملف PDF وليس رسالة نصية.",
            parse_mode='HTML'
        )
        return

    if not session:
        if text == "📊 الإحصائيات":
            stats = db.get_user_stats(user_id)
            stats_text = f'''\
📊 <b>إحصائياتك الشخصية</b>\n\n📌 <b>عدد العمليات:</b> {stats[0]}\n💾 <b>إجمالي حجم الملفات:</b> {stats[1] / (1024*1024):.2f} ميجابايت\n📅 <b>تاريخ التسجيل:</b> {stats[2]}\n👑 <b>الحالة:</b> {"مشترك 🌟" if stats[3] else "مجاني 👤"}\n'''
            bot.send_message(message.chat.id, stats_text, parse_mode='HTML')
        return

    if text == "🗑️ حذف الملفات الحالية":
        cleared = False
        if session.get('files'):
            session['files'] = []
            cleared = True
        if session.get('text_parts'):
            session['text_parts'] = []
            cleared = True

        if cleared:
            bot.reply_to(message, "🗑️ <b>تم حذف المدخلات الحالية.</b>\nيمكنك البدء من جديد.", parse_mode='HTML')
        else:
            bot.reply_to(message, "⚠️ <b>لا توجد مدخلات لحذفها.</b>", parse_mode='HTML')

        session_manager.update_session(user_id, files=session.get('files', []), text_parts=session.get('text_parts', []))
        return

    if text == "🔄 إعادة إرسال الملف":
        session['files'] = []
        bot.reply_to(message, "🔄 <b>يمكنك الآن إرسال الملف الجديد.</b>", parse_mode='HTML')
        session_manager.update_session(user_id, files=[])
        return

    mode = session['mode']

    if text == "🔐 تنفيذ الحماية" and mode == 'encrypt_pdf':
        if not session.get('password'):
            bot.reply_to(message, "⚠️ <b>لم تحدد كلمة المرور بعد!</b>\nأرسل كلمة المرور أولاً.", parse_mode='HTML')
            return
        if not _check_rate_limit_for_message(message):
            return
        process_file(message, session)
        return

    if text == "💧 تنفيذ العلامة المائية" and mode == 'watermark':
        if not session.get('watermark_text'):
            bot.reply_to(message, "⚠️ <b>لم تحدد نص العلامة المائية بعد!</b>\nأرسل النص أولاً.", parse_mode='HTML')
            return
        if not _check_rate_limit_for_message(message):
            return
        process_file(message, session)
        return

    if text in ["✅ تم الإدخال", "تم"]:
        if mode in ['img_to_pdf', 'merge_pdf']:
            if not session.get('files'):
                bot.reply_to(
                    message,
                    "⚠️ <b>لم ترسل ملفات بعد.</b>\nيرجى إرسال الملفات أولاً.",
                    reply_markup=UIManager.create_error_buttons(),
                    parse_mode='HTML'
                )
                return
            session['step'] = 'الاسم'
            bot.send_message(
                message.chat.id,
                "📝 <b>يرجى كتابة اسم الملف النهائي:</b>\n\n📌 <b>مثال:</b> تقرير_العمل .pdf (اختياري)",
                parse_mode='HTML'
            )
            return

        if mode == 'text_to_pdf':
            if not session.get('text_parts'):
                bot.reply_to(
                    message,
                    "⚠️ <b>لم ترسل نصاً بعد.</b>\nيرجى إرسال نص أو ملف TXT/DOC/DOCX أولاً.",
                    reply_markup=UIManager.create_error_buttons(),
                    parse_mode='HTML'
                )
                return
            session['step'] = 'الاسم'
            bot.send_message(
                message.chat.id,
                "📝 <b>يرجى كتابة اسم الملف النهائي:</b>\n\n📌 <b>مثال:</b> تقرير_العمل .pdf (اختياري)",
                parse_mode='HTML'
            )
            return

    if session.get('step') == 'الاسم':
        session['output_name'] = FileProcessor.sanitize_filename(text, default_name="مستند_جديد")
        if not _check_rate_limit_for_message(message):
            return
        process_file(message, session)
        return

    if mode == 'text_to_pdf':
        if 'text_parts' not in session:
            session['text_parts'] = []
        session['text_parts'].append(text)
        bot.reply_to(
            message,
            "✅ <b>تم الحفظ.</b>\nأرسل المزيد أو اضغط على '✅ تم الإدخال'.",
            parse_mode='HTML'
        )
        session_manager.update_session(user_id, text_parts=session['text_parts'])
        return

    if mode == 'encrypt_pdf':
        session['password'] = text
        bot.reply_to(
            message,
            "✅ <b>تم حفظ كلمة المرور.</b>\nاضغط 'تنفيذ الحماية' للبدء.",
            parse_mode='HTML'
        )
        session_manager.update_session(user_id, password=text)
        return

    if mode == 'watermark':
        session['watermark_text'] = text
        bot.reply_to(
            message,
            "✅ <b>تم حفظ نص العلامة المائية.</b>\nاضغط 'تنفيذ العلامة المائية' للبدء.",
            parse_mode='HTML'
        )
        session_manager.update_session(user_id, watermark_text=text)
        return

    if mode == 'split_pdf':
        if not is_valid_page_range(text):
            bot.reply_to(message, "⚠️ <b>صيغة نطاق الصفحات غير صحيحة. مثال: 1-5</b>", parse_mode='HTML')
            return
        session['pages'] = text
        session['step'] = 'الاسم'
        bot.send_message(message.chat.id, "📝 <b>يرجى كتابة اسم الملف النهائي:</b>", parse_mode='HTML')
        session_manager.update_session(user_id, pages=text, step='الاسم')
        return

    if mode == 'rotate_pdf':
        if text in ['90°', '180°', '270°']:
            session['angle'] = int(text.replace('°', ''))
            if not _check_rate_limit_for_message(message):
                return
            process_file(message, session)
        else:
            bot.reply_to(message, "⚠️ <b>زاوية غير صالحة!</b>\nاختر من: 90°، 180°، 270°", parse_mode='HTML')

