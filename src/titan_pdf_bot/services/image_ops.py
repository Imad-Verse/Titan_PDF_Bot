import os
import time
import zipfile
import img2pdf
from PIL import Image
import fitz  # PyMuPDF

# Verify fitz (PyMuPDF) installation to catch common "fitz has no attribute open" error
if not hasattr(fitz, "open"):
    try:
        import pymupdf
        fitz = pymupdf
    except ImportError:
        # If both fail, we'll log it later during usage but at least we tried to fix the common naming conflict
        pass

from telebot import types
from titan_pdf_bot.utils.file_utils import FileProcessor
from titan_pdf_bot.utils.ui_utils import UIManager
from titan_pdf_bot.core.loader import bot
from titan_pdf_bot.core.database import db
from titan_pdf_bot.core.session import session_manager


def process_images_to_pdf(image_paths, file_name, user_id):
    output = FileProcessor.build_output_path(user_id, file_name)

    images = []
    for img_path in image_paths:
        try:
            with Image.open(img_path) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background

                temp_path = os.path.splitext(img_path)[0] + "_temp.jpg"
                img.convert('RGB').save(temp_path, 'JPEG', quality=95)
                images.append(temp_path)
        except Exception as e:
            raise Exception(f"خطأ أثناء معالجة الصورة {os.path.basename(img_path)}: {str(e)}")

    try:
        with open(output, "wb") as f:
            f.write(img2pdf.convert(images))
    finally:
        for temp_img in images:
            if os.path.exists(temp_img) and temp_img.endswith("_temp.jpg"):
                try:
                    os.remove(temp_img)
                except Exception:
                    pass

    return output


def process_pdf_to_images(path, uid, prog, msg):
    try:
        start_time = time.time()
        out_dir = FileProcessor.get_user_directory(uid)
        images = []

        if not hasattr(fitz, "open"):
            raise ImportError(
                "❌ مكتبة PyMuPDF (fitz) غير مثبتة بشكل صحيح. "
                "يرجى تشغيل: pip uninstall fitz pymupdf && pip install pymupdf"
            )

        with fitz.open(path) as doc:
            total_pages = len(doc)
            if total_pages == 0:
                raise ValueError("ملف PDF فارغ")

            for i, page in enumerate(doc):
                progress_percent = int(((i + 1) / total_pages) * 100)
                UIManager.update_progress_message(
                    prog.message_id, msg.chat.id, "جارٍ استخراج الصور...", progress_percent
                )

                # Use 300 DPI for high quality (standard is 72 DPI)
                zoom = 300 / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_path = os.path.join(out_dir, f"page_{i + 1}.jpg")
                # Ensure compatibility with different PyMuPDF versions
                pix.save(img_path)
                images.append(img_path)

        try:
            bot.delete_message(msg.chat.id, prog.message_id)
        except Exception:
            pass
        UIManager.clear_reply_keyboard(msg.chat.id)

        if len(images) > 30:
            zip_path = os.path.join(out_dir, "images.zip")
            with zipfile.ZipFile(zip_path, 'w') as z:
                for img in images:
                    z.write(img, os.path.basename(img))
            with open(zip_path, 'rb') as f:
                bot.send_document(
                    msg.chat.id, f, caption="✅ تم جمع كل الصور في ملف ZIP",
                    reply_markup=UIManager.create_completion_buttons()
                )
        else:
            for i in range(0, len(images), 10):
                media_group = []
                opened_files = []
                try:
                    for img_path in images[i:i + 10]:
                        f = open(img_path, 'rb')
                        opened_files.append(f)
                        media_group.append(types.InputMediaPhoto(f))
                    
                    if media_group:
                        bot.send_media_group(msg.chat.id, media_group)
                finally:
                    for f in opened_files:
                        try:
                            f.close()
                        except Exception:
                            pass

            if images:
                bot.send_message(
                    msg.chat.id,
                    f"✅ <b>تم استخراج {len(images)} صورة بنجاح!</b>",
                    reply_markup=UIManager.create_completion_buttons(),
                    parse_mode='HTML'
                )

        db.log_operation(uid, "PDF إلى صور", os.path.basename(path), os.path.getsize(path),
                         processing_time=time.time() - start_time)
        session_manager.clear_session(uid)

    except Exception as e:
        try:
            bot.delete_message(msg.chat.id, prog.message_id)
        except Exception:
            pass
        bot.send_message(
            msg.chat.id, f"❌ <b>خطأ في العملية:</b>\n{str(e)}",
            reply_markup=UIManager.create_error_buttons()
        )
        session_manager.update_session(uid, last_error=str(e))
