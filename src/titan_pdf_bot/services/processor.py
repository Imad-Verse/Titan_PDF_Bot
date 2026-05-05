import os
import time
import threading
from pypdf import PdfReader
from titan_pdf_bot.core.config import AdvancedConfig
from titan_pdf_bot.core.loader import bot
from titan_pdf_bot.utils.ui_utils import UIManager
from titan_pdf_bot.core.database import db
from titan_pdf_bot.core.session import session_manager
from titan_pdf_bot.utils.file_utils import FileProcessor
from titan_pdf_bot.services.image_ops import process_images_to_pdf, process_pdf_to_images
from titan_pdf_bot.services.pdf_ops import (
    process_text_to_pdf, process_file_info, process_encrypt_pdf,
    process_watermark, process_merge_pdf, process_compress_pdf,
    process_split_pdf, process_rotate_pdf
)

# منظم العمليات الثقيلة (يمنع استهلاك المعالج بالكامل)
heavy_process_semaphore = threading.Semaphore(AdvancedConfig.MAX_CONCURRENT_TASKS)


def process_file(message, session):
    user_id = message.from_user.id
    mode = session['mode']
    progress = None
    
    # رسالة تنبيه إذا كان النظام مشغولاً
    waiting_msg = None
    if heavy_process_semaphore._value == 0:
        waiting_msg = bot.send_message(
            message.chat.id, 
            "⏳ <b>النظام مشغول بمعالجة طلبات أخرى حالياً...</b>\nتم وضع طلبك في الطابور وسيبدأ التنفيذ تلقائياً.",
            parse_mode='HTML'
        )

    with heavy_process_semaphore:
        try:
            if waiting_msg:
                try: bot.delete_message(message.chat.id, waiting_msg.message_id)
                except: pass

            progress = UIManager.create_progress_message(message.chat.id, "جارٍ المعالجة...", 10)
            start_time = time.time()
            result_path = None
            fallback_name = f"مستند_{int(time.time())}"
            custom_name = FileProcessor.sanitize_filename(
                session.get('output_name') or fallback_name,
                default_name=fallback_name
            )

            if progress:
                UIManager.update_progress_message(progress.message_id, message.chat.id, "جارٍ المعالجة...", 30)

            if mode == 'img_to_pdf':
                if not session['files']:
                    raise ValueError("لم يتم العثور على ملفات")
                sorted_files = sorted(session['files'], key=lambda x: x['id'])
                paths = [f['path'] for f in sorted_files]
                result_path = process_images_to_pdf(paths, custom_name, user_id)
                op_info = "تحويل صور إلى PDF"

            elif mode == 'text_to_pdf':
                if not session.get('text_parts'):
                    raise ValueError("لم يتم العثور على نص")
                full_text = "\n\n".join(session['text_parts'])
                result_path = process_text_to_pdf(full_text, custom_name, user_id)
                op_info = "تحويل نص إلى PDF"

            elif mode == 'file_info':
                if not session['files']:
                    raise ValueError("لم يتم العثور على ملف")
                info_text = process_file_info(session['files'][0]['path'])
                try:
                    if progress:
                        bot.delete_message(message.chat.id, progress.message_id)
                except Exception:
                    pass
                UIManager.clear_reply_keyboard(message.chat.id)
                bot.send_message(
                    message.chat.id, info_text, parse_mode='HTML',
                    reply_markup=UIManager.create_completion_buttons()
                )
                session_manager.clear_session(user_id)
                return

            elif mode == 'encrypt_pdf':
                if not session['files']:
                    raise ValueError("لم يتم العثور على ملف")
                if not session.get('password'):
                    raise ValueError("لم يتم تحديد كلمة المرور")
                result_path = process_encrypt_pdf(session['files'][0]['path'], session['password'], user_id)
                op_info = "حماية PDF"

            elif mode == 'watermark':
                if not session['files']:
                    raise ValueError("لم يتم العثور على ملف")
                if not session.get('watermark_text'):
                    raise ValueError("لم يتم تحديد نص العلامة المائية")
                result_path = process_watermark(session['files'][0]['path'], session['watermark_text'], user_id)
                op_info = "إضافة علامة مائية"

            elif mode == 'merge_pdf':
                if not session['files']:
                    raise ValueError("لم يتم العثور على ملفات")
                paths = [f['path'] for f in session['files']]
                result_path = process_merge_pdf(paths, custom_name, user_id)
                op_info = "دمج PDF"

            elif mode == 'compress_pdf':
                if not session['files']:
                    raise ValueError("لم يتم العثور على ملف")
                result_path = process_compress_pdf(session['files'][0]['path'], user_id)
                op_info = "ضغط PDF"

            elif mode == 'split_pdf':
                if not session['files']:
                    raise ValueError("لم يتم العثور على ملف")
                if not session.get('pages'):
                    raise ValueError("لم يتم تحديد الصفحات")
                result_path = process_split_pdf(session['files'][0]['path'], session['pages'], custom_name, user_id)
                op_info = "تقسيم PDF"

            elif mode == 'pdf_to_img':
                if not session['files']:
                    raise ValueError("لم يتم العثور على ملف")
                process_pdf_to_images(session['files'][0]['path'], user_id, progress, message)
                return

            elif mode == 'rotate_pdf':
                if not session['files']:
                    raise ValueError("لم يتم العثور على ملف")
                angle = session.get('angle', 90)
                result_path = process_rotate_pdf(session['files'][0]['path'], angle, user_id)
                op_info = f"تدوير PDF ({angle}°)"

            if progress:
                UIManager.update_progress_message(progress.message_id, message.chat.id, "جارٍ المعالجة...", 90)

            if result_path and os.path.exists(result_path):
                try:
                    if progress:
                        bot.delete_message(message.chat.id, progress.message_id)
                except Exception:
                    pass

                pages_count = "غير معروف"
                try:
                    reader = PdfReader(result_path)
                    pages_count = len(reader.pages)
                except Exception:
                    pass

                processing_time = time.time() - start_time
                file_size_bytes = os.path.getsize(result_path)
                file_size_mb = file_size_bytes / (1024 * 1024)

                if file_size_bytes > AdvancedConfig.MAX_UPLOAD_SIZE:
                     bot.send_message(
                         message.chat.id,
                         f"⚠️ <b>عذراً، لا يمكنني إرسال هذا الملف!</b>\n\n"
                         f"الملف الناتج حجمه ({file_size_mb:.2f} ميجابايت)، وهو يتجاوز الحد الأقصى الذي يسمح به تيليجرام للبوتات وهو (50 ميجابايت).\n\n"
                         "💡 <b>بإمكانك تجربة الآتي لتقليل الحجم:</b>\n"
                         "• تقليل عدد الصور المدمجة.\n"
                         "• استخدام خدمة 'ضغط PDF' على الملف الأصلي.\n"
                         "• تقسيم الملف إلى أجزاء أصغر.",
                         parse_mode='HTML',
                         reply_markup=UIManager.create_error_buttons()
                     )
                     session_manager.clear_session(user_id)
                     return

                caption = (
                    f"✅ <b>تم تنفيذ العملية بنجاح</b>\n\n"
                    f"📌 <b>العملية:</b> {op_info}\n"
                    f"📄 <b>الاسم:</b> {os.path.basename(result_path)}\n"
                    f"📑 <b>الصفحات:</b> {pages_count}\n"
                    f"💾 <b>الحجم:</b> {file_size_mb:.2f} ميجابايت\n"
                    f"⏱️ <b>الوقت:</b> {processing_time:.1f} ثانية\n\n"
                    f"🤖 <b>بواسطة:</b> @TitanPDFBot"
                )

                UIManager.clear_reply_keyboard(message.chat.id)
                with open(result_path, 'rb') as f:
                    bot.send_document(
                        message.chat.id, f, caption=caption, parse_mode='HTML',
                        reply_markup=UIManager.create_completion_buttons()
                    )

                db.log_operation(user_id, op_info, os.path.basename(result_path), os.path.getsize(result_path))
                session_manager.clear_session(user_id)

        except Exception as e:
            try:
                if progress:
                    bot.delete_message(message.chat.id, progress.message_id)
            except Exception:
                pass
            bot.send_message(
                message.chat.id,
                f"❌ <b>حدث خطأ أثناء المعالجة:</b>\n<code>{str(e)}</code>\n\n"
                "حاول مرة أخرى أو تواصل مع الدعم.",
                reply_markup=UIManager.create_error_buttons(),
                parse_mode='HTML'
            )
            session_manager.update_session(user_id, last_error=str(e))
